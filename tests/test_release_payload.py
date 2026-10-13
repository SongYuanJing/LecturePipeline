"""Release metadata/content checks without fetching runtime or suppliers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'scripts'),str(REPO/'installer')]
from build_package import VERSION
from build_bootstrap_payload import build
import updater

class ReleasePayloadTests(unittest.TestCase):
    def test_payload_version_inventory_and_packaged_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);build(REPO,root)
            meta=json.loads((root/'application.json').read_text(encoding='utf8'))
            self.assertEqual(meta['app_version'],VERSION)
            with zipfile.ZipFile(root/'application.zip') as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(set(z.namelist()),set(meta['files']))
                for name,pin in meta['files'].items():
                    self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),pin)
                    self.assertFalse(any(x in name.split('/') for x in ('tests','__pycache__','.local')))
                pointer=json.loads(z.read('current.json'))
                self.assertEqual(pointer,dict(app_version=VERSION,path='versions/'+VERSION))
                prefix=pointer['path']+'/'
                for name in ('lecture_inbox.py','lecture_dates.py','lecture_catalog.py','lecture_progress.py','course_setup.py','gui_v1.8/catalog.py'):
                    self.assertIn(prefix+name,z.namelist())
                z.extractall(root/'extract')
            app=root/'extract'/pointer['path']
            updater.verify_version(app,VERSION)
            spec=importlib.util.spec_from_file_location('packaged_release_config',app/'pipeline_config.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.assertEqual(module.VERSION,VERSION)

    def test_old_beta_can_discover_v2_prerelease_without_protocol_change(self):
        row=dict(tag_name='v'+VERSION,draft=False,prerelease=True)
        self.assertGreater(updater.version(VERSION),updater.version('1.9.7-beta.2'))
        self.assertEqual(updater.discover('1.9.7-beta.2',[row]),row)
        self.assertIsNone(updater.discover(VERSION,[row]))
        self.assertIsNone(updater.discover('1.9.7',[row]))

if __name__=='__main__':unittest.main()
