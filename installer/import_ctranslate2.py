"""Pinned offline CTranslate2 component import, staged before a same-volume rename."""
import struct
import argparse,base64,csv,hashlib,io,json,os,shutil,stat,subprocess,sys,uuid,zipfile
from email.parser import Parser
from pathlib import Path,PurePosixPath
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent.parent
FILENAME='ctranslate2-4.8.2-cp311-cp311-win_amd64.whl'
SHA256='995938fcd24a1174a7abf9765e7fa216b5b91a1d8e8c4c8f383c7a186e8bab2e'
DIST='ctranslate2-4.8.2.dist-info'
COMPONENT='ctranslate2-4.8.2-'+SHA256[:12]

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()

def validate_archive(z):
 """Validate all names and RECORD before allowing any extraction."""
 files={};seen=set()
 for info in z.infolist():
  name=info.filename;p=PurePosixPath(name)
  if '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or not p.parts:
   raise ValueError('Unsafe wheel path: '+name)
  if any(part.rstrip(' .')!=part or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for part in p.parts):
   raise ValueError('Unsafe Windows wheel path')
  key=name.rstrip('/').casefold()
  if key in seen:raise ValueError('Duplicate wheel path')
  seen.add(key)
  if stat.S_ISLNK(info.external_attr>>16) or (info.external_attr & 0x400) or (stat.S_IFMT(info.external_attr>>16) not in (0,stat.S_IFREG,stat.S_IFDIR)):raise ValueError('Wheel unsafe entry rejected')
  if info.flag_bits & 1:raise ValueError('Encrypted wheel entry rejected')
  if not info.is_dir():files[name]=info
 if sum(i.file_size for i in files.values())>500_000_000:raise ValueError('Wheel too large')
 metadata=Parser().parsestr(z.read(DIST+'/METADATA').decode())
 wheel=Parser().parsestr(z.read(DIST+'/WHEEL').decode())
 if metadata['Name'].lower()!='ctranslate2' or metadata['Version']!='4.8.2':raise ValueError('Wrong wheel name/version')
 if wheel.get_all('Tag')!=['cp311-cp311-win_amd64'] or wheel['Root-Is-Purelib']!='false':raise ValueError('Wrong wheel ABI/architecture')
 rows=list(csv.reader(io.StringIO(z.read(DIST+'/RECORD').decode())))
 recorded=set()
 for name,digest,size in rows:
  if name not in files or name in recorded:raise ValueError('Invalid RECORD path')
  recorded.add(name)
  if name==DIST+'/RECORD':
   if digest or size:raise ValueError('Invalid RECORD self entry')
   continue
  data=z.read(name)
  expected='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
  if digest!=expected or size!=str(len(data)):raise ValueError('RECORD hash/size mismatch: '+name)
 if recorded!=set(files):raise ValueError('Unrecorded wheel file')
 for name in ('ctranslate2/_ext.cp311-win_amd64.pyd','ctranslate2/ctranslate2.dll','ctranslate2/libiomp5md.dll'):
  data=z.read(name)
  if len(data)<64 or data[:2]!=b'MZ':raise ValueError('Invalid native PE image')
  pe=struct.unpack_from('<I',data,60)[0]
  if pe+6>len(data) or data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x8664:raise ValueError('Native architecture must be AMD64')
 return files

def component_path(root=ROOT):return root/'runtime/components'/COMPONENT

