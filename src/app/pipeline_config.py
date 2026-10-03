"""v1.7 configuration boundary. No data writes, downloads, or directory creation."""
from __future__ import annotations
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path

VERSION='1.7'
class ConfigError(ValueError):pass
def need(ok,message):
 if not ok:raise ConfigError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def inside(path,root):return path==root or root in path.parents
def child(root,value):
 need(isinstance(value,str) and bool(value.strip()),'Пустой путь в config')
 p=Path(value);need(not p.is_absolute() and '..' not in p.parts,'Ожидается относительный путь без ..: '+value)
 result=(root/p).resolve();need(inside(result,root),'Путь выходит за разрешённый корень: '+value);return result
class Config:
 def __init__(self,path=None):
  self.path=Path(path or os.environ.get('LECTURE_CONFIG') or Path(__file__).with_name('config.json')).resolve()
  try:self.bytes=self.path.read_bytes();self.data=json.loads(self.bytes.decode('utf-8-sig'))
  except (OSError,ValueError) as e:raise ConfigError('Не читается config: '+str(self.path)+'; '+str(e)) from e
  d=self.data;need(d.get('schema_version')==1,'Неизвестная версия config; миграция должна быть явной')
  self.install=(self.path.parent/Path(d.get('install_root','.'))).resolve()
  self.home=(self.path.parent/Path(d.get('application_home',d.get('install_root','.')))).resolve()
  need(inside(self.install,self.home),'Application code must be inside application_home')
  self.data_root=Path(d['data_root']).expanduser().resolve();need(Path(d['data_root']).is_absolute(),'data_root должен быть абсолютным')
  need(not inside(self.home,self.data_root) and not inside(self.data_root,self.home),'install_root и data_root не должны пересекаться')
  self.active=d['active_workspace'];spaces=d['workspaces'];need(isinstance(spaces,dict) and self.active in spaces,'active_workspace не найден')
  need(d.get('ai',{}).get('mode')=='manual_chatgpt','Поддерживается только AI mode manual_chatgpt')
  need(d['asr']['model']=='large-v3','v1.7 поддерживает только large-v3; автоматическая смена модели запрещена')
  from asr_device import configured_mode
  try:self.device_mode=configured_mode(d['asr'])
  except ValueError as e:raise ConfigError(str(e)) from e
  self._asr_selection=None
  for language in d['languages'].values():need(language in ('zh','en','auto'),'Язык: zh, en или auto')
  for field in ('lecture','dialogue'):need(field in d['languages'],'Отсутствует default language: '+field)
  states=set();homes=set();subject_roots=[];output_roots=[]
  for key,w in spaces.items():
   need(re.fullmatch(r'[a-zA-Z0-9_-]+',key) is not None,'Недопустимый workspace id')
   wr=child(self.data_root,w['folder']);need(isinstance(w['subjects'],list),'subjects должен быть списком')
   for field in ('lecture_state','ai_state'):
    p=child(wr,w[field]);need(p not in states,'Конфликт state между workspaces');states.add(p)
   home=child(self.home,w.get('worker_home','runtime/workspaces/'+key));need(home not in homes,'У workspaces должен быть отдельный worker_home');homes.add(home)
   codes=set()
   for s in w['subjects']:
    code=s['subject_code'];need(isinstance(code,str) and re.fullmatch(r'[A-Za-z0-9_-]+',code) is not None and code not in codes,'Повтор/недопустимый subject_code');codes.add(code)
    need(isinstance(s['subject_name'],str) and bool(s['subject_name'].strip()),'Пустое имя предмета');need(type(s['enabled']) is bool,'enabled должен быть boolean')
    need(s.get('default_language',d['languages']['lecture']) in ('zh','en','auto'),'Недопустимый язык предмета')
    sr=child(wr,s['folder']);need(all(not inside(sr,x) and not inside(x,sr) for x in subject_roots),'Предметы не должны пересекаться');subject_roots.append(sr)
    paths=[child(sr,s['paths'][f]) for f in ('audio','raw','ready')]
    need(all(not inside(a,b) and not inside(b,a) for i,a in enumerate(paths) for b in paths[i+1:]),'Папки audio/raw/ready пересекаются');output_roots+=paths
  self.workspace=spaces[self.active];self.workspace_root=child(self.data_root,self.workspace['folder'])
  self.worker_home=child(self.home,self.workspace.get('worker_home','runtime/workspaces/'+self.active))
  self.dialogue_root=child(self.data_root,d['dialogue']['folder']);self.dialogue_home=self.local(d['dialogue'].get('runtime','dialogue_runtime'))
  need(all(not inside(self.dialogue_root,x) and not inside(x,self.dialogue_root) for x in subject_roots),'Dialogue пересекается с предметами')
  need(self.dialogue_home not in homes,'Dialogue и Lecture runtime совпадают')
  self.queue_home=self.local(d.get('ai',{}).get('queue_runtime','ai_queue'))
  need(self.queue_home not in homes and self.queue_home!=self.dialogue_home,'AI queue runtime пересекается с worker runtime')
  self.state=child(self.workspace_root,self.workspace['lecture_state']);self.ai_state=child(self.workspace_root,self.workspace['ai_state'])
  self.dictionary=child(self.data_root,d['dictionary']['book'])
  need(self.dictionary not in states and all(not inside(p,x) for p in states|{self.dictionary} for x in output_roots),'Служебные данные пересекаются с аудио/результатами')
 def local(self,value):return child(self.home,value)
 def runtime(self,key,default):
  value=self.data.get('runtimes',{}).get(key,default);p=Path(value).expanduser();return p.resolve() if p.is_absolute() else self.local(value)
 def assert_current(self):need(self.path.read_bytes()==self.bytes,'Config изменён: остановите и перезапустите workers; горячее переключение workspace запрещено')
 def subjects(self):
  out={}
  for s in self.workspace['subjects']:
   if not s['enabled']:continue
   root=child(self.workspace_root,s['folder']);paths=s['paths']
   out[s['subject_code']]=dict(title=s['subject_name'],subject_name=s['subject_name'],subject_dir=root,notes_dir=child(root,paths.get('notes','.')),audio_dir=child(root,paths['audio']),raw_dir=child(root,paths['raw']),ready_dir=child(root,paths['ready']),default_language=s.get('default_language',self.data['languages']['lecture']),prompt=s.get('asr_context',{}).get('prompt',''),hotwords=s.get('asr_context',{}).get('hotwords',''))
  return out
 def layout(self):
  self.assert_current();need(self.data_root.is_dir(),'Data root недоступен: '+str(self.data_root));need(self.workspace_root.is_dir(),'Workspace недоступен: '+str(self.workspace_root))
  subjects=self.subjects()
  for code,s in subjects.items():
   for field in ('subject_dir','audio_dir','raw_dir','ready_dir'):need(s[field].is_dir(),f'Предмет {code}: не найдена {field}: {s[field]}')
  need(self.state.is_file(),'Lecture state недоступен; автоматический сброс запрещён: '+str(self.state))
  return self.state,(self.local('logs/lecture/pipeline.log') if 'application_home' in self.data else self.state.parent/'pipeline.log'),subjects
 def dialogue(self):return dict(version='1.6',root=str(self.dialogue_root),home=str(self.dialogue_home),asr_home=str(self.install),lecture_home=str(self.worker_home),document_python=str(self.runtime('document_python','.venv/Scripts/python.exe')),default_language=self.data['languages']['dialogue'],stable_seconds=120,hash_interval=15,poll_seconds=10,retry_seconds=300,max_attempts=3)
 def task_names(self):
  prefix=self.data.get('task_prefix')
  if prefix is None:return {'lecture':'LecturePipelineWorker','dialogue':'LecturePipelineDialogueWorker'}
  need(re.fullmatch(r'LP-[a-f0-9]{12}',prefix) is not None,'Invalid isolated task prefix')
  return {'lecture':prefix+'-Lecture','dialogue':prefix+'-Dialogue'}
 def model_cache(self):return self.runtime('model_cache',str(Path.home()/'.cache'/'huggingface'/'hub'))
 def model_snapshot(self):
  root=self.model_cache()/'models--Systran--faster-whisper-large-v3';ref=root/'refs'/'main'
  if ref.is_file():p=root/'snapshots'/ref.read_text().strip()
  else:
   candidates=[p for p in (root/'snapshots').glob('*') if (p/'model.bin').is_file()];need(len(candidates)==1,'Модель large-v3 отсутствует или кэш неоднозначен');p=candidates[0]
  for name in ('model.bin','config.json','tokenizer.json','preprocessor_config.json'):need((p/name).is_file(),'Не найден файл модели '+str(p/name))
  return p
 def asr_selection(self):
  from asr_device import detect,select
  self.assert_current()
  if self._asr_selection is None:
   report=detect(self.home,self.runtime('asr_python','.venv/Scripts/python.exe'),self.model_cache(),self.runtime('cuda','cuda_runtime/v1.3'),self.device_mode)
   self._asr_selection=select(self.device_mode,report)
  return dict(self._asr_selection)
 def new_model(self,*args,**kwargs):
  from lecture_asr import ProductionWhisperModel
  self.assert_current();self.model_snapshot();os.environ['HF_HUB_CACHE']=str(self.model_cache())
  selected=self.asr_selection()
  kwargs.update(device=selected['device'],compute_type=selected['compute_type'],allow_cpu_fallback=selected['allow_cpu_fallback'],runtime_dir=self.runtime('cuda','cuda_runtime/v1.3'))
  return ProductionWhisperModel(*args,**kwargs)

