"""Regression for real wheel imports whose old UUID staging exceeded MAX_PATH."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from test_thin_package import wheel as av_wheel
from test_ctranslate2_component import wheel as ct_wheel
import import_pyav
import import_ctranslate2
import import_model


class ShortStagingTests(unittest.TestCase):
    def test_model_snapshot_fits_when_revision_suffix_stage_does_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/('x'*(116-len(str(base))-1));source=base/'source'
            source.mkdir();(root/'launcher').mkdir(parents=True)
            name='preprocessor_config.json';data=b'model path regression'
            (source/name).write_bytes(data)
            spec={'revision':'a'*40,'files':{name:hashlib.sha256(data).hexdigest()}}
            (root/'launcher/model-manifest.json').write_text(json.dumps(spec))
            snapshots=root/'models/huggingface/hub/models--Systran--faster-whisper-large-v3/snapshots'
            final=snapshots/spec['revision']/name
            self.assertLess(len(str(final)),260);self.assertGreaterEqual(len(str(final))+8,260)
            import_model.install(source,root)
            self.assertEqual(final.read_bytes(),data)
            self.assertEqual((source/name).read_bytes(),data)
            self.assertFalse((snapshots/'.model.pending').exists())
            self.assertEqual(import_model.install(source,root),'Existing model verified; no copy')

    def test_long_install_root_uses_short_locked_stage(self):
        for module, fixture, pending in ((import_pyav, av_wheel, '.pyav.pending'),
                                          (import_ctranslate2, ct_wheel, '.ctranslate2.pending')):
            with self.subTest(component=module.COMPONENT), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / ('x' * max(1, 130 - len(str(base)) - 1))
                root.mkdir()
                relative = 'native/' + 'a' * 65 + '.dll'
                final = module.component_path(root) / relative
                self.assertLess(len(str(final)), 260)
                self.assertGreaterEqual(len(str(final)) + 41, 260)
                wheel = root / module.FILENAME
                fixture(wheel, extra={relative: b'regression fixture'})
                stage = module.component_path(root).parent / pending
                stage.mkdir(parents=True)
                (stage / 'interrupted').write_text('previous interrupted importer')
                with patch.object(module, 'SHA256', module.sha(wheel)), patch.object(module, 'probe', return_value={}) as probe:
                    module.install(wheel, root)
                    self.assertEqual(probe.call_args.args[1], stage)
                    self.assertTrue(module.valid(root))
                self.assertTrue(final.is_file())
                self.assertFalse(stage.exists())


if __name__ == '__main__':
    unittest.main()
