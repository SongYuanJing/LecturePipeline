"""Device policy and isolated private-runtime probes. Never download or write config."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave

MODES = ('auto', 'cpu', 'gpu')
GPU_HELP = 'Выберите CPU или Auto либо восстановите GPU-компоненты и повторите проверку.'


def configured_mode(asr):
    if 'device_mode' in asr:
        mode = asr['device_mode']
    else:
        # Old GPU preference permitted fallback; do not turn it into strict GPU.
        if 'preferred_device' in asr and asr['preferred_device'] not in ('cpu', 'gpu'):
            raise ValueError('preferred_device: cpu или gpu')
        mode = 'cpu' if asr.get('preferred_device') == 'cpu' else 'auto'
    if mode not in MODES:
        raise ValueError('asr.device_mode: auto, cpu или gpu')
    return mode


def select(mode, report):
    if mode not in MODES:
        raise ValueError('Неизвестный режим ASR')
    if mode == 'gpu':
        if not report['gpu']['available']:
            raise RuntimeError('GPU недоступен: ' + report['gpu']['reason'] + '. ' + GPU_HELP)
        device = 'cuda'
    elif mode == 'auto' and report['gpu']['available']:
        device = 'cuda'
    else:
        if not report['cpu']['available']:
            raise RuntimeError('CPU ASR недоступен: ' + report['cpu']['reason'])
        device = 'cpu'
    return dict(mode=mode, device=device, compute_type='int8' if device == 'cpu' else 'int8_float16',
                allow_cpu_fallback=mode == 'auto', reason=report['gpu']['reason'] if mode == 'auto' and device == 'cpu' else '')


def hardware():
    """Informational only: Windows inventory is never proof of GPU ASR capability."""
    try:
        system = Path(os.environ.get('SYSTEMROOT', 'C:/Windows')) / 'System32'
        result = subprocess.run([str(system / 'WindowsPowerShell/v1.0/powershell.exe'),
            '-NoProfile', '-NonInteractive', '-Command',
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); @(Get-CimInstance Win32_VideoController -ErrorAction Stop | Select-Object -ExpandProperty Name) | ConvertTo-Json -Compress"],
            capture_output=True, text=True, encoding='utf8', errors='replace', timeout=15,
            creationflags=0x08000000 if os.name == 'nt' else 0)
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[-300:])
        names = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(names, str):
            names = [names]
        return dict(adapters=names, reason='')
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        return dict(adapters=[], reason='Список видеокарт недоступен: ' + str(exc))


def component_errors(home, check_gpu):
    """Reuse package hashes; legacy layouts without manifests retain runtime probing."""
    if not (home / 'launcher/pyav-manifest.json').exists():
        return '', ''
    # A process belongs to one installation. Do not remove another thread's path
    # entry while the first-run UI is importing its selected release.
    launcher = str(home / 'launcher')
    if launcher not in sys.path:
        sys.path.insert(0, launcher)
    import component_status as components
    required = {'Base runtime': components.base_integrity(home),
                'PyAV': components.wheel_state(components.pyav, home),
                'CTranslate2': components.wheel_state(components.ct2, home),
                'Whisper': components.asset_state(home, 'model')}
    common = '; '.join(name + ': ' + item['status'] for name, item in required.items() if item['status'] != 'Valid')
    cuda = components.asset_state(home, 'cuda') if check_gpu else None
    return common, ('CUDA: ' + cuda['status']) if cuda and cuda['status'] != 'Valid' else ''


def run_probe(python, home, cache, cuda, device, timeout=180):
    """Native abort/OOM/timeout cannot terminate the UI or worker."""
    env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP'}}
    env.update(HF_HUB_CACHE=str(cache), HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               PATH=str(Path(env.get('SYSTEMROOT', env.get('SystemRoot', 'C:/Windows'))) / 'System32'))
    try:
        result = subprocess.run([str(python), '-I', '-B', '-X', 'utf8', str(Path(__file__).resolve()),
            '--probe', str(home), str(cache), str(cuda), device], env=env, capture_output=True,
            text=True, encoding='utf8', errors='replace', timeout=timeout,
            creationflags=0x08000000 if os.name == 'nt' else 0)
        if result.returncode:
            raise RuntimeError('Private runtime exit=' + str(result.returncode) + ': ' + (result.stderr or result.stdout)[-800:])
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or value.get('device') != device or value.get('available') is not True:
            raise RuntimeError('Некорректный ответ private-runtime probe')
        return value
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return dict(available=False, device=device, reason=str(exc))


def detect(home, python, cache, cuda, mode='auto', *, inventory=False):
    if mode not in MODES:
        raise ValueError('Неизвестный режим ASR')
    home, python, cache, cuda = map(lambda p: Path(p).resolve(), (home, python, cache, cuda))
    report = dict(cpu=dict(available=False, reason='Не проверен'),
                  gpu=dict(available=False, reason='GPU не проверялся: выбран CPU'))
    if inventory:
        report['hardware'] = hardware()
    try:
        common, gpu_error = component_errors(home, mode != 'cpu')
    except (OSError, ValueError, ImportError, KeyError) as exc:
        common, gpu_error = str(exc), ''
    if common:
        report['cpu']['reason'] = common
        report['gpu']['reason'] = common
    else:
        report['cpu'] = run_probe(python, home, cache, cuda, 'cpu', timeout=60)
        if mode != 'cpu':
            report['gpu'] = (dict(available=False, reason=gpu_error) if gpu_error else
                             run_probe(python, home, cache, cuda, 'cuda'))
    report['recommended'] = 'gpu' if report['gpu']['available'] else ('cpu' if report['cpu']['available'] else None)
    return report


def probe_child(home, cache, cuda, device):
    """Executed by configured private Python, with no CPU fallback in a GPU probe."""
    import ctranslate2
    import faster_whisper
    import av
    home = Path(home).resolve()
    for module in (ctranslate2, faster_whisper, av):
        if home not in Path(module.__file__).resolve().parents:
            raise RuntimeError('ASR module outside private application: ' + module.__name__)
    if home not in Path(sys.executable).resolve().parents:
        raise RuntimeError('Probe requires private application Python')
    if device == 'cpu':
        if 'int8' not in ctranslate2.get_supported_compute_types('cpu'):
            raise RuntimeError('CPU int8 недоступен')
        return dict(available=True, device='cpu', reason='Private CPU int8 runtime доступен')
    if ctranslate2.get_cuda_device_count() < 1:
        raise RuntimeError('NVIDIA GPU недоступен private runtime (устройство или драйвер)')
    # Force actual inference even if VAD considers the synthetic audio silent.
    # Also exercise the VAD dependency separately, used by the production GPU profile.
    import numpy as np
    from faster_whisper.vad import get_speech_timestamps
    get_speech_timestamps(np.zeros(16000, dtype=np.float32))
    import lecture_asr
    with tempfile.TemporaryDirectory(prefix='lp-gpu-probe-') as temporary:
        folder = Path(temporary)
        audio = folder / 'probe.wav'
        with wave.open(str(audio), 'wb') as out:
            out.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            out.writeframes(b''.join(struct.pack('<h', int(1000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(16000)))
        request = dict(audio=str(audio), profile=lecture_asr.GPU_PROFILE, runtime_dir=str(cuda),
                       parent_pid=os.getppid(), progress=str(folder / 'progress.json'),
                       options=dict(language='en', beam_size=1, temperature=0.0, vad_filter=False,
                                    condition_on_previous_text=False, max_new_tokens=8))
        lecture_asr._write_json(folder / 'request.json', request)
        code = lecture_asr._child(folder / 'request.json', folder / 'result.json')
        result = json.loads((folder / 'result.json').read_text(encoding='utf8'))
        if code or result.get('actual_device') != 'cuda':
            raise RuntimeError(result.get('error', 'GPU inference did not confirm CUDA backend'))
    return dict(available=True, device='cuda', reason='Private GPU probe: model + inference + VAD пройдены')


if __name__ == '__main__':
    if len(sys.argv) != 6 or sys.argv[1] != '--probe':
        raise SystemExit('Internal private-runtime probe')
    # -I does not add the script directory. Only the selected release is exposed.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        print(json.dumps(probe_child(*sys.argv[2:]), ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(str(exc))
