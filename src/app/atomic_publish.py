"""v1.8.1 same-machine transaction protocol. Never coordinates different PCs.

A stable sidecar plus a Windows named mutex outlive target replacement. Target
guards exclude Excel; uncertain external modifications are never rolled back.
"""
from __future__ import annotations
import ctypes,hashlib,json,os,re,threading,uuid
from pathlib import Path
from contextlib import contextmanager
from ctypes import wintypes
import windows_publish as win

_held=set();_mu=threading.Lock()
def sha(data):return hashlib.sha256(data).hexdigest()
def sidecar(path,suffix):return path.with_name('.'+path.name+'.transaction.'+suffix)
def kernel():
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];k.CreateFileW.restype=wintypes.HANDLE
 k.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR];k.CreateMutexW.restype=wintypes.HANDLE
 k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
 k.ReleaseMutex.argtypes=[wintypes.HANDLE];k.CloseHandle.argtypes=[wintypes.HANDLE]
 return k

@contextmanager
def handle(path,*,create=False,replaceable=False):
 if os.name!='nt':raise OSError('Atomic publish currently requires Windows')
 import msvcrt
 k=kernel();h=k.CreateFileW(str(path),0xC0000000,4 if replaceable else 0,None,4 if create else 3,0x80,None)
 if h==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'Файл занят/недоступен. Закройте Excel или другой writer: '+str(path))
 try:fd=msvcrt.open_osfhandle(h,os.O_RDWR|os.O_BINARY)
 except BaseException:k.CloseHandle(h);raise
 with os.fdopen(fd,'r+b') as f:yield f

@contextmanager
def transaction_lock(target):
 target=Path(target).resolve();identity=os.path.normcase(str(target));k=kernel()
 with _mu:
  if identity in _held:raise OSError('Транзакция уже выполняется: '+str(target))
  _held.add(identity)
 mutex=None;owned=False
 try:
  mutex=k.CreateMutexW(None,False,'Global\\LecturePipeline.Publish.'+sha(identity.encode()))
  if not mutex:raise ctypes.WinError(ctypes.get_last_error())
  status=k.WaitForSingleObject(mutex,0)
  if status not in (0,0x80):raise OSError('Другой процесс выполняет транзакцию: '+str(target))
  owned=True
  # Never replace/delete the sidecar. The mutex also protects against sync
  # replacing its file object on this machine. Both remain held through recovery.
  with handle(sidecar(target,'lock'),create=True):yield
 finally:
  if owned:k.ReleaseMutex(mutex)
  if mutex:k.CloseHandle(mutex)
  with _mu:_held.discard(identity)

@contextmanager
def target_guard(path):
 path=Path(path).resolve()
 if path.suffix.lower()=='.xlsx' and path.with_name('~$'+path.name).exists():raise OSError('Закройте Excel: книга открыта либо остался owner-файл; автоматическая запись запрещена')
 # Permit our rename but deny other readers/writers of this file object.
 with win.opened(path) as f:yield f

@contextmanager
def exclusive(path):
 with transaction_lock(path):
  with target_guard(path) as f:yield f

def durable(path,data):
 """Only new, transaction-owned files; no user target is opened for writing."""
 with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def atomic_json(path,value):
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  durable(tmp,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode('utf8'));os.replace(tmp,path)
 finally:
  try:tmp.unlink(missing_ok=True)
  except OSError:pass

def _metadata(target,root):
 path=sidecar(target,'json')
 if not path.exists():return None
 try:m=json.loads(path.read_text(encoding='utf8'))
 except Exception as e:raise ValueError('Повреждён recovery journal; сохранён для ручной проверки') from e
 valid=(m.get('schema_version')==1 and m.get('target')==str(target) and re.fullmatch('[0-9a-f]{32}',str(m.get('id',''))))
 if not valid:raise ValueError('Неверный recovery journal; запись запрещена')
 tx=root/m['id'];stage=target.with_name('.'+target.name+'.'+m['id']+'.pending')
 if m.get('backup')!=str(tx/target.name) or m.get('receipt')!=str(tx/'transaction.json') or m.get('stage')!=str(stage):raise ValueError('Recovery paths не соответствуют target/backup root')
 for key in ('before','after'):
  if not re.fullmatch('[0-9a-f]{64}',str(m.get(key,''))):raise ValueError('Некорректный recovery hash')
 return m

def _finish(target,m,status):
 receipt=dict(m,status=status,old_sha256=m['before'],new_sha256=m['after'])
 atomic_json(Path(m['receipt']),receipt)
 # Only metadata-identified staging; target and verified backup are retained.
 Path(m['stage']).unlink(missing_ok=True)
 sidecar(target,'json').unlink()
 return receipt

def _recover(target,root,validate):
 m=_metadata(target,root)
 if m is None:return None
 backup=Path(m['backup'])
 if not backup.is_file() or sha(backup.read_bytes())!=m['before']:raise ValueError('Backup recovery повреждён; evidence сохранён')
 with target_guard(target) as f:
  actual=f.read();h=sha(actual)
  if h not in (m['before'],m['after']):raise ValueError('External modification: target не принадлежит pending transaction; blind rollback запрещён')
  validate(actual)
  return _finish(target,m,'committed' if h==m['after'] else 'aborted_before_replace')

def recover(target,backup_root,validate):
 target=Path(target).resolve();root=Path(backup_root).resolve()
 with transaction_lock(target):return _recover(target,root,validate)

def publish(target,expected,build,validate,backup_root,*,checkpoint=None):
 """build(old_bytes)->new_bytes runs under stable lock. No blind rollback.

If failure occurs after replace, the complete new file remains; pending metadata
allows a later locked recovery to verify it and complete the success receipt.
checkpoint is an injected test callback, never an env flag or production default.
"""
 target=Path(target).resolve();root=Path(backup_root).resolve()
 def point(name):
  if checkpoint:checkpoint(name)
 with transaction_lock(target):
  _recover(target,root,validate)
  with target_guard(target) as original:
   old=original.read()
   if sha(old)!=expected:raise ValueError('Target changed after reading; regenerate proposal')
   validate(old);new=build(old)
   if new==old:return None
   validate(new)
   identity=uuid.uuid4().hex;tx=root/identity;tx.mkdir(parents=True)
   backup=tx/target.name;stage=target.with_name('.'+target.name+'.'+identity+'.pending')
   durable(backup,old)
   if sha(backup.read_bytes())!=expected:raise OSError('Backup verification failed')
   m=dict(schema_version=1,id=identity,target=str(target),before=expected,after=sha(new),backup=str(backup),receipt=str(tx/'transaction.json'),stage=str(stage))
   atomic_json(sidecar(target,'json'),m);point('prepared')
   durable(stage,new);staged=stage.read_bytes()
   if sha(staged)!=m['after']:raise OSError('Staging hash mismatch')
   validate(staged);point('before_replace')
   with win.opened(stage,win.READ|win.DELETE) as staged_handle:
    method=win.dispatch(target,stage,original,staged_handle,expected,m['after'],validate,point)
    point('before_postverify');actual=win.read_shared(target)
    if sha(actual)!=m['after']:raise ValueError('External modification after replace; evidence retained')
    validate(actual);win.writer_blocked(target);point('after_postverify')
    m['replacement_method']=method
    result=_finish(target,m,'committed');point('finished')
   return result
