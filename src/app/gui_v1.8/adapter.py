"""GUI projections and control transactions; never transcribes or writes pipeline ledgers."""
from __future__ import annotations
import base64,copy,json,os,statistics,subprocess,time,uuid,shutil,hashlib
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
from pipeline_config import Config,ConfigError,preflight,read,inside
from ai_queue import load_queue,select

TEST_TASKS={'2026-2027-s1/05/990_2026-09-25'}
TASKS={'lecture':'LecturePipelineWorker','dialogue':'LecturePipelineDialogueWorker'}
SCRIPTS={'lecture':'WorkerControl.ps1','dialogue':'DialogueControl.ps1'}
NO_WINDOW=0x08000000 if os.name=='nt' else 0

def atomic_bytes(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  try:tmp.unlink(missing_ok=True)
  except OSError:pass # Preserve the original error; never remove another writer's temp file.

def atomic(path,value):atomic_bytes(path,json.dumps(value,ensure_ascii=False,indent=2).encode())

def age(stamp,now=None):
 try:return max(0,((now or datetime.now(timezone.utc))-datetime.fromisoformat(stamp)).total_seconds())
 except (ValueError,TypeError):return None

def duration(seconds):
 if seconds is None:return 'нет данных'
 return f'{max(0,round(seconds))//60} мин {max(0,round(seconds))%60:02d} с'

def heartbeat(data):
 a=age(data.get('heartbeat'))
 if a is None:return 'Нет heartbeat'
 if a>180:return 'Нет связи (>3 мин)'
 return 'Работает' if data.get('worker')=='RUNNING' else str(data.get('worker','Неизвестно'))

def eta(audio_seconds,elapsed,history):
 """Conservative range only with >=3 comparable measured RTFs and known duration."""
 valid=[x for x in history if isinstance(x,(int,float)) and 0<x<100]
 if not audio_seconds or elapsed is None or len(valid)<3:return 'ETA: недостаточно измерений'
 estimate=audio_seconds*statistics.median(valid)-elapsed
 if estimate<=0:return 'ETA: прежняя оценка превышена'
 lo=max(1,int(estimate*.7/60));hi=max(lo+1,int(estimate*1.5/60)+1)
 return f'ETA ≈ {lo}–{hi} мин (оценка)'

def backend_text(result,preferred='gpu'):
 row=next((x for x in (result or {}).get('checks',[]) if x['id']=='asr_backend'),None)
 if not row:return 'GPU/CPU: проверка ещё не выполнена'
 if row['status']=='error':return 'ASR: ошибка preflight — '+row['message']
 if preferred=='cpu':return 'CPU выбран в конфигурации'
 return row['message']

def safe_open(c,path,opener=None):
 if not path:raise ValueError('Для этой записи путь отсутствует')
 p=Path(path).resolve()
 if not any(inside(p,r) for r in (c.data_root,c.home)):raise ValueError('Путь вне корней pipeline')
 if not p.exists():raise FileNotFoundError('Путь недоступен: '+str(p))
 if p.is_file() and p.suffix.lower() not in {'.docx','.txt','.srt','.json','.log','.md'}:raise ValueError('Этот тип файла нельзя открыть из GUI')
 (opener or os.startfile)(str(p))

def snapshot(config_path,show_tests=False):
 c=Config(config_path);errors=[]
 def load(path,default):
  try:return read(path)
  except Exception as e:errors.append(str(path)+': '+str(e));return default
 try:c.layout()
 except Exception as e:errors.append(str(e))
 ls=load(c.worker_home/'worker_status.json',{});ds=load(c.dialogue_home/'status.json',{})
 state=load(c.state,{'lectures':{}});ai=load(c.ai_state,{'processed':{}})
 dialogue=load(c.dialogue_home/'dialogue_state.json',{'jobs':{}})
 try:q=load_queue(c)
 except Exception as e:errors.append('AI queue: '+str(e));q={'tasks':{}}
 subjects=c.subjects();records=ai.get('processed',{}).values();lectures=[];hidden=0
 tasks={t['subject_code']+'/'+t['lecture_key']:t for t in q['tasks'].values() if t['workspace']==c.active}
 keys=set(tasks)|set(state.get('lectures',{}))|set(ls.get('lectures',{}))
 for key in sorted(keys,reverse=True):
  if '/' not in key:errors.append('Некорректный lecture key: '+key);continue
  code,lecture=key.split('/',1);test=c.active+'/'+key in c.data.get('hidden_tasks',TEST_TASKS)
  if test and not show_tests:hidden+=1;continue
  t=tasks.get(key,{});worker=ls.get('lectures',{}).get(key,{});s=subjects.get(code,{})
  matching=[r for r in records if r.get('subject_code')==code and r.get('lecture_id')==lecture]
  words=set()
  for r in matching:
   if r.get('output_docx_local_path'):words.add(r['output_docx_local_path'])
   elif r.get('output_docx_name') and s.get('ready_dir'):words.add(str(s['ready_dir']/r['output_docx_name']))
  error=t.get('error') or state.get('lectures',{}).get(key,{}).get('error') or ''
  if len(words)>1:error+=' Несколько Word результатов: выберите файл в папке.'
  status=worker.get('status',state.get('lectures',{}).get(key,{}).get('status','waiting'))
  elapsed=age(worker.get('updated_at')) if status=='TRANSCRIBING' else None
  manifest=t.get('manifest');folder=str(Path(manifest).parent) if manifest else str(s.get('raw_dir',''))
  row=dict(id=key,name=lecture,subject=code+' · '+s.get('title',t.get('subject_name','')),date=t.get('lecture_date',lecture.split('_',1)[-1]),status=status,ai=t.get('status','—'),test=test,
   word=next(iter(words)) if len(words)==1 else None,folder=folder,txt=t.get('raw'),srt=t.get('srt',[]),packet=str(Path(t['source_packet']).parent) if t.get('source_packet') else None,
   detail=error or worker.get('detail',''),elapsed=duration(elapsed) if elapsed is not None else '—',eta='ETA: нет измерений текущей задачи',part='Часть: worker не публикует счётчик')
  if t.get('status')=='completed':
   receipt=c.queue_home/'finalize'/hashlib.sha256((c.active+'/'+key).encode()).hexdigest()[:24]/'result.json'
   if receipt.exists():
    try:
     report=read(receipt).get('dictionary',{});row['detail']+='\nСловарь: +'+str(report.get('added',0))+' / обновлено '+str(report.get('updated',0))
    except (OSError,ValueError):pass
  lectures.append(row)
 lectures.sort(key=lambda r:(r['date'],r['name']),reverse=True)
 rows=[];known=set()
 for j in sorted(dialogue.get('jobs',{}).values(),key=lambda x:x.get('created_at',''),reverse=True):
  name=j.get('source_name','');known.add(name);out=j.get('output_name');raw=c.dialogue_root/'01 — Расшифровки'/out if out else None
  rows.append(dict(id=j.get('id',name),name=name,status=j.get('status','?'),language=j.get('detected_language',j.get('language','auto')),duration=duration(j.get('asr',{}).get('info',{}).get('duration')),timing=duration(j.get('elapsed_asr_seconds')),detail=j.get('error') or ds.get('files',{}).get(name,''),word=str(c.dialogue_root/'02 — Word'/(out+'.docx')) if out and j.get('status')=='completed' else None,folder=str(raw) if raw else str(c.dialogue_root),txt=str(raw/'transcript.txt') if raw and j.get('status')=='completed' else None,srt=[str(raw/'transcript.srt')] if raw and j.get('status')=='completed' else [],eta='ETA: недостаточно измерений'))
 for name,status in ds.get('files',{}).items():
  if name not in known:rows.append(dict(id='incoming:'+name,name=name,status='waiting / stability',language=c.data['languages']['dialogue'],duration='—',timing='—',detail=status,folder=str(c.dialogue_root/'00 — Входящие аудио'),srt=[]))
 # New drops may not yet have reached the worker's next poll.
 incoming=c.dialogue_root/'00 — Входящие аудио'
 try:
  for p in incoming.iterdir():
   if p.is_file() and p.suffix.lower() in {'.m4a','.mp3','.wav','.aac','.flac','.mp4','.mov','.ogg','.opus','.wma'} and p.name not in known and p.name not in ds.get('files',{}):
    rows.append(dict(id='drop:'+p.name,name=p.name,status='waiting',language=c.data['languages']['dialogue'],duration='—',timing='—',detail='Ожидается проверка стабильности worker; GUI не запускает ASR.',folder=str(incoming),srt=[]))
 except OSError as e:errors.append(str(e))
 active=[r for r in lectures if r['status'] not in ('DONE','completed','done')]
 current='Нет активной локальной обработки'
 if active:current='\n'.join(r['subject']+' / '+r['name']+' · '+r['status']+' · '+r['detail']+'\nПрошло: '+r['elapsed']+' · '+r['eta']+' · '+r['part'] for r in active)
 if ds.get('active'):current+='\nDialogue: '+ds['active']+' · '+ds.get('files',{}).get(ds['active'],'processing')+' · ETA: недостаточно данных'
 progress=None;asr_active=any(r['status']=='TRANSCRIBING' for r in lectures)
 if asr_active:
  try:
   from human_ux import progress_view
   v=read(c.worker_home/'asr_progress.json')
   if time.time()-v['updated_at']<10 and any(r['id']==v['identity'] and r['status']=='TRANSCRIBING' for r in lectures):
    result=progress_view(v);progress=result['progress'];phase={'cuda_setup':'Подготовка GPU','model_load':'Загрузка модели','transcribe':'Распознавание','asr_complete':'TXT/SRT: подготовка'}.get(v['phase'],v['phase'])
    current=f"{v['identity']} · {phase} · часть {v.get('part','?')}/{v.get('parts','?')}\n{v['backend']} · {v['model']} · {v['language']}\nОбработано: {duration(v['processed_audio_sec'])} / {duration(v['audio_duration_sec'])}\nПрошло: {duration(v['elapsed_sec'])} · Осталось: "+('≈ '+duration(result['eta'])+' (оценка)' if result['eta'] is not None else 'рассчитывается…')
  except (OSError,ValueError,KeyError):pass
 return dict(progress=progress,asr_active=asr_active,config=c,lectures=lectures,dialogues=rows,lecture_worker=heartbeat(ls),dialogue_worker=heartbeat(ds),lecture_status=ls,dialogue_status=ds,errors=errors,hidden=hidden,current=current,queue=q)

class Controls:
 def __init__(self,c):
  self.c=c
  self.tasks=c.task_names()
  if c.path.resolve()!=Path(os.environ.get('LECTURE_CONFIG',str(c.install/'config.json'))).resolve():raise ConfigError('Управление Windows workers разрешено только для install_root/config.json; тесты используют изолированный контроллер')
 def ps(self,code,extra=None):
  env=dict(os.environ,LECTURE_CONFIG=str(self.c.path));env.update(extra or {})
  r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',"$ErrorActionPreference='Stop'; "+code],env=env,capture_output=True,encoding='utf-8',errors='replace',creationflags=NO_WINDOW,timeout=100)
  if r.returncode:raise RuntimeError(r.stderr.strip() or r.stdout.strip() or 'Ошибка контроллера')
  return r.stdout.strip()
 def states(self):
  s=self.ps("[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); ($env:GUI_TASKS | ConvertFrom-Json) | ForEach-Object { $t=Get-ScheduledTask -TaskName $_; [pscustomobject]@{name=$_.ToString();running=($t.State -eq 'Running');enabled=$t.Settings.Enabled} } | ConvertTo-Json -Compress",{'GUI_TASKS':json.dumps(list(self.tasks.values()))})
  rows=json.loads(s);return {k:next(x for x in rows if x['name']==name) for k,name in self.tasks.items()}
 def action(self,kind,action):
  if kind not in TASKS or action not in ('Stop','Start'):raise ValueError('Неверное действие')
  self.ps("& $env:GUI_CONTROL -Action $env:GUI_ACTION; if($LASTEXITCODE -and $LASTEXITCODE -ne 0){throw 'Controller failed'}",{'GUI_CONTROL':str(self.c.install/SCRIPTS[kind]),'GUI_ACTION':action})
  if action=='Start':
   if not hasattr(self,'starts'):self.starts={}
   self.starts[kind]=datetime.now(timezone.utc)
 def wait_stopped(self,kinds,timeout=65):
  end=time.monotonic()+timeout
  while True:
   if not any(self.states()[k]['running'] for k in kinds):return
   if time.monotonic()>end:raise TimeoutError('Worker занят. Конфигурация не переключена; дождитесь окончания задачи.')
   time.sleep(1)
 def restore(self,previous):
  for k,s in previous.items():
   if s['running']:self.action(k,'Start')
   elif s['enabled']:self.ps('Enable-ScheduledTask -TaskName $env:GUI_TASK | Out-Null',{'GUI_TASK':self.tasks[k]})
 def confirm_started(self,previous):
  end=time.monotonic()+45
  required=[k for k,v in previous.items() if v['running']]
  while required:
   states=self.states();c=Config(self.c.path)
   paths={'lecture':c.worker_home/'worker_status.json','dialogue':c.dialogue_home/'status.json'}
   good=True
   for k in required:
    try:
     r=read(paths[k]);started=datetime.fromisoformat(r['started_at']);requested=getattr(self,'starts',{}).get(k,datetime.now(timezone.utc))
     good=good and states[k]['running'] and heartbeat(r)=='Работает' and (requested-started).total_seconds()<3
    except Exception:good=False
   if good:return
   if time.monotonic()>end:raise RuntimeError('Новый worker не подтвердил запуск; выполняется откат')
   time.sleep(1)

@contextmanager
def transaction_lock(home):
 home.mkdir(parents=True,exist_ok=True)
 with (home/'control.lock').open('a+b') as f:
  if os.name=='nt':
   import msvcrt
   if f.tell()==0:f.write(b'0');f.flush()
   f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  yield

class Manager:
 def __init__(self,path,controls=Controls,check=preflight):
  self.path=Path(path);self.controls=controls;self.check=check
 @property
 def journal(self):return Config(self.path).local('run/gui')/'workspace-transaction.json'
 def pending(self):
  p=self.journal
  return read(p) if p.exists() and read(p).get('phase') not in ('committed','rolled_back') else None
 def recover(self):
  c=Config(self.path)
  with transaction_lock(c.local('run/gui')):
   j=self.pending()
   if not j:return
   self._rollback(j)
 def _rollback(self,j):
  old=base64.b64decode(j['old']);new=base64.b64decode(j['new']);now=self.path.read_bytes()
  if now not in (old,new):raise RuntimeError('Config изменён вне GUI. Автоматический откат запрещён; сохранён журнал для ручной проверки.')
  ctl=self.controls(Config(self.path))
  if now!=old:
   for k in TASKS:ctl.action(k,'Stop')
   ctl.wait_stopped(list(TASKS));atomic_bytes(self.path,old)
  ctl=self.controls(Config(self.path));ctl.restore(j['workers'])
  if now!=old:ctl.confirm_started(j['workers'])
  j['phase']='rolled_back';atomic(self.journal,j)
 def switch(self,target):
  c=Config(self.path)
  if target==c.active:return 'Workspace уже активен'
  if target not in c.data['workspaces']:raise ConfigError('Workspace не настроен')
  data=copy.deepcopy(c.data);data['active_workspace']=target
  return self.apply_config(data)
 def apply_config(self,data):
  c=Config(self.path);target=data['active_workspace']
  with transaction_lock(c.local('run/gui')):
   if self.pending():raise RuntimeError('Сначала восстановите незавершённое переключение')
   if shutil.disk_usage(c.path.parent).free<1024*1024:raise OSError('Недостаточно места для безопасной транзакции config (нужен минимум 1 MiB)')
   new=json.dumps(data,ensure_ascii=False,indent=2).encode();probe=c.path.with_name('.gui-preflight-'+uuid.uuid4().hex+'.json')
   # Same parent preserves relative install_root. This is not the live config.
   atomic_bytes(probe,new)
   try:
    result=self.check(Config(probe))
    if not result['ok']:raise ConfigError('; '.join(x['message'] for x in result['checks'] if x['status']=='error'))
   finally:probe.unlink(missing_ok=True)
   ctl=self.controls(c);previous=ctl.states()
   j=dict(phase='stopping',old=base64.b64encode(c.bytes).decode(),new=base64.b64encode(new).decode(),workers=previous,target=target)
   atomic(self.journal,j)
   try:
    for k in TASKS:ctl.action(k,'Stop')
    ctl.wait_stopped(list(TASKS));c.assert_current()
    atomic_bytes(c.path,new);j['phase']='checking';atomic(self.journal,j)
    result=self.check(Config(c.path))
    if not result['ok']:raise ConfigError('Preflight нового workspace не прошёл')
    ctl=self.controls(Config(c.path));ctl.restore(previous);ctl.confirm_started(previous)
    j['phase']='committed';atomic(self.journal,j)
    return 'Workspace переключён; прежнее состояние запуска workers восстановлено'
   except Exception as e:
    j['error']=str(e)
    # Logging failure must not skip recovery of the live config/workers.
    try:atomic(self.journal,j)
    except OSError:pass
    try:self._rollback(j)
    except Exception as rollback:raise RuntimeError(f'{e}. Откат требует внимания: {rollback}') from e
    raise RuntimeError(str(e)+'; исходный config восстановлен') from e
 def restart(self,kind):
  c=Config(self.path)
  with transaction_lock(c.local('run/gui')):
   if self.pending():raise RuntimeError('Сначала восстановите переключение workspace')
   result=self.check(c)
   if not result['ok']:raise ConfigError('Preflight не прошёл; запуск запрещён')
   ctl=self.controls(c);before=ctl.states();ctl.action(kind,'Stop')
   try:ctl.wait_stopped([kind])
   except Exception:ctl.restore({kind:before[kind]});raise
   ctl.action(kind,'Start');ctl.confirm_started({kind:{'running':True}})
   return kind+' worker перезапущен'

