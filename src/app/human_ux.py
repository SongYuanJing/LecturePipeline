"""Small GUI actions over existing config/READY/AI contracts. No AI generation."""
import copy,hashlib,json,os,re,shutil,subprocess,uuid,zipfile
from datetime import datetime,timezone
from pathlib import Path
from pipeline_config import Config,need,read,child
import ai_queue
import lecture_dates

class SourceReview(ValueError):
 """Known content/lineage ambiguity; never allocate another key on retry."""

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(4194304),b''):h.update(block)
 return h.hexdigest()
def pipeline(c):
 os.environ['LECTURE_CONFIG']=str(c.path)
 import lecture_pipeline as p
 return p

def intake_reservations(c,subject):
 path=c.worker_home/'inbox.json'
 state=read(path) if path.exists() else {}
 keys={r['lecture_key'] for section in ('sources','groups') for r in state.get(section,{}).values()
       if r.get('course_id')==subject and r.get('lecture_key')}
 for receipt in c.subjects()[subject]['audio_dir'].glob('.manual-handoff-*.json'):
  row=read(receipt)
  if row.get('lecture_key'):keys.add(row['lecture_key'])
 return keys

def next_number(c,subject):
 p=pipeline(c);s=c.subjects()[subject];keys=set(p.collect_lectures(s['audio_dir']))|{k.split('/',1)[1] for k in read(c.state)['lectures'] if k.startswith(subject+'/')}
 keys.update(intake_reservations(c,subject))
 return max([int(k.split('_',1)[0]) for k in keys if re.match(r'^\d+_',k)]+[0])+1

def add_lecture(c,subject,day,number,files,*,intake=None,reserve=None):
 if intake is not None:return _add_lecture(c,subject,day,number,files,intake=intake,reserve=reserve)
 c.assert_current();need(subject in c.subjects(),'Выберите действующий предмет');need(bool(files),'Выберите аудиофайлы')
 p=pipeline(c);s=c.subjects()[subject];paths=[Path(f).resolve() for f in files]
 identity=hashlib.sha256(json.dumps([c.active,subject,[os.path.normcase(str(f)) for f in paths]]).encode()).hexdigest()
 receipt=s['audio_dir']/('.manual-handoff-'+identity+'.json')
 with p.pipeline_lock(s['audio_dir']/'.manual-ingest.lock'):
  if receipt.exists():
   row=read(receipt);need(row.get('source_id')==identity,'Manual handoff identity mismatch')
   if day:need(lecture_dates.day(day)==row['lecture_date'],'Дата зарезервирована; изменение требует проверки')
   need([p.source_signature(f) for f in paths]==[m['signature'] for m in row['members']],
        'changed_source_requires_review: ручной источник изменился после резервирования')
  else:
   row=lecture_dates.resolve([str(f) for f in paths],override=day or None,imported_at=datetime.now(timezone.utc).isoformat(),same_session=False)
   need(row['lecture_date'] is not None,'Дата неизвестна или конфликтует; требуется ручная проверка')
   row.update(source_id=identity,course_id=subject,members=[dict(source_id=identity+'-'+str(i),source_path=str(f),signature=p.source_signature(f),part_hint=i) for i,f in enumerate(paths,1)])
  def reserved(key):
   need(key not in intake_reservations(c,subject) and key not in p.collect_lectures(s['audio_dir']),'Лекция уже существует или зарезервирована')
   row['lecture_key']=key;ai_queue.atomic(receipt,row)
  result=_add_lecture(c,subject,row['lecture_date'],number,paths,intake=row,reserve=reserved)
  row.update(lecture_key=result,status='queued');ai_queue.atomic(receipt,row)
  return result

