"""The full Setup payload carries both the new shell and the Tk escape hatch."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from build_bootstrap_payload import build


class DeliveryPayloadTests(unittest.TestCase):
    def test_public_payload_rejects_accidental_user_state_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('src/app', 'installer', 'components'):
                shutil.copytree(REPO / name, root / name)
            shutil.copy2(REPO / 'config.example.json', root / 'config.example.json')
            (root / 'src/app/state.json').write_text('{"lectures":{}}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Public ZIP exclusion failure'):
                build(root, root / 'output', version='2.0.0-beta.5')

    def test_product_dashboard_payload_has_beta_identity_without_dev_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            native = output / 'native'
            native.mkdir()
            for name in ('LecturePipelineDesktop.exe', 'LecturePipelineDesktop.exe.config',
                         'Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll',
                         'WebView2Loader.dll', 'LecturePipeline-A-dark.ico',
                         'LecturePipeline-A-light.ico'):
                (native / name).write_bytes(name.encode('ascii'))
            version = '2.0.0-beta.5'
            build(REPO, output, version=version, desktop_bin=native,
                  distribution_status='beta')
            with zipfile.ZipFile(output / 'application.zip') as archive:
                names = set(archive.namelist())
                self.assertIn('Lecture Pipeline.vbs', names)
                self.assertIn('Lecture Pipeline (Tk).vbs', names)
                self.assertNotIn('Lecture Pipeline DEV.vbs', names)
                self.assertFalse(any('DEV_CANDIDATE' in name for name in names))
                release = json.loads(archive.read('versions/' + version + '/release.json'))
                self.assertEqual(release['app_version'], version)
                self.assertEqual(release['distribution_status'], 'beta')
                self.assertEqual(release['baseline'], 'v1.8.1')
                self.assertEqual(release['data_schema_version']['dictionary'], '1.4')
                self.assertFalse(release['migration_required'])

    def test_unified_payload_has_selected_icon_and_default_dashboard_entry(self):
        native = Path('C:/PipLine GPT WORK/unified-dev/app/versions/2.0.0-beta.5-dev.4/gui_web/native')
        if not native.is_dir():
            self.skipTest('The isolated Sprint 10 native shell is unavailable')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            prepared = output / 'native'
            prepared.mkdir()
            for name in ('LecturePipelineDesktop.exe','LecturePipelineDesktop.exe.config',
                         'Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll',
                         'WebView2Loader.dll'):
                shutil.copy2(native / name, prepared / name)
            for name in ('LecturePipeline-A-dark.ico','LecturePipeline-A-light.ico'):
                shutil.copy2(REPO / 'src/gui_web/desktop' / name, prepared / name)
            version = '2.0.0-beta.5-dev.5'
            build(REPO, output, version=version, desktop_bin=prepared)
            with zipfile.ZipFile(output / 'application.zip') as archive:
                names = set(archive.namelist())
                self.assertIn('Lecture Pipeline.vbs', names)
                self.assertIn('Lecture Pipeline (Tk).vbs', names)
                self.assertIn('versions/' + version + '/gui_v1.8/icon.ico', names)
                self.assertIn('versions/' + version + '/gui_web/native/LecturePipeline-A-dark.ico', names)
                self.assertIn('versions/' + version + '/gui_web/native/LecturePipeline-A-light.ico', names)
                self.assertIn(' dashboard', archive.read('Lecture Pipeline.vbs').decode('ascii'))
                self.assertIn(' gui', archive.read('Lecture Pipeline (Tk).vbs').decode('ascii'))
                release = json.loads(archive.read('versions/' + version + '/release.json'))
                self.assertIn('gui_v1.8/icon.ico', release['files'])


if __name__ == '__main__':
    unittest.main()
