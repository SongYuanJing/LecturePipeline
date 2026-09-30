import base64,csv,hashlib,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
REPO=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(REPO/'installer'),str(REPO/'scripts')]
import import_pyav as p
from public_exclusions import check

def wheel(path,version='18.1.0',tag='cp311-abi3-win_amd64',extra=None,bad_record=False):
 files={p.DIST+'/METADATA':f'Name: av\nVersion: {version}\n'.encode(),p.DIST+'/WHEEL':f'Root-Is-Purelib: false\nTag: {tag}\n'.encode(),'av/__init__.py':b''}
 files.update(extra or {})
 rows=[[n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode().rstrip('='),str(len(b))] for n,b in files.items()]
 if bad_record:rows[0][1]='sha256=bad'
 rows.append([p.DIST+'/RECORD','','']);s=io.StringIO();csv.writer(s).writerows(rows);files[p.DIST+'/RECORD']=s.getvalue().encode()
 with zipfile.ZipFile(path,'w') as z:
  for n,b in files.items():z.writestr(n,b)

class ThinTests(unittest.TestCase):
 def test_exclusion(self):
  for n in ['runtime/asr/Lib/site-packages/av/__init__.py','av.libs/avcodec-62.dll','av-18.1.0.dist-info/RECORD','ctranslate2/cudnn64_9.dll','models/model.bin','logs/x.log','raw/a.wav','libx265.dll','runtime/cuda/x']:
   with self.subTest(n=n),self.assertRaises(ValueError):check([n])
  check(['components/model-manifest.json','runtime/document/Lib/site-packages/docx/templates/default.docx'])
 def test_archive_matrix(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/p.FILENAME
   for kwargs in [dict(version='17.0.1'),dict(tag='cp311-abi3-win32'),dict(extra={'../escape':b'x'}),dict(extra={'C:/escape':b'x'}),dict(extra={'av/CON':b'x'}),dict(bad_record=True)]:
    wheel(f,**kwargs)
    with zipfile.ZipFile(f) as z,self.assertRaises(ValueError):p.validate_archive(z)
   wheel(f)
   with zipfile.ZipFile(f) as z:self.assertEqual(len(p.validate_archive(z)),4)
 def test_wrong_hash_and_filename(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=root/p.FILENAME;f.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'SHA256'):p.install(f,root)
   with self.assertRaisesRegex(ValueError,'filename'):p.install(root/'wrong.whl',root)
   self.assertFalse((root/'runtime').exists())
 def test_failed_stage_cleanup_and_existing_preservation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=root/p.FILENAME;wheel(f)
   with patch.object(p,'SHA256',p.sha(f)),patch.object(p,'probe',side_effect=ValueError('injected')):
    with self.assertRaisesRegex(ValueError,'injected'):p.install(f,root)
    self.assertFalse(p.component_path(root).exists());self.assertEqual(list((root/'runtime/components').glob('*.pending-*')),[])
   dest=p.component_path(root);dest.mkdir();(dest/'keep').write_text('keep')
   with patch.object(p,'SHA256',p.sha(f)),self.assertRaisesRegex(ValueError,'preserved'):p.install(f,root)
   self.assertEqual((dest/'keep').read_text(),'keep')
 def test_missing_preflight_before_data(self):
  from component_status import require_components
  with tempfile.TemporaryDirectory() as td,self.assertRaisesRegex(RuntimeError,'COMPONENT MISSING: PyAV'):require_components(Path(td))

if __name__=='__main__':unittest.main()
