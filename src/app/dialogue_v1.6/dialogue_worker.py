"""Isolated drop-folder worker. Reuses unchanged lecture_asr v1.3 as a library."""
from __future__ import annotations
import argparse,hashlib,json,logging,os,re,shutil,subprocess,sys,threading,time,uuid
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
EXT={'.m4a','.mp3','.wav','.aac','.flac','.mp4','.mov','.ogg','.opus','.wma'}
DIRS=('00 — Входящие аудио','01 — Расшифровки','02 — Word','99 — Служебное')
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 with t.open('w',encoding='utf8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
 os.replace(t,p)
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def metadata(p):
 s=p.stat();return [s.st_size,s.st_mtime_ns]
def stamp(t,sep=','):
 n=round(t*1000);return f'{n//3600000:02d}:{n//60000%60:02d}:{n//1000%60:02d}{sep}{n%1000:03d}'
def basename(name):
 s=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',Path(name).stem).strip(' .')[:60] or 'разговор'
 if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]',s,re.I):s='_'+s
 return s
@contextmanager
def single_instance(home):
 p=Path(home)/'dialogue.lock';p.parent.mkdir(parents=True,exist_ok=True);f=p.open('a+b')
 try:
  if os.name=='nt':
   import msvcrt
   if f.tell()==0:f.write(b'0');f.flush()
   f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  else:
   import fcntl
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  yield
 finally:f.close()
