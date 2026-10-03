"""Device policy, private probe boundary, first-run persistence; disposable data only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src/app'), str(REPO / 'installer')]
import asr_device as device
import asr_devices
import component_status
import lecture_asr as asr
from pipeline_config import Config, preflight
import setup_gui
spec = importlib.util.spec_from_file_location('setup_modes', REPO / 'installer/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def report(gpu=False, reason='CUDA missing', cpu=True):
    return dict(cpu=dict(available=cpu, reason='CPU ready' if cpu else 'CPU unavailable'),
                gpu=dict(available=gpu, reason='GPU inference passed' if gpu else reason),
                recommended='gpu' if gpu else ('cpu' if cpu else None),
                hardware=dict(adapters=['NVIDIA fixture'], reason=''))


def config_fixture(base, mode='auto'):
    home = base / 'app'
    home.mkdir()
    data = json.loads((REPO / 'config.example.json').read_text(encoding='utf8'))
    data.update(install_root='versions/test', application_home='.', data_root=str(base / 'data'))
    if mode is None:
        data['asr'].pop('device_mode')
    else:
        data['asr']['device_mode'] = mode
    path = home / 'config.json'
    path.write_text(json.dumps(data), encoding='utf8')
    return Config(path)


class DevicePolicyTests(unittest.TestCase):
    def test_nvidia_with_working_private_gpu_stack(self):
        with patch.object(device, 'component_errors', return_value=('', '')), patch.object(device, 'hardware', return_value=report()['hardware']), patch.object(device, 'run_probe', side_effect=[report()['cpu'], report(True)['gpu']]) as probe:
            result = device.detect(Path('isolated'), Path('private/python.exe'), Path('cache'), Path('cuda'), inventory=True)
        self.assertEqual(result['recommended'], 'gpu')
        self.assertEqual(device.select('auto', result)['device'], 'cuda')
        self.assertEqual([call.args[-1] for call in probe.call_args_list], ['cpu', 'cuda'])

    def test_nvidia_without_cuda_uses_cpu_no_gpu_probe(self):
        with patch.object(device, 'component_errors', return_value=('', 'CUDA: Missing')), patch.object(device, 'hardware', return_value=report()['hardware']), patch.object(device, 'run_probe', return_value=report()['cpu']) as probe:
            result = device.detect('isolated', 'python.exe', 'cache', 'cuda', inventory=True)
        self.assertEqual(result['hardware']['adapters'], ['NVIDIA fixture'])
        self.assertEqual(device.select('auto', result)['device'], 'cpu')
        self.assertEqual(probe.call_count, 1)
        self.assertIn('CUDA', result['gpu']['reason'])

    def test_no_gpu_and_nvidia_but_failed_inference_both_fall_back(self):
        for names, reason in (([], 'No NVIDIA device'), (['NVIDIA fixture'], 'CUDA model out of memory')):
            with self.subTest(reason=reason), patch.object(device, 'component_errors', return_value=('', '')), patch.object(device, 'hardware', return_value=dict(adapters=names, reason='')), patch.object(device, 'run_probe', side_effect=[report()['cpu'], report(reason=reason)['gpu']]):
                result = device.detect('isolated', 'python.exe', 'cache', 'cuda', inventory=True)
                self.assertEqual(device.select('auto', result)['device'], 'cpu')
                self.assertEqual(result['recommended'], 'cpu')
                self.assertEqual(result['gpu']['reason'], reason)

    def test_forced_cpu_never_probes_gpu(self):
        with patch.object(device, 'component_errors', return_value=('', '')) as components, patch.object(device, 'run_probe', return_value=report()['cpu']) as probe:
            result = device.detect('isolated', 'python.exe', 'cache', 'absent-cuda', 'cpu')
        self.assertFalse(components.call_args.args[1])
        self.assertEqual([call.args[-1] for call in probe.call_args_list], ['cpu'])
        self.assertEqual(device.select('cpu', report(True))['device'], 'cpu')
        self.assertFalse(device.select('cpu', result)['allow_cpu_fallback'])

    def test_forced_gpu_failure_explains_recovery(self):
        with self.assertRaisesRegex(RuntimeError, 'CUDA missing.*CPU.*Auto'):
            device.select('gpu', report())
        self.assertFalse(device.select('gpu', report(True))['allow_cpu_fallback'])

    def test_missing_cpu_cannot_be_reported_as_successful_auto_fallback(self):
        with self.assertRaisesRegex(RuntimeError, 'CPU ASR'):
            device.select('auto', report(cpu=False))

    def test_bad_mode_rejected_and_legacy_safe_defaults(self):
        for value, expected in (({}, 'auto'), ({'preferred_device': 'gpu'}, 'auto'), ({'preferred_device': 'cpu'}, 'cpu')):
            self.assertEqual(device.configured_mode(value), expected)
        with self.assertRaises(ValueError):
            device.configured_mode(dict(device_mode='cuda'))
        with self.assertRaises(ValueError):
            device.configured_mode(dict(device_mode=None))
        for old in ('gpu', 'cpu', None):
            with tempfile.TemporaryDirectory() as temporary:
                config = config_fixture(Path(temporary), None)
                value = config.data
                if old is None:
                    value['asr'].pop('preferred_device')
                else:
                    value['asr']['preferred_device'] = old
                config.path.write_text(json.dumps(value))
                original = config.path.read_bytes()
                self.assertEqual(Config(config.path).device_mode, 'cpu' if old == 'cpu' else 'auto')
                self.assertEqual(config.path.read_bytes(), original)

    def test_probe_crash_timeout_wrong_device_do_not_grant_gpu(self):
        outcomes = [SimpleNamespace(returncode=0, stdout='{"available":true,"device":"cpu"}'),
                    SimpleNamespace(returncode=1, stderr='native abort', stdout=''),
                    subprocess.TimeoutExpired('private probe', 180)]
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                with patch.object(device.subprocess, 'run', **({'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome})) as run:
                    result = device.run_probe(Path('private/python.exe'), Path('home'), Path('cache'), Path('cuda'), 'cuda')
                    self.assertFalse(result['available'])
                    self.assertEqual(run.call_args.args[0][0], str(Path('private/python.exe')))
                    self.assertEqual(run.call_args.kwargs['env']['HF_HUB_OFFLINE'], '1')
                    self.assertNotIn('PYTHONPATH', run.call_args.kwargs['env'])

    def test_explicit_cpu_component_validation_does_not_read_cuda(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / 'launcher').mkdir()
            (home / 'launcher/pyav-manifest.json').write_text('{}')
            good = component_status.state('Valid')
            with patch.object(component_status, 'base_integrity', return_value=good), patch.object(component_status, 'wheel_state', return_value=good), patch.object(component_status, 'asset_state', return_value=good) as asset:
                self.assertEqual(device.component_errors(home, False), ('', ''))
                self.assertEqual([call.args[-1] for call in asset.call_args_list], ['model'])


class ConfigBackendTests(unittest.TestCase):
    def test_gpu_probe_runs_real_child_boundary_and_consumes_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            cuda = home / 'cuda'
            cuda.mkdir()
            for name in asr.CUDA_DLLS:
                (cuda / name).touch()
            calls = []
            class Model:
                def __init__(self, name, **kwargs):
                    calls.append(('load', name, kwargs))
                    self.model = SimpleNamespace(device=kwargs['device'], compute_type=kwargs['compute_type'])
                def transcribe(self, audio, **kwargs):
                    calls.append(('transcribe', Path(audio).is_file(), kwargs))
                    def segments():
                        calls.append(('iterate',))
                        yield SimpleNamespace(start=0, end=1, text='fixture', avg_logprob=0, no_speech_prob=0, temperature=0)
                    return segments(), SimpleNamespace(duration=1, duration_after_vad=1, language='en')
            modules = {
                'ctranslate2': SimpleNamespace(__file__=str(home / 'ct2.py'), get_cuda_device_count=lambda: 1),
                'faster_whisper': SimpleNamespace(__file__=str(home / 'whisper.py'), WhisperModel=Model),
                'av': SimpleNamespace(__file__=str(home / 'av.py')),
                'numpy': SimpleNamespace(zeros=lambda *a, **k: [0], float32='float32'),
                'faster_whisper.vad': SimpleNamespace(get_speech_timestamps=lambda audio: calls.append(('vad',))) }
            import ctypes
            with patch.dict(sys.modules, modules), patch.object(sys, 'executable', str(home / 'python.exe')), patch.object(asr, '_watch_parent'), patch.object(asr.os, 'add_dll_directory'), patch.object(ctypes, 'WinDLL', return_value=SimpleNamespace(cudnnGetVersion=Mock(return_value=91000))):
                result = device.probe_child(home, home / 'cache', cuda, 'cuda')
            self.assertTrue(result['available'])
            self.assertIn(('iterate',), calls)
            self.assertIn(('vad',), calls)
            load = next(c for c in calls if c[0] == 'load')
            self.assertEqual(load[2], dict(device='cuda', compute_type='int8_float16', local_files_only=True))
            transcribe = next(c for c in calls if c[0] == 'transcribe')
            self.assertTrue(transcribe[1])
            self.assertFalse(transcribe[2]['vad_filter'])

    def test_device_count_does_not_mask_model_load_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            modules = {'ctranslate2': SimpleNamespace(__file__=str(home / 'ct2.py'), get_cuda_device_count=lambda: 1),
                       'faster_whisper': SimpleNamespace(__file__=str(home / 'whisper.py')),
                       'av': SimpleNamespace(__file__=str(home / 'av.py')),
                       'numpy': SimpleNamespace(zeros=lambda *a, **k: [0], float32='float32'),
                       'faster_whisper.vad': SimpleNamespace(get_speech_timestamps=lambda audio: [])}
            def failed(request, result):
                result.write_text(json.dumps(dict(error='CUDA OOM during model load')))
                return 1
            with patch.dict(sys.modules, modules), patch.object(sys, 'executable', str(home / 'python.exe')), patch.object(asr, '_child', side_effect=failed):
                with self.assertRaisesRegex(RuntimeError, 'CUDA OOM'):
                    device.probe_child(home, home / 'cache', home / 'cuda', 'cuda')

    def test_config_selection_reaches_real_model_profiles(self):
        for mode, available, expected in [('auto', True, 'cuda'), ('auto', False, 'cpu'), ('cpu', True, 'cpu'), ('gpu', True, 'cuda')]:
            with self.subTest(mode=mode, available=available), tempfile.TemporaryDirectory() as temporary:
                config = config_fixture(Path(temporary), mode)
                success = dict(segments=[], info=dict(duration=1, language='en'))
                with patch.object(Config, 'model_snapshot'), patch.object(device, 'detect', return_value=report(available)) as detect, patch.object(asr.ProductionWhisperModel, '_invoke', return_value=success) as backend, patch.dict(os.environ):
                    model = config.new_model(device='cuda', compute_type='int8_float16')
                    model.transcribe('disposable.wav')
                    self.assertEqual(backend.call_args.args[2]['device'], expected)
                    self.assertEqual(model.allow_cpu_fallback, mode == 'auto')
                    self.assertEqual(detect.call_args.args[-1], mode)

    def test_forced_gpu_later_oom_does_not_retry_cpu(self):
        model = asr.ProductionWhisperModel(allow_cpu_fallback=False)
        with patch.object(model, '_invoke', side_effect=asr.BackendError('CUDA OOM', cuda=True)) as backend:
            with self.assertRaisesRegex(asr.BackendError, 'CPU fallback отключён.*CPU.*Auto'):
                model.transcribe('disposable.wav')
            self.assertEqual(backend.call_count, 1)
            self.assertFalse(model.cpu_only)

    def test_forced_gpu_config_failure_does_not_construct_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = config_fixture(Path(temporary), 'gpu')
            with patch.object(Config, 'model_snapshot'), patch.object(device, 'detect', return_value=report()), patch.object(asr, 'ProductionWhisperModel') as model, patch.dict(os.environ):
                with self.assertRaisesRegex(RuntimeError, 'GPU недоступен'):
                    config.new_model()
                model.assert_not_called()

    def test_config_selection_cached_but_changed_config_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = config_fixture(Path(temporary))
            with patch.object(device, 'detect', return_value=report()) as detect:
                config.asr_selection()
                config.asr_selection()
                self.assertEqual(detect.call_count, 1)
                config.path.write_text(config.path.read_text() + ' ')
                with self.assertRaisesRegex(ValueError, 'Config изменён'):
                    config.asr_selection()

    def test_preflight_forced_gpu_failure_is_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = config_fixture(Path(temporary), 'gpu')
            with patch.object(device, 'detect', return_value=report()), patch('pipeline_config.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='fixture', stderr='')):
                status = preflight(config)
            check = next(x for x in status['checks'] if x['id'] == 'asr_backend')
            self.assertEqual(check['status'], 'error')
            self.assertIn('CPU или Auto', check['message'])

    def test_preflight_auto_cpu_fallback_is_warning(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = config_fixture(Path(temporary), 'auto')
            with patch.object(device, 'detect', return_value=report()), patch('pipeline_config.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='fixture', stderr='')):
                status = preflight(config)
            check = next(x for x in status['checks'] if x['id'] == 'asr_backend')
            self.assertEqual(check['status'], 'warning')
            self.assertTrue(check['cpu_fallback'])
            self.assertFalse(check['gpu_available'])


class SetupDeviceTests(unittest.TestCase):
    def test_first_run_persists_requested_mode_and_legacy_hint(self):
        for mode, gpu in [('cpu', False), ('auto', False), ('auto', True), ('gpu', True)]:
            with self.subTest(mode=mode, gpu=gpu), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'app'
                (root / 'launcher').mkdir(parents=True)
                (root / 'launcher/config.example.json').write_bytes((REPO / 'config.example.json').read_bytes())
                with patch.object(setup, 'app_root', return_value=root / 'versions/test'), patch.object(setup, 'validate_runtimes'), patch.object(asr_devices, 'selection', return_value=device.select(mode, report(gpu))) as select, patch.object(setup.subprocess, 'run'):
                    path = setup.configure(root, Path(temporary) / 'data', 'term', 'DEMO', device_mode=mode)
                config = Config(path)
                self.assertEqual(config.device_mode, mode)
                self.assertEqual(config.data['schema_version'], 1)
                self.assertEqual(config.data['asr']['preferred_device'], 'gpu' if gpu else 'cpu')
                select.assert_called_once_with(root.resolve(), mode)

    def test_forced_gpu_failure_precedes_all_setup_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'app'
            root.mkdir()
            with patch.object(setup, 'app_root', return_value=root / 'versions/test'), patch.object(setup, 'validate_runtimes'), patch.object(asr_devices, 'selection', side_effect=RuntimeError('GPU недоступен; CPU или Auto')):
                with self.assertRaisesRegex(RuntimeError, 'GPU недоступен'):
                    setup.configure(root, Path(temporary) / 'data', 'term', 'DEMO', device_mode='gpu')
            self.assertEqual(list(root.iterdir()), [])
            self.assertFalse((Path(temporary) / 'data').exists())

    def test_gui_summary_distinguishes_hardware_and_capability(self):
        message = setup_gui.device_summary(report(reason='CUDA missing'), 'gpu')
        self.assertIn('NVIDIA fixture', message)
        self.assertIn('GPU недоступен', message)
        self.assertIn('CPU или Auto', message)

    def test_gui_report_does_not_overwrite_user_choice(self):
        mode = Mock()
        mode.get.return_value = 'CPU'
        jobs = []
        panel = SimpleNamespace(home=Path('disposable'), mode=mode, status=Mock(),
                                async_=SimpleNamespace(busy=False, run=lambda fn, done: jobs.append((fn, done))))
        with patch.object(setup_gui, 'command', return_value=json.dumps(report())) as command:
            setup_gui.DeviceChoice.refresh(panel)
            fn, done = jobs[0]
            done(fn(), None)
            command.assert_called_once_with(panel.home, 'asr_devices.py', 'cpu')
        mode.set.assert_not_called()


if __name__ == '__main__':
    unittest.main()
