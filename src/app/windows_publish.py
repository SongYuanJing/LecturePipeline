"""Same-machine guarded rename. No filesystem-name/drive-letter dispatch."""
import ctypes,hashlib,json,os,subprocess,sys
from pathlib import Path
from contextlib import contextmanager
from ctypes import wintypes as W
READ=0x80000000;WRITE=0x40000000;DELETE=0x10000
def kernel():
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
 k.CloseHandle.argtypes=[W.HANDLE]
 k.SetFileInformationByHandle.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];k.SetFileInformationByHandle.restype=W.BOOL
 return k
@contextmanager
def opened(path,access=READ,share=5):
 import msvcrt
 k=kernel();h=k.CreateFileW(str(path),access,share,None,3,0x80,None)
 if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
 try:fd=msvcrt.open_osfhandle(h,os.O_RDONLY|os.O_BINARY)
 except BaseException:k.CloseHandle(h);raise
 with os.fdopen(fd,'rb') as f:yield f
def read_shared(path):
 with opened(path,READ,7) as f:return f.read()
def sha(data):return hashlib.sha256(data).hexdigest()
def rename(stage_handle,target,extended):
 import msvcrt
 name=str(target).encode('utf-16-le')
 class Info(ctypes.Structure):
  _fields_=[('flags',W.DWORD),('root',W.HANDLE),('length',W.DWORD),('name',W.WCHAR*(len(name)//2+1))]
 info=Info();info.flags=3 if extended else 1;info.length=len(name);info.name=str(target)
 k=kernel()
 if not k.SetFileInformationByHandle(msvcrt.get_osfhandle(stage_handle.fileno()),22 if extended else 3,ctypes.byref(info),ctypes.sizeof(info)):raise ctypes.WinError(ctypes.get_last_error())
def writer_blocked(path):
 r=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'probe',str(path)],capture_output=True,text=True,timeout=15,creationflags=0x08000000)
 if r.returncode:raise OSError('Writer probe failed: '+r.stderr[-300:])
 result=json.loads(r.stdout)
 if result.get('winerror')!=32:raise OSError('External writer exclusion not proven: '+str(result))
def checked(path,handle,expected,validate):
 data=read_shared(path)
 if sha(data)!=expected:raise ValueError('External modification / hash mismatch: '+str(path))
 validate(data);handle.seek(0)
 if sha(handle.read())!=expected:raise ValueError('Guard no longer owns expected file: '+str(path))
 if os.stat(path).st_ino!=os.fstat(handle.fileno()).st_ino:raise ValueError('Path/guard identity mismatch: '+str(path))
def dispatch(target,stage,old_handle,new_handle,old_hash,new_hash,validate,checkpoint=lambda name:None):
 checked(target,old_handle,old_hash,validate);checked(stage,new_handle,new_hash,validate)
 writer_blocked(target);writer_blocked(stage)
 names={p.name for p in target.parent.iterdir()}
 try:rename(new_handle,target,True);method='FileRenameInfoEx'
 except OSError as e:
  if getattr(e,'winerror',None)!=87:raise
  # 87 is capability fallback only if this exact operation was a no-op.
  checkpoint('unsupported')
  checked(target,old_handle,old_hash,validate);checked(stage,new_handle,new_hash,validate)
  if {p.name for p in target.parent.iterdir()}!=names:raise ValueError('Directory changed during unsupported rename; no fallback')
  writer_blocked(target);writer_blocked(stage);checkpoint('fallback_gate')
  rename(new_handle,target,False);method='FileRenameInfo'
 checkpoint('after_replace')
 return method
if __name__=='__main__':
 if len(sys.argv)!=3 or sys.argv[1]!='probe':raise SystemExit(2)
 try:
  with opened(Path(sys.argv[2]),WRITE,7):pass
  print(json.dumps({'allowed':True}))
 except OSError as e:print(json.dumps({'allowed':False,'winerror':e.winerror}))
