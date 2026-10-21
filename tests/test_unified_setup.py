"""The desktop candidate must be self-identifying and keep its data separate."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer'))
sys.path.insert(0, str(ROOT / 'src/app'))
import setup as installer_setup


class UnifiedSetupTests(unittest.TestCase):
    def test_dev_setup_writes_isolation_marker_and_rejects_external_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / 'candidate'
            root, data = candidate / 'app', candidate / 'data'
            app = root / 'versions' / '2.0.0-beta.5-dev.2'
            (app / 'gui_web').mkdir(parents=True)
            (app / 'gui_web/desktop_runner.py').write_text('', encoding='utf-8')
            (app / 'release.json').write_text(json.dumps({'distribution_status': 'dev'}), encoding='utf-8')
            (root / 'launcher').mkdir(parents=True)
            (root / 'launcher/config.example.json').write_bytes((ROOT / 'config.example.json').read_bytes())

            def make_book(command, **_):
                book = Path(command[2])
                book.parent.mkdir(parents=True, exist_ok=True)
                book.write_bytes(b'disposable test dictionary')

            with patch.object(installer_setup, 'app_root', return_value=app), \
                    patch.object(installer_setup, 'validate_runtimes'), \
                    patch('asr_devices.selection', return_value={'device': 'cpu'}), \
                    patch.object(installer_setup.subprocess, 'run', side_effect=make_book):
                with self.assertRaisesRegex(ValueError, 'sibling'):
                    installer_setup.configure(root, Path(temporary) / 'outside', 'sprint09', 'METHODS')
                self.assertFalse((root / 'config/config.json').exists())
                self.assertFalse((candidate / 'DEV_CANDIDATE.json').exists())
                installer_setup.configure(root, data, 'sprint09', 'METHODS')
            marker = json.loads((candidate / 'DEV_CANDIDATE.json').read_text(encoding='utf-8'))
            self.assertEqual(marker['install_root'], str(root.resolve()))
            self.assertEqual(marker['data_root'], str(data.resolve()))
            self.assertEqual(marker['purpose'], 'Lecture Pipeline unified DEV')


if __name__ == '__main__':
    unittest.main()