class Changed(Exception):pass
class Worker:
 def __init__(self,config,asr=None,word=None,clock=time.monotonic):
  self.cfg=config;self.root=Path(config['root']);self.home=Path(config['home']);self.home.mkdir(parents=True,exist_ok=True)
  self.statefile=self.home/'dialogue_state.json';self.clock=clock;self.obs={};self.asr=asr;self.word=word;self.rows={};self.active=None
  self.mu=threading.RLock();self.status_mu=threading.Lock();self.started=now()
  if self.statefile.exists():
   self.state_bytes=self.statefile.read_bytes();self.state=json.loads(self.state_bytes.decode('utf-8-sig'))
   if self.state.get('schema_version')!=1 or not isinstance(self.state.get('jobs'),dict):raise ValueError('Invalid dialogue state; restore backup, do not requeue')
  elif (self.home/'initialized').exists():raise ValueError('Dialogue state missing; restore it before starting')
  else:
   self.state_bytes=None;self.state=dict(schema_version=1,mode='dialogue',jobs={});self.save();(self.home/'initialized').write_text('1',encoding='ascii')
 def check_state(self):
  if self.state_bytes is not None:
   if not self.statefile.is_file() or self.statefile.read_bytes()!=self.state_bytes:raise ValueError('Dialogue state изменён или исчез во время работы; остановите worker и восстановите/проверьте state перед перезапуском')
 def save(self):
  self.check_state()
  if self.statefile.exists():
   # Parse before rotating; never back up a corrupt ledger over the last good copy.
   load(self.statefile);shutil.copy2(self.statefile,self.home/'dialogue_state.previous.json')
  # write() uses text mode's platform newline conversion.
  encoded=json.dumps(self.state,ensure_ascii=False,indent=2,allow_nan=False).replace('\n',os.linesep).encode('utf8')
  write(self.statefile,self.state);self.state_bytes=encoded
 def journal(self,event,**data):
  with (self.home/'journal.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(at=now(),event=event,**data),ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 def layout(self):
  if not self.root.is_dir():raise OSError('Dialogue root unavailable: '+str(self.root))
  for name in DIRS:
   if not (self.root/name).is_dir():raise OSError('Dialogue folder unavailable: '+name)
 def status(self):
  with self.status_mu:self._status()
 def _status(self):
  with self.mu:data=dict(version='1.6',worker='RUNNING',started_at=self.started,heartbeat=now(),active=self.active,files=dict(self.rows))
  write(self.home/'status.json',data)
  try:
   self.layout();svc=self.root/DIRS[3];write(svc/'status.json',data)
   # Only copy a committed atomic snapshot, not an object concurrently being changed.
   state=load(self.statefile);write(svc/'dialogue_state.json',state)
   tmp=svc/'journal.pending';shutil.copy2(self.home/'journal.jsonl',tmp) if (self.home/'journal.jsonl').exists() else tmp.write_text('',encoding='utf8');os.replace(tmp,svc/'journal.jsonl')
   lines=['Dialogue Quick 1.6',data['heartbeat'],'Работает в фоне. Обычный файл: язык auto.']+[f'{k}: {v}' for k,v in data['files'].items()]
   tmp=svc/'STATUS.pending';tmp.write_text('\n'.join(lines),encoding='utf8');os.replace(tmp,svc/'STATUS.txt')
  except OSError:logging.warning('Drive status temporarily unavailable')
 def say(self,name,status):
  with self.mu:self.rows[name]=status
 def language(self,name):
  p=self.root/DIRS[3]/'task_options.json';o=load(p) if p.exists() else {}
  lang=o.get('files',{}).get(name,{}).get('language',self.cfg.get('default_language',o.get('default_language','auto')))
  if lang not in ('auto','zh','en'):raise ValueError('Language must be auto, zh or en')
  return lang
 def stable(self,p):
  t=self.clock();meta=metadata(p);o=self.obs.get(p.name)
  if not o or o['meta']!=meta:
   self.obs[p.name]=dict(meta=meta,since=t,hash=None,hash_at=0);return None
  if meta[0]<=0 or t-o['since']<self.cfg.get('stable_seconds',120):return None
  if t-o['hash_at']<self.cfg.get('hash_interval',15):return None
  h=digest(p)
  if metadata(p)!=meta:self.obs.pop(p.name,None);return None
  if o['hash']!=h:
   if o['hash'] is not None:o['since']=t
   o.update(hash=h,hash_at=t);return None
  o['hash_at']=t;return h,meta
 def busy_lecture(self):
  p=Path(self.cfg.get('lecture_home',self.cfg['asr_home']))/'worker_status.json'
  try:return any(v.get('status') in ('TRANSCRIBING','COPYING','PUBLISHING') for v in load(p).get('lectures',{}).values())
  except (OSError,ValueError):return False
 def recognize(self,p,language):
  if self.asr:return self.asr(p,language)
  sys.path.insert(0,self.cfg['asr_home']);from lecture_asr import ProductionWhisperModel,bounded_segments
  if not hasattr(self,'model'):
   if self.cfg.get('central_config'):
    from pipeline_config import Config
    self.model=Config(self.cfg['central_config']).new_model()
   else:self.model=ProductionWhisperModel()
  started=time.monotonic();segments,info=self.model.transcribe(p,language=None if language=='auto' else language)
  rows=[dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,no_speech_prob=s.no_speech_prob) for s in segments]
  bounded=bounded_segments([(s['start'],s['end'],s['text']) for s in rows],info.duration)
  # Timestamp bounding can merge a late tail. Retain conservative confidence for that case.
  result=[dict(start=x,end=y,text=text,avg_logprob=min((s['avg_logprob'] for s in rows if s['end']>=x and s['start']<=y),default=-1.1),no_speech_prob=max((s['no_speech_prob'] for s in rows if s['end']>=x and s['start']<=y),default=0)) for x,y,text in bounded]
  return dict(segments=result,detected_language=info.language,duration=info.duration,asr=self.model.last_run,elapsed_asr_seconds=time.monotonic()-started)
 def build_word(self,request,output):
  if self.word:return self.word(request,output)
  result=subprocess.run([self.cfg['document_python'],'-B','-X','utf8',str(Path(__file__).with_name('dialogue_word.py')),str(request),str(output)],capture_output=True,text=True,encoding='utf8',timeout=180,creationflags=0x08000000 if os.name=='nt' else 0)
  if result.returncode:raise RuntimeError('Word build failed: '+result.stderr[-2000:])
  return json.loads(result.stdout)
 def paths(self,j):return self.root/DIRS[1]/j['output_name'],self.root/DIRS[2]/(j['output_name']+'.docx')
 def choose_name(self,name,key):
  base=basename(name);candidate=base
  used={j['output_name'].casefold() for j in self.state['jobs'].values()}
  for attempt in range(100):
   if candidate.casefold() not in used and not (self.root/DIRS[1]/candidate).exists() and not (self.root/DIRS[2]/(candidate+'.docx')).exists():return candidate
   candidate=base+'__'+key[:12]+('' if attempt==0 else '_'+str(attempt))
  raise ValueError('Output name collision')
 def complete(self,j,spool):
  self.check_state()
  raw,word=self.paths(j);stage=spool/'outputs'
  expected=j['output_hashes']
  # Recover crash between publication steps from fully built local artifacts. Never overwrite conflicting files.
  targets={'transcript.txt':raw/'transcript.txt','transcript.srt':raw/'transcript.srt','dialogue.docx':word}
  for name,p in targets.items():
   if p.exists() and digest(p)!=expected[name]:raise ValueError('Output conflict; retained for manual review: '+str(p))
  pending_raw=raw.with_name('.'+raw.name+'.'+j['id'][:12]+'.pending');pending_word=word.with_name('.'+word.name+'.'+j['id'][:12]+'.pending')
  if not raw.exists():
   pending_raw.mkdir(exist_ok=True)
   for name in ('transcript.txt','transcript.srt'):shutil.copy2(stage/name,pending_raw/name)
   os.rename(pending_raw,raw)
  else:
   for name in ('transcript.txt','transcript.srt'):
    if not (raw/name).exists():raise ValueError('Incomplete foreign transcript directory')
  if not word.exists():shutil.copy2(stage/'dialogue.docx',pending_word);os.rename(pending_word,word)
  if any(digest(p)!=expected[name] for name,p in targets.items()):raise IOError('Output verification failed')
  j.update(status='completed',completed_at=now(),error=None);self.save();self.journal('completed',job=j['id'],source=j['source_name'],outputs=[str(p) for p in targets.values()])
 def process(self,p,h,meta,language):
  self.check_state()
  key=hashlib.sha256((h+'\0'+language).encode()).hexdigest();j=self.state['jobs'].get(key)
  if j and j['status']=='completed':
   raw,word=self.paths(j)
   good=all(x.is_file() and digest(x)==j['output_hashes'][name] for name,x in [('transcript.txt',raw/'transcript.txt'),('transcript.srt',raw/'transcript.srt'),('dialogue.docx',word)])
   self.say(p.name,'ЗАВЕРШЕНО → '+j['output_name'] if good else 'Результат изменён/удалён; ASR повторно не запускается');return
  if j and j.get('retry_at',0)>time.time():self.say(p.name,'Ошибка; ожидается повтор: '+str(j.get('error')));return
  if j and j.get('attempts',0)>=self.cfg.get('max_attempts',3):self.say(p.name,'ОШИБКА — нужен retry: '+str(j.get('error')));return
  if not j:
   j=dict(id=key,source_name=p.name,source_sha256=h,source_metadata=meta,language=language,status='queued',output_name=self.choose_name(p.name,key),attempts=0,created_at=now());self.state['jobs'][key]=j;self.save()
  spool=self.home/'spool'/key;spool.mkdir(parents=True,exist_ok=True);audio=spool/('audio'+p.suffix.lower());cache=spool/'asr.json'
  with self.mu:self.active=p.name
  try:
   if j['status']=='publishing':self.complete(j,spool);return
   j.update(status='processing',attempts=j['attempts']+1);self.save();self.journal('started',job=key,language=language,source=p.name)
   if not cache.exists():
    shutil.copyfile(p,audio)
    if digest(audio)!=h or digest(p)!=h or metadata(p)!=meta:raise Changed('Source changed while copying')
    self.say(p.name,'РАСПОЗНАВАНИЕ '+language);data=self.recognize(audio,language);data.update(source_sha256=h,title=Path(p.name).stem,processed_at=now());write(cache,data)
   else:
    data=load(cache)
    if data['source_sha256']!=h:raise ValueError('ASR cache identity mismatch')
   if digest(p)!=h or metadata(p)!=meta:raise Changed('Source changed during processing')
   stage=spool/'outputs';stage.mkdir(exist_ok=True);rows=data['segments']
   (stage/'transcript.txt').write_text('\n'.join(f"[{stamp(s['start'],'.')}–{stamp(s['end'],'.')}] {s['text']}" for s in rows)+'\n',encoding='utf8')
   (stage/'transcript.srt').write_text('\n\n'.join(f"{i}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['text']}" for i,s in enumerate(rows,1))+'\n',encoding='utf8')
   self.say(p.name,'СБОРКА WORD');details=self.build_word(cache,stage/'dialogue.docx')
   import zipfile
   with zipfile.ZipFile(stage/'dialogue.docx') as z:
    if z.testzip() or 'word/document.xml' not in z.namelist():raise ValueError('Invalid Word output')
   if digest(p)!=h or metadata(p)!=meta:raise Changed('Source changed before publish')
   j.update(status='publishing',output_hashes={q.name:digest(q) for q in stage.iterdir() if q.name in ('transcript.txt','transcript.srt','dialogue.docx')},asr=data.get('asr'),elapsed_asr_seconds=data.get('elapsed_asr_seconds'),detected_language=data['detected_language'],word=details);self.save();self.journal('publishing',job=key)
   self.complete(j,spool);self.say(p.name,'ЗАВЕРШЕНО → '+j['output_name'])
  except Exception as exc:
   # Publishing status is retained to recover its transaction without ASR. Other errors retry cached ASR if present.
   if j['status']!='publishing':j['status']='source_changed' if isinstance(exc,Changed) else 'failed'
   j.update(error=f'{type(exc).__name__}: {exc}',retry_at=time.time()+self.cfg.get('retry_seconds',300));self.save();self.journal('error',job=key,error=j['error']);self.say(p.name,'ОШИБКА: '+j['error']);logging.exception('Dialogue failed: %s',p.name)
  finally:
   with self.mu:self.active=None
 def tick(self):
  self.check_state()
  if self.cfg.get('central_config'):
   from pipeline_config import Config
   if Config(self.cfg['central_config']).bytes.hex()!=self.cfg['config_signature']:raise ValueError('Config изменён; требуется перезапуск Dialogue')
  self.layout()
  for p in sorted((self.root/DIRS[0]).iterdir(),key=lambda p:p.name.casefold()):
   if not p.is_file() or p.suffix.lower() not in EXT or p.name.startswith(('~','.')):continue
   try:
    ready=self.stable(p)
    if not ready:
     if not self.rows.get(p.name,'').startswith('ЗАВЕРШЕНО') or self.clock()-self.obs.get(p.name,{}).get('since',self.clock())<self.cfg.get('stable_seconds',120):self.say(p.name,'Ожидание стабильности/проверки SHA-256')
     continue
    if self.busy_lecture():self.say(p.name,'Ожидание освобождения ASR лекционного worker');continue
    self.process(p,*ready,self.language(p.name))
   except Exception as exc:self.say(p.name,'ОШИБКА ФАЙЛА: '+str(exc));self.journal('file_error',source=p.name,error=str(exc));logging.exception('File failed')
  self.status()
