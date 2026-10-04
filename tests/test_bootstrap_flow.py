import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
import bootstrap_flow as flow
import download_components as downloads
import launch


class Response(io.BytesIO):
    headers={'Content-Length':'6'}
    def geturl(self):return 'https://files.pythonhosted.org/a.whl'


class BootstrapTests(unittest.TestCase):
    def test_bridge_cuda_download_is_only_a_hint_and_cpu_skips_it(self):
        app=Path(__file__).resolve().parents[1]/'src/app'
        sys.path.insert(0,str(app))
        import asr_device
        import pipeline_config
        for mode,adapters,expected in [('cpu',['NVIDIA'],['required']),('auto',[],['required']),
            ('auto',['NVIDIA GeForce'],['required','cuda']),('gpu',[],['required','cuda'])]:
            with self.subTest(mode=mode,adapters=adapters),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/'app';root.mkdir();data=Path(temporary)/'data'
                with patch.object(flow,'app_root',return_value=app), \
                     patch.object(asr_device,'hardware',return_value=dict(adapters=adapters,reason='')), \
                     patch.object(flow.download_components,'install',return_value='verified') as install, \
                     patch.object(flow,'configure_resumable',return_value=root/'config/config.json'), \
                     patch.object(pipeline_config,'Config') as config, \
                     patch.object(flow.component_status,'status',return_value={'CPU ASR capability':{'status':'Available'}}),redirect_stdout(io.StringIO()):
                    config.return_value.asr_selection.return_value={'device':'cpu'}
                    flow.run(root,data,mode,root/'cancel')
                    self.assertEqual([call.args[0] for call in install.call_args_list],expected)
                    self.assertEqual(json.loads((root/'logs/bootstrap-health.json').read_text())['selection']['device'],'cpu')

    def test_incomplete_install_blocks_launch_but_legacy_and_ready_enter_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for status in ('installing','cancelled','failed'):
                flow.write(root/'bootstrap-state.json',dict(status=status))
                with patch.object(launch,'ROOT',root),patch.object(launch,'app_root') as enter:
                    with self.assertRaisesRegex(RuntimeError,'не завершена'):launch.main()
                    enter.assert_not_called()
            for status in ('ready',None):
                if status:flow.write(root/'bootstrap-state.json',dict(status=status))
                else:(root/'bootstrap-state.json').unlink()
                with patch.object(launch,'ROOT',root),patch.object(launch,'app_root',side_effect=RuntimeError('entered existing launcher')):
                    with self.assertRaisesRegex(RuntimeError,'entered existing launcher'):launch.main()

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
