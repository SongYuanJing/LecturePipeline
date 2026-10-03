"""v1.3 ASR only. No READY, ledger, publication, Word or dictionary writes.

Native CUDA runs in a disposable process so DLL aborts and OOM cannot corrupt
the scheduled worker. A complete result crosses the boundary only on success.
"""
from __future__ import annotations
import dataclasses
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

VERSION = '1.3'
MODEL = 'large-v3'
RUNTIME = Path(__file__).resolve().parent / 'cuda_runtime' / 'v1.3'
GPU_PROFILE = dict(device='cuda', compute_type='int8_float16', vad_filter=True)
CPU_PROFILE = dict(device='cpu', compute_type='int8', vad_filter=False)
VAD_PARAMETERS = dict(threshold=0.25, neg_threshold=0.1,
                      min_silence_duration_ms=3000, speech_pad_ms=1600)
CUDA_DLLS = ('cublas64_12.dll', 'cublasLt64_12.dll', 'cudnn64_9.dll',
             'cudnn_graph64_9.dll', 'cudnn_ops64_9.dll', 'cudnn_cnn64_9.dll',
             'cudnn_adv64_9.dll', 'cudnn_engines_precompiled64_9.dll',
             'cudnn_engines_runtime_compiled64_9.dll', 'cudnn_heuristic64_9.dll')

class CudaUnavailable(RuntimeError):
    pass

class BackendError(RuntimeError):
    def __init__(self, message, *, cuda=False):
        super().__init__(message)
        self.cuda = cuda

def cuda_error(exc):
    if isinstance(exc, (CudaUnavailable, MemoryError)):
        return True
    text = str(exc).lower()
    return isinstance(exc, (RuntimeError, OSError, ImportError)) and any(
        s in text for s in ('cuda', 'cublas', 'cudnn', 'dll load failed',
                            'out of memory', 'nvcuda', 'no kernel image'))

def bounded_segments(rows, duration):
    """Bound exported millisecond timestamps, retaining every nonempty text.

Text in a wholly late segment is joined to the last valid interval. We never
trim waveform samples or silently drop a possibly meaningful late sentence.
"""
    if not math.isfinite(duration) or duration <= 0:
        if rows:
            raise ValueError('Cannot export speech without a positive audio duration')
        return []
    limit = math.floor(duration * 1000) / 1000
    if limit <= 0 and rows:
        raise ValueError('Audio is shorter than the timestamp resolution')
    result = []
    for start, end, text in rows:
        if not text.strip():
            continue
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            raise ValueError('Invalid ASR timestamp')
        start, end = max(0.0, min(start, limit)), max(0.0, min(end, limit))
        # Rounding in the SRT exporter must not produce a zero-length tail.
        if round(start * 1000) >= round(end * 1000):
            if result:
                old_start, old_end, old_text = result[-1]
                result[-1] = (old_start, max(old_end, end), old_text + ' ' + text)
            else:
                result.append((0.0, max(0.001, end), text))
        else:
            result.append((start, end, text))
    return result

def _write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)

