import base64,csv,hashlib,io,json,struct,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
REPO=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(REPO/'installer'),str(REPO/'scripts')]
import import_ctranslate2 as c
import component_status as status
from public_exclusions import check

def wheel(path,version='4.8.2',tag='cp311-cp311-win_amd64',extra=None,bad_record=False):
 pe=bytearray(80);pe[:2]=b'MZ';struct.pack_into('<I',pe,60,64);pe[64:68]=b'PE\0\0';struct.pack_into('<H',pe,68,0x8664)
 files={c.DIST+'/METADATA':f'Name: ctranslate2\nVersion: {version}\n'.encode(),c.DIST+'/WHEEL':f'Root-Is-Purelib: false\nTag: {tag}\n'.encode(),'ctranslate2/__init__.py':b''}
 for n in ('_ext.cp311-win_amd64.pyd','ctranslate2.dll','libiomp5md.dll'):files['ctranslate2/'+n]=bytes(pe)
 files.update(extra or {});rows=[[n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode().rstrip('='),str(len(b))] for n,b in files.items()]
 if bad_record:rows[0][1]='sha256=bad'
 rows.append([c.DIST+'/RECORD','','']);s=io.StringIO();csv.writer(s).writerows(rows);files[c.DIST+'/RECORD']=s.getvalue().encode()
 with zipfile.ZipFile(path,'w') as z:
  for n,b in files.items():z.writestr(n,b)

class CT2Tests(unittest.TestCase):
 def test_public_ownership_exclusion(self):
  for n in ['runtime/asr/Lib/site-packages/ctranslate2/version.py','ctranslate2-4.8.2.dist-info/METADATA','ctranslate2.libs/unknown.dll','ctranslate2-4.8.2.data/any.txt','libiomp5md.dll','unrelated/_ext.cp311-win_amd64.pyd',c.FILENAME]:
   with self.subTest(n=n),self.assertRaises(ValueError):check([n])
 def test_wrong_metadata_abi_and_record(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/c.FILENAME
   for kw in [dict(version='4.8.1'),dict(tag='cp312-cp312-win_amd64'),dict(tag='cp311-cp311-win32'),dict(bad_record=True)]:
    wheel(f,**kw)
    with zipfile.ZipFile(f) as z,self.assertRaises(ValueError):c.validate_archive(z)
 def test_unsafe_paths(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/c.FILENAME
   for n in ['../escape','C:/escape','/escape','ctranslate2/CON.txt','ctranslate2/a:stream','ctranslate2/trailing.','ctranslate2\\evil','ctranslate2/LPT1']:
    wheel(f,extra={n:b'x'})
    with zipfile.ZipFile(f) as z,self.assertRaises(ValueError):c.validate_archive(z)
 def test_duplicate_and_symlink(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/c.FILENAME
   for kind in ('duplicate','symlink','reparse'):
    wheel(f)
    with zipfile.ZipFile(f,'a') as z:
     info=zipfile.ZipInfo('CTRANSLATE2/__init__.py' if kind=='duplicate' else 'unsafe');info.external_attr={'duplicate':0,'symlink':0o120777<<16,'reparse':0x400}[kind];z.writestr(info,b'x')
    with zipfile.ZipFile(f) as z,self.assertRaises(ValueError):c.validate_archive(z)
 def test_filename_hash_malformed(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=root/c.FILENAME;f.write_bytes(b'not zip')
   with self.assertRaisesRegex(ValueError,'filename'):c.install(root/'wrong.whl',root)
   with self.assertRaisesRegex(ValueError,'SHA256'):c.install(f,root)
   with patch.object(c,'SHA256',c.sha(f)),self.assertRaises(zipfile.BadZipFile):c.install(f,root)
   self.assertFalse((root/'runtime').exists())
 def test_native_architecture(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/c.FILENAME;wheel(f,extra={'ctranslate2/ctranslate2.dll':b'bad'})
   with zipfile.ZipFile(f) as z,self.assertRaisesRegex(ValueError,'PE'):c.validate_archive(z)
 def test_failed_probe_cleanup(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=root/c.FILENAME;wheel(f)
   with patch.object(c,'SHA256',c.sha(f)),patch.object(c,'probe',side_effect=ValueError('native failure')):
    with self.assertRaisesRegex(ValueError,'native failure'):c.install(f,root)
   self.assertFalse(c.component_path(root).exists());self.assertEqual(list((root/'runtime/components').glob('*.pending-*')),[])
 def test_corrupt_existing_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=root/c.FILENAME;wheel(f);dest=c.component_path(root);dest.mkdir(parents=True);(dest/'sentinel').write_text('keep')
   with patch.object(c,'SHA256',c.sha(f)),self.assertRaisesRegex(ValueError,'preserved'):c.install(f,root)
   self.assertEqual((dest/'sentinel').read_text(),'keep')
 def test_concurrent_lock(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   with c.import_lock(root),self.assertRaisesRegex(ValueError,'running'):
    with c.import_lock(root):pass
 def test_component_combinations(self):
  for av,ct,model,cuda,expected in [('Missing','Valid','Valid','Missing','Blocked'),('Valid','Missing','Valid','Missing','Blocked'),('Valid','Valid','Missing','Missing','Blocked'),('Valid','Valid','Valid','Missing','Available'),('Valid','Valid','Valid','Valid','Available'),('Invalid','Valid','Valid','Valid','Blocked'),('Valid','Invalid','Valid','Valid','Blocked'),('Valid','Valid','Invalid','Valid','Blocked'),('Valid','Valid','Valid','Invalid','Available')]:
   with self.subTest(av=av,ct=ct,model=model,cuda=cuda),patch.object(status,'base_integrity',return_value=status.state('Valid')),patch.object(status,'wheel_state',side_effect=lambda module,root:status.state(av if module is status.pyav else ct)),patch.object(status,'asset_state',side_effect=lambda root,kind:status.state(cuda if kind=='cuda' else model)),patch.object(status,'probe_backend',return_value={'cpu':True,'gpu':1}):
    r=status.status(Path('unused'));self.assertEqual(r['CPU ASR capability']['status'],expected);self.assertEqual(r['GPU ASR capability']['status'],'Unverified' if expected=='Available' and cuda=='Valid' else 'Blocked') # Device count is not an inference probe.
 def test_missing_ct2_action(self):
  with patch.object(status,'status',return_value={'PyAV':status.state('Valid'),'CTranslate2':status.state('Missing')}),self.assertRaisesRegex(RuntimeError,'ImportCTranslate2.cmd'):status.require_components(Path('unused'))

if __name__=='__main__':unittest.main()
