import copy
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src/app'))
from pipeline_config import Config


class ConfigPointerTests(unittest.TestCase):
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