class ProductionWhisperModel:
    def __init__(self, model_size_or_path=MODEL, device='cuda',
                 compute_type='int8_float16', local_files_only=True, *, runtime_dir=None, allow_cpu_fallback=True):
        if model_size_or_path != MODEL or not local_files_only:
            raise ValueError('Production requires the locally cached large-v3; no model substitution')
        if (device, compute_type) not in {('cuda', 'int8_float16'), ('cpu', 'int8')}:
            raise ValueError('Unsupported production ASR profile')
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else RUNTIME
        self.cpu_only = device == 'cpu'
        self.allow_cpu_fallback = allow_cpu_fallback
        self.fallback_reason = None
        self.last_run = None
        self.progress_callback = None
        self.progress_context = {}

    def _invoke(self, audio, options, profile):
        with tempfile.TemporaryDirectory(prefix='lecture-asr-') as folder:
            folder = Path(folder)
            request, result, progress = [folder / n for n in ('request.json','result.json','progress.json')]
            _write_json(request, dict(audio=str(Path(audio).resolve()), options=options,
                       profile=profile, runtime_dir=str(self.runtime_dir.resolve()),
                       parent_pid=os.getpid(), progress=str(progress)))
            python = Path(sys.executable).with_name('python.exe') if sys.platform == 'win32' else Path(sys.executable)
            process = subprocess.Popen([str(python), '-B', '-X', 'utf8', str(Path(__file__).resolve()),
                        '--child', str(request), str(result)], stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                        creationflags=0x08000000 if sys.platform == 'win32' else 0)
            started = time.monotonic()
            try:
                while True:
                    try:
                        output, _ = process.communicate(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        if self.progress_callback and progress.exists():
                            try:
                                value=json.loads(progress.read_text(encoding='utf8'))
                                self.progress_callback(dict(value,**self.progress_context))
                            except Exception:
                                pass # Observational telemetry must never change ASR outcome.
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            data = json.loads(result.read_text(encoding='utf-8')) if result.exists() else None
            if process.returncode != 0 or not data or data.get('status') != 'ok':
                phase = json.loads(progress.read_text(encoding='utf-8')).get('phase') if progress.exists() else None
                message = data.get('error', '') if data else output[-4000:]
                native = (process.returncode & 0xffffffff) in {0xc0000005, 0xc0000409, 0xc0000135, 0xc000007b, 0xc0000017}
                is_cuda = profile['device'] == 'cuda' and (
                    bool(data and data.get('cuda_error')) or
                    (not data and (phase == 'cuda_setup' or native or cuda_error(RuntimeError(message)))))
                raise BackendError(f"ASR {profile['device']} failed (exit={process.returncode}, phase={phase}): {message}", cuda=is_cuda)
            data['process_wall_s'] = time.monotonic() - started
            return data

    def transcribe(self, audio, **options):
        # Avoid propagating hallucinated context on GPU; preserve v1.2 CPU behavior.
        options = dict(options, beam_size=5)
        profile = CPU_PROFILE if self.cpu_only else GPU_PROFILE
        options['vad_filter'] = profile['vad_filter']
        options['condition_on_previous_text'] = profile['device'] == 'cpu'
        options.pop('vad_parameters', None)
        if profile['vad_filter']:
            options['vad_parameters'] = VAD_PARAMETERS.copy()
        try:
            data = self._invoke(audio, options, profile)
        except BackendError as exc:
            if self.cpu_only or not exc.cuda:
                raise
            if not self.allow_cpu_fallback:
                raise BackendError(str(exc) + '. GPU выбран явно; CPU fallback отключён. Выберите CPU или Auto.', cuda=exc.cuda) from exc
            self.cpu_only = True  # Sticky for this worker/model lifetime, not persisted in state.
            self.fallback_reason = str(exc)
            print('    ASR FALLBACK CPU large-v3/int8/VAD=false: ' + str(exc), flush=True)
            options['vad_filter'] = False
            options['condition_on_previous_text'] = True
            options.pop('vad_parameters', None)
            data = self._invoke(audio, options, CPU_PROFILE)
        data['fallback_reason'] = self.fallback_reason
        self.last_run = {k:v for k,v in data.items() if k != 'segments'}
        print('    ASR result: ' + json.dumps(self.last_run, ensure_ascii=False), flush=True)
        rows = [SimpleNamespace(**row) for row in data['segments']]
        return iter(rows), SimpleNamespace(**data['info'])

def _watch_parent(pid):
    if sys.platform != 'win32':
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
    def watch():
        if kernel.WaitForSingleObject(handle, 0xffffffff) == 0:
            os._exit(74)
    threading.Thread(target=watch, daemon=True).start()

def _child(request_file, result_file):
    request = json.loads(Path(request_file).read_text(encoding='utf-8'))
    profile = request['profile']; started = time.monotonic(); phase = 'start'
    last_emit=0.0;audio_duration=0.0;processed=0.0;language=request.get('options',{}).get('language') or 'auto'
    def set_phase(name,force=True):
        nonlocal phase,last_emit
        phase=name;now=time.monotonic()
        if not force and now-last_emit<1:return
        last_emit=now
        try:_write_json(request['progress'],dict(phase=name,audio_duration_sec=audio_duration,processed_audio_sec=min(processed,audio_duration),elapsed_sec=now-started,backend=profile['device'],model=MODEL,language=language,updated_at=time.time()))
        except OSError:pass
    try:
        _watch_parent(request['parent_pid'])
        if profile['device'] == 'cuda':
            set_phase('cuda_setup')
            runtime = Path(request['runtime_dir'])
            missing = [n for n in CUDA_DLLS if not (runtime/n).is_file()]
            if missing:
                raise CudaUnavailable('Missing local CUDA DLLs: ' + ', '.join(missing))
            os.environ['PATH'] = str(runtime) + os.pathsep + os.environ.get('PATH', '')
            dll_handle = os.add_dll_directory(str(runtime))
            import ctypes
            cudnn = ctypes.WinDLL(str(runtime/'cudnn64_9.dll'))
            cudnn.cudnnGetVersion.restype = ctypes.c_size_t
            cudnn.cudnnGetVersion()  # Native missing-backend abort is confined to this child.
        set_phase('model_load')
        from faster_whisper import WhisperModel
        model = WhisperModel(MODEL, device=profile['device'], compute_type=profile['compute_type'], local_files_only=True)
        if model.model.device != profile['device']:
            raise RuntimeError('ASR backend differs from requested device: ' + str(model.model.device))
        load_s = time.monotonic()-started
        set_phase('transcribe'); transcription_started = time.monotonic()
        segments, info = model.transcribe(request['audio'], **request['options'])
        audio_duration=float(info.duration);language=info.language;rows=[];set_phase('transcribe')
        for s in segments:
            processed=max(processed,float(s.end));set_phase('transcribe',False)
            if s.text.strip():
                rows.append(dict(start=float(s.start),end=float(s.end),text=s.text.strip(),avg_logprob=float(s.avg_logprob),no_speech_prob=float(s.no_speech_prob),temperature=float(s.temperature)))
        processed=audio_duration;set_phase('asr_complete')
        data = dict(status='ok', version=VERSION, model=MODEL, profile=profile,
                    vad_parameters=request['options'].get('vad_parameters'),
                    condition_on_previous_text=request['options'].get('condition_on_previous_text'),
                    actual_compute_type=model.model.compute_type,
                    actual_device=model.model.device,
                    load_s=load_s, transcribe_s=time.monotonic()-transcription_started,
                    info=dict(duration=float(info.duration), language=info.language,
                              duration_after_vad=float(info.duration_after_vad)), segments=rows)
        _write_json(result_file,data)
        return 0
    except Exception as exc:
        _write_json(result_file,dict(status='error',phase=phase,error=f'{type(exc).__name__}: {exc}',
                                    cuda_error=profile['device']=='cuda' and (phase=='cuda_setup' or cuda_error(exc))))
        return 1

if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--child':
        raise SystemExit('Internal ASR child; use lecture_pipeline.py')
    raise SystemExit(_child(sys.argv[2],sys.argv[3]))