def run(config):
 central=Path(os.environ.get('LECTURE_CONFIG',str(Path(config).resolve().parent.parent/'config.json')))
 cfg=load(config) if Path(config).is_file() else {}
 if central.is_file():
  sys.path.insert(0,str(Path(__file__).resolve().parent.parent));from pipeline_config import Config,require_preflight
  c=Config(central);require_preflight(c);cfg=c.dialogue();cfg.update(central_config=str(c.path),config_signature=c.bytes.hex())
 home=Path(cfg['home']);home.mkdir(parents=True,exist_ok=True)
 from logging.handlers import RotatingFileHandler
 logging.basicConfig(handlers=[RotatingFileHandler(home/'worker.log',maxBytes=5000000,backupCount=3,encoding='utf8')],level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
 class LogStream:
  def write(self,text):
   if text.strip():logging.info(text.strip())
  def flush(self):pass
 sys.stdout=sys.stderr=LogStream()
 with single_instance(home):
  w=Worker(cfg);stop=threading.Event()
  def heartbeat():
   while not stop.wait(15):
    try:w.status()
    except Exception:logging.exception('Heartbeat failed')
  threading.Thread(target=heartbeat,daemon=True).start();w.journal('worker_start',pid=os.getpid());w.status()
  try:
   while not (home/'stop').exists():
    try:w.tick()
    except Exception:logging.exception('Scan failed; no state reset')
    if (home/'stop').exists():break
    time.sleep(cfg.get('poll_seconds',10))
  finally:
   stop.set();w.journal('worker_stop');write(home/'status.json',dict(worker='STOPPED',at=now()))
   try:write(w.root/DIRS[3]/'status.json',dict(worker='STOPPED',at=now()))
   except OSError:pass
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);args=p.parse_args();run(args.config)