@contextmanager
def import_lock(root):
 import msvcrt
 parent=component_path(root).parent;parent.mkdir(parents=True,exist_ok=True)
 with (parent/'.ctranslate2-import.lock').open('a+b') as lock:
  if lock.tell()==0:lock.write(b'0');lock.flush()
  lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:raise ValueError('Another CTranslate2 import is running; retry after it finishes')
  try:
   for pending in [*parent.glob(COMPONENT+'.pending-*'),parent/'.ctranslate2.pending']:
    if not pending.exists():continue
    if pending.is_symlink() or getattr(pending.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Refusing reparse-point staging directory')
    if pending.is_dir():shutil.rmtree(pending)
   yield
  finally:
   lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def valid(root=ROOT):
 dest=component_path(root)
 try:
  manifest=json.loads((dest/'component.json').read_text(encoding='utf8'))
  if manifest['wheel_sha256']!=SHA256:return False
  expected=manifest['files']
  if not expected or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n or ':' in n for n in expected):return False
  actual={p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='component.json'}
  return actual==set(expected) and all(sha(dest/n)==h for n,h in expected.items())
 except (OSError,ValueError,KeyError,TypeError,AttributeError):return False

def probe(root,stage):
 code="import site,sys,json,pathlib,struct;assert sys.version_info[:2]==(3,11) and struct.calcsize('P')==8;site.addsitedir(sys.argv[1]);sys.path.insert(0,sys.argv[1]);import ctranslate2;import ctranslate2._ext as native;stage=pathlib.Path(sys.argv[1]).resolve();assert stage in pathlib.Path(ctranslate2.__file__).resolve().parents;assert stage in pathlib.Path(native.__file__).resolve().parents;assert ctranslate2.__version__=='4.8.2';assert 'int8' in ctranslate2.get_supported_compute_types('cpu');print(json.dumps({'version':ctranslate2.__version__,'architecture':'AMD64','python_abi':'cp311','native_extension':pathlib.Path(native.__file__).name,'cpu_types':sorted(ctranslate2.get_supported_compute_types('cpu'))}))"
 env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}}
 env['PATH']=str(Path(env.get('SystemRoot',env.get('SYSTEMROOT','C:/Windows')))/'System32')
 result=subprocess.run([str(root/'runtime/asr/python.exe'),'-I','-B','-X','utf8','-c',code,str(stage)],env=env,capture_output=True,text=True,timeout=60)
 if result.returncode:raise ValueError('Private CTranslate2 import failed: '+result.stderr[-1000:])
 return json.loads(result.stdout)

def install(source,root=ROOT):
 source=Path(source)
 if source.name!=FILENAME:raise ValueError('Wrong wheel filename/version/ABI; expected '+FILENAME)
 if source.stat().st_size>100_000_000:raise ValueError('CTranslate2 wheel too large')
 data=source.read_bytes()  # One verified immutable snapshot; no hash/open race.
 if hashlib.sha256(data).hexdigest()!=SHA256:raise ValueError('CTranslate2 SHA256 mismatch')
 if sys.maxsize<2**32 or sys.version_info[:2]!=(3,11):raise ValueError('Requires private CPython 3.11 x64')
 with zipfile.ZipFile(io.BytesIO(data)) as z:files=validate_archive(z)
 with import_lock(root):return publish(root,data,files)

def publish(root,data,files):
 dest=component_path(root)
 if dest.exists():
  if valid(root):return 'CTranslate2: Valid (already imported)'
  raise ValueError('Existing CTranslate2 component invalid; preserved, not overwritten')
 dest.parent.mkdir(parents=True,exist_ok=True)
 # Serialized by import_lock; keep staging shorter than the published path.
 stage=dest.parent/'.ctranslate2.pending'
 try:
  stage.mkdir()
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   for name in files:
    target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
  versions=probe(root,stage)
  record={'wheel_sha256':SHA256,'version':'4.8.2','native_probe':versions,'files':{n:sha(stage/n) for n in files}}
  (stage/'component.json').write_text(json.dumps(record,indent=2),encoding='utf8')
  # Publish only a complete immutable directory. Competing import cannot replace it.
  stage.rename(dest)
 finally:
  if stage.exists():shutil.rmtree(stage)
 return 'CTranslate2: Valid (imported offline)'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('wheel',type=Path);a=p.parse_args()
 try:print(install(a.wheel))
 except Exception as e:raise SystemExit('CTranslate2 component import failed: '+str(e))