def _add_lecture(c,subject,day,number,files,*,intake=None,reserve=None):
 c.assert_current()
 metadata=dict(intake) if intake is not None else lecture_dates.resolve([str(f) for f in files],override=day or None,imported_at=datetime.now(timezone.utc).isoformat(),same_session=False)
 day=metadata.get('lecture_date')
 need(day is not None,'Дата неизвестна или конфликтует; требуется ручная проверка')
 lecture_dates.day(day)
 need(number is None and intake is not None or type(number) is int and 1<=number<=999,'Номер лекции: 1–999')
 need(subject in c.subjects(),'Выберите действующий предмет');need(bool(files),'Выберите аудиофайлы')
 p=pipeline(c);s=c.subjects()[subject];files=[Path(f).resolve() for f in files]
 need(len(files)==len(set(files)),'Один файл выбран несколько раз')
 # Separate producer lock: never waits on/stops the long-lived worker lock.
 with p.pipeline_lock(s['audio_dir']/'.ingest.lock'):
  key=(intake or {}).get('lecture_key')
  if key and p.ready_path(s,key).exists():
   ready=p.read_ready(s,key,p.collect_lectures(s['audio_dir']).get(key,[]))
   need(ready.get('intake',{}).get('source_id')==intake['source_id'],'READY принадлежит другому source')
   if 'members' in intake:need(ready.get('intake',{}).get('members')==intake['members'],'READY содержит другой набор частей')
   need(all(sha(s['audio_dir']/e['name'])==e['sha256'] for e in ready['files']),'Повреждён опубликованный intake')
   intake['recovery_action']='recovered_existing_ready'
   return key
  need(all(f.is_file() and f.suffix.lower() in p.AUDIO_EXTENSIONS for f in files),'Неподдерживаемый аудиофайл')
  need(all(f.stat().st_size>0 for f in files),'Аудио пусто: дождитесь завершения копирования')
  hashes=[sha(f) for f in files]
  if intake and intake.get('source_hashes') and hashes!=intake['source_hashes']:
   raise SourceReview('changed_source_requires_review: содержимое изменилось после резервирования')
  for sealed in s['audio_dir'].glob('*.READY.json'):
   previous=read(sealed)
   if previous.get('lecture')==key:continue
   if sorted(hashes)==sorted(e['sha256'] for e in previous['files']):
    raise SourceReview('duplicate_source_requires_review: комплект уже существует как '+previous['lecture'])
  for pending in s['audio_dir'].glob('.manual-handoff-*.json'):
   previous=read(pending)
   if previous.get('source_id')!=(intake or {}).get('source_id') and sorted(previous.get('source_hashes',[]))==sorted(hashes):
    raise SourceReview('duplicate_source_requires_review: тот же комплект уже зарезервирован')
  metadata['source_hashes']=hashes
  metadata['source_lineage']=[dict(source_path=str(f),signature=p.source_signature(f),sha256=h) for f,h in zip(files,hashes)]
  if intake is not None:intake['source_hashes']=hashes
  if key is None:
   number=next_number(c,subject) if number is None else number
   need(1<=number<=999,'Номер лекции: 1–999');key=f'{number:02d}_{day}'
   if reserve:reserve(key)
  elif intake is not None:intake['recovery_action']='resumed_reserved_handoff'
  need(re.fullmatch(r'\d{2,3}_\d{4}-\d{2}-\d{2}',key) is not None and key.split('_',1)[1]==day,'Некорректный intake lecture key')
  if intake:
   members=intake.get('members',[intake])
   need(len(files)==len(members) and all(p.source_signature(f)==m['signature'] and
        str(f)==m['source_path'] for f,m in zip(files,members)),'Source изменился после stability gate')
  else:
   need(key not in intake_reservations(c,subject),'Номер зарезервирован Inbox: выберите другой номер')
   need(key not in p.collect_lectures(s['audio_dir']),'Лекция уже существует: выберите другой номер')
  need(subject+'/'+key not in read(c.state)['lectures'] and not p.ready_path(s,key).exists(),'Лекция уже существует: выберите другой номер')
  stage=s['audio_dir']/('.ingest-'+uuid.uuid4().hex);stage.mkdir();published=[]
  try:
   for i,source in enumerate(files,1):
    signature=p.source_signature(source);target=stage/f'{key}_{i}{source.suffix.lower()}'
    shutil.copy2(source,target)
    need(target.stat().st_size>0 and signature==p.source_signature(source) and sha(source)==sha(target)==hashes[i-1],'Аудио изменяется/пусто: дождитесь завершения копирования')
    with target.open('r+b') as f:os.fsync(f.fileno())
   c.assert_current()
   for f in sorted(stage.iterdir()):
    dest=s['audio_dir']/f.name
    if dest.exists():
     need(intake is not None and sha(dest)==sha(f),'Файл уже появился: '+dest.name)
     f.unlink() # Only our owned unpublished staging copy; keep existing input.
    else:f.rename(dest)
    published.append(dest)
   metadata.setdefault('course_id',subject)
   p.prepare_ready(s,key,len(files),metadata=metadata)
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
