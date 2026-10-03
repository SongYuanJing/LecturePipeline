"""Disposable private-Python process smoke with explicit FAKE supplier modules.

Set LP_TEST_PYTHON311 to an isolated embedded Python 3.11 python.exe. No production
installation is consulted. This proves process/config routing, not native ASR.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
FAKE_WHISPER = '''from pathlib import Path
from types import SimpleNamespace
import json
class WhisperModel:
    def __init__(self, name, device, compute_type, local_files_only):
        assert name == 'large-v3' and local_files_only
        self.model = SimpleNamespace(device=device, compute_type=compute_type)
    def transcribe(self, audio, **options):
        Path(audio).with_suffix('.backend.json').write_text(json.dumps(dict(device=self.model.device, compute_type=self.model.compute_type, vad=options['vad_filter'])))
        row = SimpleNamespace(start=0, end=1, text='FAKE supplier smoke', avg_logprob=0, no_speech_prob=0, temperature=0)
        return iter([row]), SimpleNamespace(duration=1, duration_after_vad=1, language='en')
'''


class DeviceProcessSmoke(unittest.TestCase):
    def test_disposable_config_to_probe_to_asr_child_without_cuda(self):
        python = os.environ.get('LP_TEST_PYTHON311')
        if not python:
            self.skipTest('Provide isolated embedded LP_TEST_PYTHON311; never use an installed app')
        source = Path(python).resolve().parent
        if not (source / 'python311._pth').is_file():
            self.fail('Smoke expects an isolated embedded Python 3.11 directory')
        with tempfile.TemporaryDirectory(prefix='lp-device-smoke-') as temporary:
            base = Path(temporary)
            home = base / 'app'
            runtime = home / 'runtime/asr'
            shutil.copytree(source, runtime)
            app = home / 'versions/test'
            app.mkdir(parents=True)
            for name in ('pipeline_config.py', 'asr_device.py', 'lecture_asr.py'):
                shutil.copy2(REPO / 'src/app' / name, app / name)
            (runtime / 'python311._pth').write_text('python311.zip\n.\n../../versions/test\n', encoding='ascii')
            (runtime / 'av.py').write_text('# FAKE supplier for process contract only\n')
            (runtime / 'ctranslate2.py').write_text("def get_supported_compute_types(device):\n assert device == 'cpu'\n return {'int8'}\ndef get_cuda_device_count():\n return 0\n")
            (runtime / 'faster_whisper.py').write_text(FAKE_WHISPER)
            model = home / 'models/huggingface/hub/models--Systran--faster-whisper-large-v3'
            (model / 'snapshots/fixture').mkdir(parents=True)
            (model / 'refs').mkdir()
            (model / 'refs/main').write_text('fixture')
            for name in ('model.bin', 'config.json', 'tokenizer.json', 'preprocessor_config.json'):
                (model / 'snapshots/fixture' / name).write_text('FAKE model fixture')
            value = json.loads((REPO / 'config.example.json').read_text(encoding='utf8'))
            value.update(application_home='.', install_root='versions/test', data_root=str(base / 'data'))
            config = home / 'config.json'
            audio = base / 'probe.wav'
            audio.write_bytes(b'FAKE audio fixture')
            command = [str(runtime / 'python.exe'), '-I', '-B', '-X', 'utf8', '-c',
                       "import sys; from pipeline_config import Config; c=Config(sys.argv[1]); m=c.new_model(); rows,_=m.transcribe(sys.argv[2]); assert next(rows).text=='FAKE supplier smoke'; print(c.device_mode)", str(config), str(audio)]
            for mode in ('cpu', 'auto'):
                value['asr']['device_mode'] = mode
                config.write_text(json.dumps(value))
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                backend = json.loads(audio.with_suffix('.backend.json').read_text())
                self.assertEqual(backend, dict(device='cpu', compute_type='int8', vad=False))
                self.assertIn(mode, result.stdout)
            # Forced GPU cannot create a CPU output when no GPU is available.
            audio.with_suffix('.backend.json').unlink()
            value['asr']['device_mode'] = 'gpu'
            config.write_text(json.dumps(value))
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('CPU или Auto', result.stderr)
            self.assertFalse(audio.with_suffix('.backend.json').exists())
            self.assertFalse((home / 'runtime/cuda').exists())
            self.assertFalse((base / 'data').exists())


if __name__ == '__main__':
    unittest.main()
