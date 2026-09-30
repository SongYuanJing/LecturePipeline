"""Small GUI actions over existing config/READY/AI contracts. No AI generation."""
import copy,hashlib,json,os,re,shutil,subprocess,uuid,zipfile
from datetime import date
from pathlib import Path
from pipeline_config import Config,need,read,child
import ai_queue

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(4194304),b''):h.update(block)
 return h.hexdigest()
def pipeline(c):
 os.environ['LECTURE_CONFIG']=str(c.path)
 import lecture_pipeline as p
 return p

def next_number(c,subject):
 p=pipeline(c);s=c.subjects()[subject];keys=set(p.collect_lectures(s['audio_dir']))|{k.split('/',1)[1] for k in read(c.state)['lectures'] if k.startswith(subject+'/')}
 return max([int(k.split('_',1)[0]) for k in keys if re.match(r'^\d+_',k)]+[0])+1

def add_lecture(c,subject,day,number,files):
 c.assert_current();date.fromisoformat(day);need(type(number) is int and 1<=number<=999,'Номер лекции: 1–999')
 need(subject in c.subjects(),'Выберите действующий предмет');need(bool(files),'Выберите аудиофайлы')
 p=pipeline(c);s=c.subjects()[subject];key=f'{number:02d}_{day}';files=[Path(f).resolve() for f in files]
 need(len(files)==len(set(files)),'Один файл выбран несколько раз')
 need(all(f.is_file() and f.suffix.lower() in p.AUDIO_EXTENSIONS for f in files),'Неподдерживаемый аудиофайл')
 # Separate producer lock: never waits on/stops the long-lived worker lock.
 with p.pipeline_lock(s['audio_dir']/'.ingest.lock'):
  need(key not in p.collect_lectures(s['audio_dir']) and subject+'/'+key not in read(c.state)['lectures'] and not p.ready_path(s,key).exists(),'Лекция уже существует: выберите другой номер')
  stage=s['audio_dir']/('.ingest-'+uuid.uuid4().hex);stage.mkdir();published=[]
  try:
   for i,source in enumerate(files,1):
    signature=p.source_signature(source);target=stage/f'{key}_{i}{source.suffix.lower()}'
    shutil.copy2(source,target)
    need(target.stat().st_size>0 and signature==p.source_signature(source) and sha(source)==sha(target),'Аудио изменяется/пусто: дождитесь завершения копирования')
    with target.open('r+b') as f:os.fsync(f.fileno())
   c.assert_current()
   for f in sorted(stage.iterdir()):
    dest=s['audio_dir']/f.name;need(not dest.exists(),'Файл уже появился: '+dest.name);f.rename(dest);published.append(dest)
   p.prepare_ready(s,key,len(files)) # Existing atomic READY and exact contract.
   p.read_ready(s,key,p.collect_lectures(s['audio_dir'])[key])
   return key
  except Exception:
   # No READY means worker cannot process partial input. Keep evidence for diagnosis.
   raise
  finally:
   if stage.exists() and not any(stage.iterdir()):stage.rmdir()

def export_packet(c,identity,destination):
 task=ai_queue.load_queue(c)['tasks'].get(identity);need(task is not None and task['workspace']==c.active,'Выберите лекцию текущего workspace')
 folder=Path(task['source_packet']).parent;ai_queue.verify_packet(folder)
 destination=Path(destination);need(not destination.exists(),'Файл экспорта уже существует')
 temp=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.pending')
 try:
  with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
   for p in sorted(folder.iterdir()):
    if p.is_file():z.write(p,p.name)
  ai_queue.verify_packet(folder)
  with zipfile.ZipFile(temp) as z:
   need(z.testzip() is None,'Повреждён экспорт')
   for n,h in read(folder/'package_hashes.json').items():need(hashlib.sha256(z.read(n)).hexdigest()==h,'Пакет изменился во время экспорта')
  temp.rename(destination)
 finally:temp.unlink(missing_ok=True)
 return str(destination)

