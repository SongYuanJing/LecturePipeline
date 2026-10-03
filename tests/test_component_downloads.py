"""Tiny disposable supplier fixtures; no installed application or network required."""
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'installer'))
import download_components as downloads
import import_pyav
import setup_gui

URL = 'https://files.pythonhosted.org/packages/fixture.whl'


class Response(io.BytesIO):
    def geturl(self):
        return URL


class DownloadTests(unittest.TestCase):
    def test_long_cuda_cache_path_uses_short_temporary_name(self):
        payload=b'pinned fixture';sha=hashlib.sha256(payload).hexdigest()
        name='nvidia_cublas_cu12-12.9.2.10-py3-none-win_amd64.whl'
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/('x'*(116-len(str(base))-1));cache=root/'cache/downloads'
            final=cache/sha/name
            self.assertLess(len(str(final)),260);self.assertGreaterEqual(len(str(final))+14,260)
            with patch.object(downloads,'open_url',return_value=Response(payload)):
                self.assertEqual(downloads.fetch(URL,sha,name,cache,limit=100),final)
            self.assertEqual(final.read_bytes(),payload)
            self.assertEqual(list(cache.rglob('*.part')),[])

    def test_verified_cache_avoids_network_and_corruption_is_repaired(self):
        payload = b'verified fixture'
        sha = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            with patch.object(downloads, 'open_url', return_value=Response(payload)) as network:
                target = downloads.fetch(URL, sha, 'fixture.whl', cache, limit=100)
                self.assertEqual(target.read_bytes(), payload)
                downloads.fetch(URL, sha, 'fixture.whl', cache, limit=100)
                network.assert_called_once()
            target.write_bytes(b'corrupt cache')
            with patch.object(downloads, 'open_url', return_value=Response(payload)):
                self.assertEqual(downloads.fetch(URL, sha, 'fixture.whl', cache, limit=100).read_bytes(), payload)
            self.assertEqual(list(cache.rglob('*.part')), [])

    def test_bad_hash_size_and_interruption_never_publish(self):
        class Broken(Response):
            def read(self, size):
                if self.tell():
                    raise OSError('connection lost')
                return super().read(size)
        sha = hashlib.sha256(b'expected').hexdigest()
        for response, limit, error in ((Response(b'wrong'), 100, 'SHA256'),
                                       (Response(b'expected'), 2, 'size'),
                                       (Broken(b'partial'), 100, 'connection lost')):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as td:
                with patch.object(downloads, 'open_url', return_value=response):
                    with self.assertRaisesRegex((ValueError, OSError), error):
                        downloads.fetch(URL, sha, 'fixture.whl', Path(td), limit=limit)
                self.assertFalse(any(p.is_file() for p in Path(td).rglob('*')))

    def test_reject_unsafe_names_urls_and_hashes_before_network(self):
        cases = [('http://files.pythonhosted.org/x', 'a' * 64, 'a.whl'),
                 ('https://example.com/x', 'a' * 64, 'a.whl'),
                 (URL, '../bad', 'a.whl'), (URL, 'a' * 64, '../outside'),
                 (URL, 'a' * 64, 'C:bad'), (URL, 'a' * 64, 'NUL.dll')]
        with tempfile.TemporaryDirectory() as td, patch.object(downloads, 'open_url') as network:
            for url, sha, name in cases:
                with self.subTest(name=name, url=url), self.assertRaises(ValueError):
                    downloads.fetch(url, sha, name, Path(td), limit=100)
            network.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'redirect'):
            downloads.HTTPSRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com/x')

    def test_model_real_import_and_rerun_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'launcher').mkdir()
            data = b'tiny pinned model'
            spec = {'model': 'Systran/faster-whisper-large-v3', 'revision': 'a' * 40,
                    'bytes': len(data), 'files': {'model.bin': hashlib.sha256(data).hexdigest()}}
            (root / 'launcher/model-manifest.json').write_text(json.dumps(spec))
            with patch.object(downloads, 'open_url', return_value=Response(data)) as network:
                self.assertIn('Imported', downloads.install('model', root))
                self.assertIn('already verified', downloads.install('model', root))
                network.assert_called_once()
                self.assertIn('/resolve/' + 'a' * 40 + '/model.bin', network.call_args.args[0])
            dest = root / 'models/huggingface/hub/models--Systran--faster-whisper-large-v3'
            self.assertEqual((dest / 'refs/main').read_text(), 'a' * 40)
            self.assertEqual((dest / 'snapshots' / ('a' * 40) / 'model.bin').read_bytes(), data)
            self.assertFalse((root / 'config').exists())

    def test_wrong_download_hash_never_calls_importer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'launcher').mkdir()
            shutil.copy2(REPO / 'components/pyav-manifest.json', root / 'launcher')
            with patch.object(downloads, 'open_url', return_value=Response(b'wrong')), patch.object(import_pyav, 'install') as importer:
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    downloads.install('pyav', root)
                importer.assert_not_called()
            self.assertFalse((root / 'runtime').exists())

    def test_invalid_installed_component_preserved_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dest = import_pyav.component_path(root)
            dest.mkdir(parents=True)
            (dest / 'keep').write_bytes(b'user diagnostic')
            with patch.object(downloads, 'open_url') as network, self.assertRaisesRegex(ValueError, 'preserved'):
                downloads.install('pyav', root)
            network.assert_not_called()
            self.assertEqual((dest / 'keep').read_bytes(), b'user diagnostic')

    def test_cuda_download_extract_and_real_import(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'launcher').mkdir()
            data = b'tiny pinned DLL'
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w') as wheel:
                wheel.writestr('nvidia/cublas/bin/cublas64_12.dll', data)
                wheel.writestr('../../unrelated.txt', b'never extracted')
            payload = archive.getvalue()
            spec = {'files': {'cublas64_12.dll': hashlib.sha256(data).hexdigest()}, 'bytes': len(data),
                    'wheels': {'cuda.whl': {'sha256': hashlib.sha256(payload).hexdigest(),
                                           'bytes': len(payload), 'official_source': URL}}}
            (root / 'launcher/cuda-manifest.json').write_text(json.dumps(spec))
            with patch.object(downloads, 'open_url', return_value=Response(payload)):
                self.assertIn('Imported', downloads.install('cuda', root))
            self.assertEqual((root / 'runtime/cuda/v1.3/cublas64_12.dll').read_bytes(), data)
            self.assertFalse(list(root.rglob('unrelated.txt')))
            with patch.object(downloads, 'open_url') as network:
                self.assertIn('already verified', downloads.install('cuda', root))
                network.assert_not_called()

    def test_cuda_missing_duplicate_and_wrong_dll_rejected(self):
        for entries in ([], [('one/x.dll', b'bad')], [('one/x.dll', b'ok'), ('two/x.dll', b'ok')]):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                wheel_path = root / 'cuda.whl'
                with zipfile.ZipFile(wheel_path, 'w') as wheel:
                    for name, data in entries:
                        wheel.writestr(name, data)
                output = root / 'output'
                output.mkdir()
                with self.assertRaises(ValueError):
                    downloads.extract_cuda([wheel_path], {'files': {'x.dll': hashlib.sha256(b'ok').hexdigest()}, 'bytes': 100}, output)

    def test_required_leaves_cuda_opt_in(self):
        real_install = downloads.install
        with patch.object(downloads, 'install', return_value='OK') as install:
            real_install('required', Path('unused'))
            self.assertEqual([call.args[0] for call in install.call_args_list], ['pyav', 'ctranslate2', 'model'])

    def test_gui_uses_private_runtime_command(self):
        jobs = []
        panel = SimpleNamespace(home=Path('isolated app'), status=Mock(), refresh=Mock(),
                                async_=SimpleNamespace(busy=False, run=lambda fn, done: jobs.append(fn)))
        with patch.object(setup_gui, 'command', return_value='OK') as command:
            setup_gui.Components.download(panel, 'required')
            jobs[0]()
            command.assert_called_once_with(panel.home, 'download_components.py', 'required')

    def test_package_includes_download_entry_and_hashes(self):
        sys.path.insert(0, str(REPO / 'scripts'))
        import build_package
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for kind in ('asr', 'document'):
                runtime = base / 'components' / kind
                runtime.mkdir(parents=True)
                (runtime / 'fixture.txt').write_bytes(b'disposable runtime fixture')
                (runtime / 'component.json').write_text(json.dumps({'files': {
                    'fixture.txt': {'sha256': downloads.digest(runtime / 'fixture.txt')}}}))
            with patch('builtins.print'):
                root = build_package.build(REPO, base / 'components', base / 'package')
            manifest = json.loads((root / 'package-manifest.json').read_text())['files']
            for name in ('DownloadComponents.cmd', 'launcher/download_components.py', 'launcher/cuda-manifest.json'):
                self.assertEqual(manifest[name], downloads.digest(root / name))
            self.assertIn('download_components.py', (root / 'DownloadComponents.cmd').read_text())


if __name__ == '__main__':
    unittest.main()
