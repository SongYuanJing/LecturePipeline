"""Pinned offline PyAV component import, staged before a same-volume rename."""
import argparse,base64,csv,hashlib,io,json,os,shutil,stat,subprocess,sys,uuid,zipfile
from email.parser import Parser
from pathlib import Path,PurePosixPath
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent.parent
FILENAME='av-18.1.0-cp311-abi3-win_amd64.whl'
SHA256='ea1480b7a8d5405cb5f382b344731bf125fd2c1c6fae3964f6c48595628387ff'
DIST='av-18.1.0.dist-info'
COMPONENT='pyav-18.1.0-'+SHA256[:12]

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
  if stat.S_ISLNK(info.external_attr>>16):raise ValueError('Wheel symlink rejected')
  if not info.is_dir():files[name]=info
 if sum(i.file_size for i in files.values())>500_000_000:raise ValueError('Wheel too large')
 metadata=Parser().parsestr(z.read(DIST+'/METADATA').decode())
 wheel=Parser().parsestr(z.read(DIST+'/WHEEL').decode())
 if metadata['Name'].lower()!='av' or metadata['Version']!='18.1.0':raise ValueError('Wrong wheel name/version')
 if wheel.get_all('Tag')!=['cp311-abi3-win_amd64'] or wheel['Root-Is-Purelib']!='false':raise ValueError('Wrong wheel ABI/architecture')
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
 return files

def component_path(root=ROOT):return root/'runtime/components'/COMPONENT

@contextmanager
def import_lock(root):
 import msvcrt
 parent=component_path(root).parent;parent.mkdir(parents=True,exist_ok=True)
 with (parent/'.pyav-import.lock').open('a+b') as lock:
  if lock.tell()==0:lock.write(b'0');lock.flush()
  lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:raise ValueError('Another PyAV import is running; retry after it finishes')
  try:
   for pending in parent.glob(COMPONENT+'.pending-*'):
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
 except (OSError,ValueError,KeyError):return False

def probe(root,stage):
 code="import site,sys,json,pathlib;site.addsitedir(sys.argv[1]);sys.path.insert(0,sys.argv[1]);import av;assert pathlib.Path(sys.argv[1]).resolve() in pathlib.Path(av.__file__).resolve().parents;assert av.__version__=='18.1.0';assert av.library_versions['libavcodec'][0]==62;print(json.dumps(av.library_versions))"
 env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}}
 env['PATH']=str(Path(env.get('SystemRoot',env.get('SYSTEMROOT','C:/Windows')))/'System32')
 result=subprocess.run([str(root/'runtime/asr/python.exe'),'-I','-B','-X','utf8','-c',code,str(stage)],env=env,capture_output=True,text=True,timeout=60)
 if result.returncode:raise ValueError('Private PyAV import failed: '+result.stderr[-1000:])
 return json.loads(result.stdout)

def install(source,root=ROOT):
 source=Path(source)
 if source.name!=FILENAME:raise ValueError('Wrong wheel filename/version/ABI; expected '+FILENAME)
 if source.stat().st_size>100_000_000:raise ValueError('PyAV wheel too large')
 data=source.read_bytes()  # One verified immutable snapshot; no hash/open race.
 if hashlib.sha256(data).hexdigest()!=SHA256:raise ValueError('PyAV SHA256 mismatch')
 if sys.maxsize<2**32 or sys.version_info<(3,11):raise ValueError('Requires private CPython >=3.11 x64')
 with zipfile.ZipFile(io.BytesIO(data)) as z:files=validate_archive(z)
 with import_lock(root):return publish(root,data,files)

def publish(root,data,files):
 dest=component_path(root)
 if dest.exists():
  if valid(root):return 'PyAV: Valid (already imported)'
  raise ValueError('Existing PyAV component invalid; preserved, not overwritten')
 dest.parent.mkdir(parents=True,exist_ok=True)
 stage=dest.parent/(COMPONENT+'.pending-'+uuid.uuid4().hex)
 try:
  stage.mkdir()
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   for name in files:
    target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
  versions=probe(root,stage)
  record={'wheel_sha256':SHA256,'version':'18.1.0','libav_versions':versions,'files':{n:sha(stage/n) for n in files}}
  (stage/'component.json').write_text(json.dumps(record,indent=2),encoding='utf8')
  # Publish only a complete immutable directory. Competing import cannot replace it.
  stage.rename(dest)
 finally:
  if stage.exists():shutil.rmtree(stage)
 return 'PyAV: Valid (imported offline)'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('wheel',type=Path);a=p.parse_args()
 try:print(install(a.wheel))
 except Exception as e:raise SystemExit('PyAV component import failed: '+str(e))