def quote_diagnostic(content,packet):
 index={s['id']:s for s in packet['segments']}
 def visit(x,path):
  if isinstance(x,dict):
   if 'quote' in x and 'start' in x and 'end' in x:
    a=index.get(x['start']);b=index.get(x['end'])
    text=' '.join(s['text'] for s in packet['segments'] if a and b and s['part']==a['part'] and a['cue']<=s['cue']<=b['cue'])
    need(isinstance(x['quote'],str) and bool(x['quote']) and x['quote'] in text,path+'.quote не совпадает с SRT')
   for k,v in x.items():visit(v,path+'.'+k if path else k)
  elif isinstance(x,list):
   for i,v in enumerate(x):visit(v,f'{path}[{i}]')
 visit(content,'')

def import_result(c,identity,path):
 task=ai_queue.load_queue(c)['tasks'].get(identity);need(task is not None and task['workspace']==c.active,'Выберите лекцию текущего workspace')
 packet=ai_queue.verify_packet(Path(task['source_packet']).parent);content=read(path);quote_diagnostic(content,packet)
 # Word validation requires the document runtime; no new schema or validator.
 staged=c.queue_home/'imports'/(hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True).encode()).hexdigest()+'.json')
 validator="import sys;sys.path.insert(0,sys.argv[1]);import ai_queue;from pipeline_config import Config,read;c=Config(sys.argv[2]);p=read(sys.argv[3]);ai_queue.module(c).validate_content(read(sys.argv[4]),p)"
 args=[str(c.runtime('document_python','')), '-I','-B','-X','utf8','-c',validator,str(c.install),str(c.path),task['source_packet'],str(path)]
 r=subprocess.run(args,capture_output=True,text=True,encoding='utf8',creationflags=0x08000000,timeout=60)
 if r.returncode:raise ValueError('AI result не принят: '+r.stderr.strip().splitlines()[-1])
 # Freeze accepted bytes before invoking the existing finalizer.
 need(read(path)==content,'AI result изменился во время проверки');ai_queue.atomic(staged,content)
 r=subprocess.run([str(c.runtime('document_python','')),'-I','-B','-X','utf8',str(c.install/'ai_finalize.py'),'--config',str(c.path),'--task',identity,'--content',str(staged)],capture_output=True,text=True,encoding='utf8',creationflags=0x08000000)
 if r.returncode:raise RuntimeError(r.stderr.strip() or r.stdout.strip())
 return json.loads(r.stdout)

def edit_subject(c,code,name,language,manager,new=False):
 need(re.fullmatch('[A-Za-z0-9_-]+',code) is not None,'Код предмета: латинские буквы, цифры, - или _');need(bool(name.strip()),'Введите название предмета');need(language in ('zh','en','auto'),'Выберите язык')
 data=copy.deepcopy(c.data);subjects=data['workspaces'][c.active]['subjects'];found=next((s for s in subjects if s['subject_code']==code),None)
 if new:
  need(found is None,'Такой код предмета уже существует');folder=child(c.workspace_root,code);need(not folder.exists(),'Папка предмета уже существует')
  for n in ('audio','raw','word'):(folder/n).mkdir(parents=True)
  subjects.append(dict(subject_code=code,subject_name=name,folder=code,default_language=language,enabled=True,paths=dict(audio='audio',raw='raw',ready='word')))
 else:
  need(found is not None,'Предмет не найден');found.update(subject_name=name,default_language=language)
 return manager.apply_config(data)

def add_workspace(c,name,manager):
 need(bool(name.strip()),'Введите название workspace');key='semester-'+uuid.uuid4().hex[:8];data=copy.deepcopy(c.data)
 data['workspaces'][key]=dict(name=name,folder=key,lecture_state='system/state.json',ai_state='system/ai_state.json',worker_home='run/workspaces/'+key,subjects=[])
 root=child(c.data_root,key);need(not root.exists(),'Папка уже существует');root.mkdir()
 for n,value in [('state.json',dict(version=1,lectures={})),('ai_state.json',dict(schema_version=1,processed={}))]:ai_queue.atomic(root/'system'/n,value)
 data['active_workspace']=key;return manager.apply_config(data)

def progress_view(value):
 total=value.get('audio_duration_sec',0);done=value.get('processed_audio_sec',0);elapsed=value.get('elapsed_sec',0)
 ratio=min(1,max(0,done/total)) if total and total>0 else None
 eta=(total-done)*elapsed/done if ratio is not None and 0.03<=ratio<1 and elapsed>=10 and done>=15 else None
 return dict(progress=ratio,eta=eta)
