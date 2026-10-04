import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
import bootstrap_flow as flow
import download_components as downloads


class Response(io.BytesIO):
    headers={'Content-Length':'6'}
    def geturl(self):return 'https://files.pythonhosted.org/a.whl'


class BootstrapTests(unittest.TestCase):
    def test_cancel_download_removes_partial_and_preserves_verified_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);payload=b'abcdef';sha=hashlib.sha256(payload).hexdigest();calls=[]
            with patch.object(downloads,'open_url',return_value=Response(payload)):
                target=downloads.fetch('https://files.pythonhosted.org/a.whl',sha,'a.whl',root,limit=6,
                    transfer=lambda *row:calls.append(row))
            self.assertEqual(calls,[('a.whl',6,6)])
            ticks=[0]
            def cancel():
                ticks[0]+=1
                if ticks[0]>1:raise flow.Cancelled()
            with patch.object(downloads,'open_url',return_value=Response(payload)),self.assertRaises(flow.Cancelled):
                downloads.fetch('https://files.pythonhosted.org/b.whl',sha,'b.whl',root,limit=6,checkpoint=cancel)
            self.assertEqual(target.read_bytes(),payload)
            self.assertFalse(list(root.rglob('*.part')))
            self.assertFalse((target.parent/'b.whl').exists())

    def test_new_data_unicode_spaces_and_retry_preserves_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'app';data=Path(temporary)/'Данные 课程';root.mkdir()
            def configure(home,stage,*args,**kwargs):
                stage.mkdir();(stage/'user.txt').write_text('retained')
                flow.write(home/'config/config.json',dict(data_root=str(stage),asr=dict(device_mode='cpu')))
            with patch.object(flow.setup,'configure',side_effect=configure) as called:
                cfg=flow.configure_resumable(root,data,'cpu');original=cfg.read_bytes()
                flow.configure_resumable(root,data,'gpu')
                self.assertEqual(called.call_count,1);self.assertEqual(cfg.read_bytes(),original)
                self.assertEqual((data/'user.txt').read_text(),'retained')

    def test_failed_initialization_retries_only_owned_empty_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'app';data=Path(temporary)/'data';root.mkdir()
            def failed(home,stage,*args,**kwargs):
                stage.mkdir();(stage/'partial').write_text('incomplete')
                flow.write(home/'run/dialogue/dialogue_state.json',dict(schema_version=1,mode='dialogue',jobs={}))
                raise RuntimeError('dictionary creation failed')
            with patch.object(flow.setup,'configure',side_effect=failed),self.assertRaises(RuntimeError):
                flow.configure_resumable(root,data,'auto')
            self.assertFalse(data.exists())
            def success(home,stage,*args,**kwargs):
                self.assertFalse(stage.exists());self.assertFalse((home/'run/dialogue/dialogue_state.json').exists())
                stage.mkdir();flow.write(home/'config/config.json',dict(data_root=str(stage)))
            with patch.object(flow.setup,'configure',side_effect=success):flow.configure_resumable(root,data,'auto')
            self.assertTrue(data.is_dir());self.assertFalse((root/'bootstrap-data.json').exists())

    def test_existing_data_not_adopted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'app';data=Path(temporary)/'data';root.mkdir();data.mkdir()
            (data/'keep').write_text('user data')
            with self.assertRaises(ValueError):flow.configure_resumable(root,data,'auto')
            self.assertEqual((data/'keep').read_text(),'user data')

    def test_crash_after_data_move_finishes_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'app';data=Path(temporary)/'data';root.mkdir();data.mkdir()
            stage=data.parent/('.lp-data-'+hashlib.sha256(str(root).encode()).hexdigest()[:12])
            flow.write(root/'bootstrap-data.json',dict(data=str(data),stage=str(stage)))
            flow.write(root/'config/config.json',dict(data_root=str(stage)))
            with patch.object(flow.setup,'configure') as configure:
                cfg=flow.configure_resumable(root,data,'auto');configure.assert_not_called()
            self.assertEqual(json.loads(cfg.read_text())['data_root'],str(data))

if __name__=='__main__':unittest.main()