def preflight(config=None,probe_gpu=True):
 checks=[]
 def check(name,fn):
  try:value=fn();checks.append(dict(id=name,status='ok',message=str(value or 'Доступно')))
  except Exception as e:checks.append(dict(id=name,status='error',message=str(e)))
 try:c=config or Config()
 except Exception as e:return dict(schema_version=1,version=VERSION,ok=False,checks=[dict(id='config',status='error',message=str(e))])
 def layout_status():
  _,_,subjects=c.layout();return c.workspace['name']+': '+str(len(subjects))+' enabled subjects'
 check('config',lambda:c.assert_current());check('workspace',layout_status)
 def state(p,field):
  value=read(p);need(isinstance(value.get(field),dict),'Неверная схема '+str(p));return str(p)
 check('lecture_state',lambda:state(c.state,'lectures'));check('ai_state',lambda:state(c.ai_state,'processed'));check('dialogue_state',lambda:state(c.dialogue_home/'dialogue_state.json','jobs'))
 def file(p):need(p.is_file(),'Файл недоступен: '+str(p));return str(p)
 check('dictionary',lambda:file(c.dictionary));check('word_ai',lambda:file(c.install/'word_ai_v1.5'/'lecture_ai.py'));check('model',c.model_snapshot)
 def document_runtime():
  r=subprocess.run([str(c.runtime('document_python','.venv/Scripts/python.exe')),'-B','-c','import docx; print(docx.__version__)'],capture_output=True,text=True,timeout=30,creationflags=0x08000000 if os.name=='nt' else 0)
  need(r.returncode==0,'Word Python / python-docx недоступен: '+r.stderr[-500:]);return r.stdout.strip()
 check('document_runtime',document_runtime)
 for name,path in [('asr_python',c.runtime('asr_python','.venv/Scripts/python.exe')),('document_python',c.runtime('document_python','.venv/Scripts/python.exe'))]:check(name,lambda p=path:file(p))
 def dialogue():
  for name in ('00 — Входящие аудио','01 — Расшифровки','02 — Word','99 — Служебное'):need((c.dialogue_root/name).is_dir(),'Dialogue folder недоступна: '+name)
 check('dialogue_root',dialogue)
 if probe_gpu:
  try:
   selected=c.asr_selection();gpu=selected['device']=='cuda'
   checks.append(dict(id='asr_backend',status='warning' if selected['reason'] else 'ok',message=c.device_mode.upper()+' → '+('GPU' if gpu else 'CPU')+(': '+selected['reason'] if selected['reason'] else ''),cpu_fallback=selected['allow_cpu_fallback'],gpu_available=gpu))
  except Exception as e:checks.append(dict(id='asr_backend',status='error',message=str(e)))
 return dict(schema_version=1,version=VERSION,workspace=c.active,ok=all(x['status']!='error' for x in checks),checks=checks)
def require_preflight(c):
 result=preflight(c)
 if not result['ok']:raise ConfigError('; '.join(x['id']+': '+x['message'] for x in result['checks'] if x['status']=='error'))
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--resolve',action='store_true');a=p.parse_args()
 if a.resolve:
  c=Config(a.config);print(json.dumps(dict(install_root=str(c.install),worker_home=str(c.worker_home),asr_python=str(c.runtime('asr_python','.venv/Scripts/python.exe')),document_python=str(c.runtime('document_python','.venv/Scripts/python.exe')),dictionary=str(c.dictionary),dialogue=c.dialogue(),tasks=c.task_names(),application_home=str(c.home)),ensure_ascii=False));return
 result=preflight(Config(a.config)) if a.config else preflight();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['ok'] else 2)
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps(dict(ok=False,error='Configuration error: '+str(e)),ensure_ascii=False));raise SystemExit(2)
