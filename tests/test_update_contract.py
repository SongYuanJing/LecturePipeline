import copy
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest
import argparse
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src/app'))
from pipeline_config import Config


class ConfigPointerTests(unittest.TestCase):
    def test_failed_gui_initialization_cannot_send_readiness(self):
        tree=ast.parse((REPO/'src/app/gui_v1.8/app.py').read_text(encoding='utf8'))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        root=Mock()
        scope=dict(argparse=argparse,Path=Path,__file__=str(REPO/'src/app/gui_v1.8/app.py'),
            enable_system_dpi=lambda:None,tk=SimpleNamespace(Tk=lambda:root),
            App=lambda *args:SimpleNamespace(initialized=False),os=os)
        exec(compile(ast.Module(body=[main],type_ignores=[]),'GUI main','exec'),scope)
        with patch.object(sys,'argv',['gui']),patch.dict(os.environ,LP_UPDATE_TOKEN='trial'):
            with self.assertRaisesRegex(RuntimeError,'GUI initialization failed'):scope['main']()
        root.after_idle.assert_not_called();root.mainloop.assert_not_called();root.destroy.assert_called_once()

    def test_pointer_selects_code_without_rewriting_config_and_legacy_survives(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'app';(root/'config').mkdir(parents=True)
            data=json.loads((REPO/'config.example.json').read_text(encoding='utf8'))
            data.update(application_home='..',install_root='../versions/old',data_root=str(base/'data'))
            path=root/'config/config.json';path.write_text(json.dumps(data),encoding='utf8')
            original=path.read_bytes();mtime=path.stat().st_mtime_ns
            (root/'current.json').write_text(json.dumps(dict(path='versions/new',app_version='2.0.0')))
            self.assertEqual(Config(path).install,root/'versions/new')
            tree=ast.parse((REPO/'src/app/gui_v1.8/app.py').read_text(encoding='utf8'))
            function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='bootstrap')
            scope=dict(Path=Path,json=json,sys=sys)
            exec(compile(ast.Module(body=[function],type_ignores=[]),'GUI bootstrap','exec'),scope)
            previous=list(sys.path)
            try:
                scope['bootstrap'](path)
                self.assertEqual(Path(sys.path[0]),root/'versions/new')
            finally:sys.path[:]=previous
            self.assertEqual(Config(path,code_root=root/'versions/.stage-test').install,root/'versions/.stage-test')
            self.assertEqual(path.read_bytes(),original);self.assertEqual(path.stat().st_mtime_ns,mtime)
            legacy=copy.deepcopy(data);legacy.pop('application_home');legacy['install_root']=str(root/'versions/old')
            path.write_text(json.dumps(legacy),encoding='utf8')
            self.assertEqual(Config(path).install,root/'versions/old')


if __name__=='__main__':unittest.main()
