"""Read-only prerequisite states; never initialize user data or fall back to host packages."""
import json,os,subprocess
from pathlib import Path
import import_pyav as pyav
import import_ctranslate2 as ct2
ROOT=pyav.ROOT

def state(status,reason=''):return {'status':status,'reason':reason}

def wheel_state(module,root):
 if not module.component_path(root).exists():return state('Missing')
 return state('Valid') if module.valid(root) else state('Invalid','Imported component files do not match its manifest')

def asset_state(root,kind):
 try:
  spec=json.loads((root/'launcher'/(kind+'-manifest.json')).read_text(encoding='utf8'))
  folder=root/'runtime/cuda/v1.3' if kind=='cuda' else root/'models/huggingface/hub/models--Systran--faster-whisper-large-v3/snapshots'/spec['revision']
  if not folder.exists():return state('Missing','Optional for CPU' if kind=='cuda' else 'Import verified large-v3')
  ok=all((folder/n).is_file() and pyav.sha(folder/n)==h for n,h in spec['files'].items())
  return state('Valid') if ok else state('Invalid','Component file hash mismatch')
 except (OSError,ValueError,KeyError):return state('Invalid','Missing or invalid component requirement manifest')

def base_integrity(root):
 try:
  m=json.loads((root/'package-manifest.json').read_text(encoding='utf8'))
  selected={n:h for n,h in m['files'].items() if n.startswith(('runtime/asr/','runtime/document/','launcher/'))}
  if not selected:return state('Invalid','Base package manifest is empty')
  if any('..' in Path(n).parts or Path(n).is_absolute() or not (root/n).is_file() or pyav.sha(root/n)!=h for n,h in selected.items()):return state('Invalid','Base runtime hash mismatch; restore the original ZIP')
  return state('Valid')
 except (OSError,ValueError,KeyError):return state('Invalid','Base package manifest missing or invalid')

def probe_backend(root):
 env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}}
 env['PATH']=str(Path(env.get('SystemRoot',env.get('SYSTEMROOT','C:/Windows')))/'System32')
 code="import sys,pathlib,json;root=pathlib.Path(sys.argv[1]).resolve();import ctranslate2,faster_whisper,av;assert root/'runtime/components' in pathlib.Path(ctranslate2.__file__).resolve().parents;assert root/'runtime/components' in pathlib.Path(av.__file__).resolve().parents;assert all(root==pathlib.Path(p).resolve() or root in pathlib.Path(p).resolve().parents for p in sys.path if p);print(json.dumps({'cpu':'int8' in ctranslate2.get_supported_compute_types('cpu'),'gpu':ctranslate2.get_cuda_device_count()}))"
 r=subprocess.run([str(root/'runtime/asr/python.exe'),'-I','-B','-X','utf8','-c',code,str(root)],env=env,capture_output=True,text=True,timeout=60,creationflags=0x08000000 if os.name=='nt' else 0)
 if r.returncode:raise RuntimeError(r.stderr[-800:])
 return json.loads(r.stdout)

def status(root=ROOT):
 result={'Base runtime':base_integrity(root),'PyAV':wheel_state(pyav,root),'CTranslate2':wheel_state(ct2,root),'Whisper model':asset_state(root,'model'),'CUDA':asset_state(root,'cuda')}
 blocked=[name+': '+result[name]['status'] for name in ('Base runtime','PyAV','CTranslate2','Whisper model') if result[name]['status']!='Valid']
 cpu=state('Blocked','; '.join(blocked));gpu=state('Blocked','; '.join(blocked))
 if not blocked:
  try:
   cap=probe_backend(root)
   cpu=state('Available') if cap['cpu'] else state('Blocked','CPU int8 unavailable')
   gpu=state('Available') if cap['gpu']>0 and result['CUDA']['status']=='Valid' else state('Blocked','CUDA '+result['CUDA']['status']+' or NVIDIA GPU unavailable; CPU remains independent')
  except (OSError,ValueError,subprocess.SubprocessError,RuntimeError) as exc:cpu=gpu=state('Blocked','Private ASR runtime validation failed: '+str(exc))
 result['CPU ASR capability']=cpu;result['GPU ASR capability']=gpu
 return result

def require_components(root=ROOT):
 result=status(root)
 actions={'PyAV':'ImportPyAV.cmd','CTranslate2':'ImportCTranslate2.cmd','Whisper model':'ImportModel.cmd'}
 for name,action in actions.items():
  item=result[name]
  if item['status']!='Valid':raise RuntimeError('COMPONENT '+item['status'].upper()+': '+name+'. Run '+action+' with the pinned offline component. No workspace/state created.')
 if result['CPU ASR capability']['status']!='Available':raise RuntimeError('CPU ASR blocked: '+result['CPU ASR capability']['reason'])
 return result

if __name__=='__main__':print(json.dumps(status(),ensure_ascii=False,indent=2))
