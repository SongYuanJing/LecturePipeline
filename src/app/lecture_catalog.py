"""Observational projection. No locks, writes, hashing, processing or persistent cache."""
from pathlib import Path
import re
from pipeline_config import read, child
import lecture_dates

LABELS = dict(problem='Несогласованное состояние', review='Требует проверки', error='Ошибка',
              done='Готово', vocabulary='Словарь ожидает завершения', word='Формирование Word',
              ai_ready='AI готов · ожидает Word', waiting_ai='Ожидает AI', raw='Расшифровка готова',
              asr='Распознавание', publishing='Публикация расшифровки', ready='Готово к обработке',
              waiting='Ожидание')
AI_STATES={'waiting_ai','ai_result_ready','building','vocabulary_pending','completed','failed'}
KEY=re.compile(r'\d{2,3}_\d{4}-\d{2}-\d{2}\Z')


def reason_text(value):
    text=str(value)
    for key,label in [('duplicate_source_requires_review','Найдена копия уже принятого материала'),
                      ('changed_source_requires_review','Исходник изменился после принятия'),
                      ('waiting_stable','Ожидается завершение копирования'),('waiting_parts','Ожидаются части'),
                      ('review','Требует проверки')]:
        if text==key or text.startswith(key+':'):return label+(' · '+text.split(':',1)[1].strip() if ':' in text else '')
    return text


def resolve_status(*, problems, review, error, final, vocabulary, ai, raw, job, ready):
    """Single precedence rule; committed stages dominate lagging activity flags."""
    if problems:return 'problem'
    if review:return 'review'
    if error:return 'error'
    if final:return 'done'
    if vocabulary=='batch_pending' or ai=='vocabulary_pending':return 'vocabulary'
    if ai=='building':return 'word'
    if ai=='ai_result_ready':return 'ai_ready'
    if raw:return 'waiting_ai' if ai=='waiting_ai' else 'raw'
    if job=='transcribing':return 'asr'
    if job=='publishing':return 'publishing'
    if ready:return 'ready'
    return 'waiting'


def filtered(items, course=None, status=None, newest=True):
    rows=[r for r in items if (not course or r['course_id']==course) and (not status or r['status']==status)]
    known=[r for r in rows if r['lecture_date']];unknown=[r for r in rows if not r['lecture_date']]
    return sorted(known,key=lambda r:(r['lecture_date'],r['id']),reverse=newest)+sorted(unknown,key=lambda r:r['id'])


class Reader:
    def __init__(self):self.errors=[]
    def json(self,path,*,required=False,section=None,errors=None):
        errors=self.errors if errors is None else errors
        try:
            if not path.exists() and not required:return {}
            value=read(path)
            if not isinstance(value,dict):raise ValueError('ожидается объект')
            if section is not None and not isinstance(value.get(section),dict):raise ValueError('неверное поле '+section)
            return value
        except (OSError,ValueError,TypeError) as exc:
            errors.append(f'{path.name}: {exc}');return {}
    def glob(self,path,pattern,errors=None):
        try:return sorted(path.glob(pattern))
        except OSError as exc:
            (self.errors if errors is None else errors).append(str(exc));return []


def build(c):
    reader=Reader();subjects=c.subjects(include_disabled=True);entities={};pending=[]
    state=reader.json(c.state,required=True,section='lectures').get('lectures',{})
    completed=reader.json(c.ai_state,required=True,section='processed').get('processed',{})
    inbox=reader.json(c.worker_home/'inbox.json',required=(c.worker_home/'inbox.initialized').exists())
    if inbox.get('schema_version',1)!=1:reader.errors.append('Неизвестная схема Inbox')
    jobs=reader.json(c.worker_home/'worker_jobs.json',section='jobs').get('jobs',{})
    worker=reader.json(c.worker_home/'worker_status.json').get('lectures',{})
    queue=reader.json(c.queue_home/'queue.json',required=(c.queue_home/'initialized').exists(),section='tasks').get('tasks',{})
    def entity(code,key):
        if not isinstance(key,str) or not KEY.fullmatch(key) or not isinstance(code,str):
            reader.errors.append('Некорректная идентичность лекции: '+str(code)+'/'+str(key));return None
        ident=code+'/'+key
        return entities.setdefault(ident,dict(id=ident,course_id=code,lecture_key=key,reservations=[],records=[],packets=[],problems=[]))
    def join(mapping,field):
        if not isinstance(mapping,dict):reader.errors.append('Неверная таблица '+field);return
        for ident,value in mapping.items():
            if not isinstance(value,dict) or '/' not in ident:reader.errors.append('Неверная запись '+field);continue
            code,key=ident.split('/',1);e=entity(code,key)
            if e is not None:e[field]=value
    join(state,'state');join(jobs,'job');join(worker,'worker')
    for value in queue.values():
        if not isinstance(value,dict):reader.errors.append('Неверная AI задача');continue
        if value.get('workspace')!=c.active:continue
        e=entity(value.get('subject_code'),value.get('lecture_key'))
        if e is not None:
            if 'task' in e:e['problems'].append('Несколько AI задач для одной лекции')
            e['task']=value
            if value.get('id')!=c.active+'/'+e['id']:e['problems'].append('AI identity не совпадает')
    for record in completed.values():
        if not isinstance(record,dict):reader.errors.append('Неверная запись AI completion');continue
        e=entity(record.get('subject_code'),record.get('lecture_id'))
        if e is not None:e['records'].append(record)
    sources=inbox.get('sources',{});groups=inbox.get('groups',{})
    if not isinstance(sources,dict) or not isinstance(groups,dict):
        reader.errors.append('Неверные sources/groups Inbox');sources={};groups={}
    owned=set()
    def intake(row,identity,kind,members):
        code=row.get('course_id');key=row.get('lecture_key')
        if key:
            e=entity(code,key)
            if e is not None:e['reservations'].append(dict(row,members=members))
        elif row.get('status')!='superseded':
            pending.append(dict(id=identity,course_id=code,course_display_name=subjects.get(code,{}).get('title',code),
                                name=row.get('session_stem') or Path(row.get('source_path','')).name,
                                kind=kind,status=row.get('status','review'),reason=reason_text(row.get('error') or row.get('status','Ожидание')),
                                parts=[m.get('part_hint') for m in members],members=members,**lecture_dates.metadata(row)))
    for gid,g in groups.items():
        if not isinstance(g,dict) or not isinstance(g.get('member_ids',[]),list):reader.errors.append('Неверная группа Inbox');continue
        members=[sources[sid] for sid in g.get('member_ids',[]) if isinstance(sources.get(sid),dict)]
        owned.update(g.get('member_ids',[]));intake(g,gid,'group',members)
    for sid,row in sources.items():
        if not isinstance(row,dict):reader.errors.append('Неверный источник Inbox');continue
        if sid not in owned:intake(row,sid,'source',[row])
    for code,s in subjects.items():
        for path in reader.glob(s['audio_dir'],'.manual-handoff-*.json'):
            row=reader.json(path);key=row.get('lecture_key')
            if key:
                e=entity(code,key)
                if e is not None:e['reservations'].append(row)
        for path in reader.glob(s['audio_dir'],'*.READY.json'):
            e=entity(code,path.name.removesuffix('.READY.json'))
            if e is not None:e['ready']=reader.json(path,required=True,errors=e['problems'])
        for path in reader.glob(s['raw_dir'],'*/*_manifest.json'):
            e=entity(code,path.parent.name)
            if e is not None:
                e['manifest']=reader.json(path,required=True,errors=e['problems']);e['manifest_path']=path
        # Unclaimed Word is visible as a problem, never as a successful lecture.
        for path in reader.glob(s['ready_dir'],'*/lecture.docx'):
            if KEY.fullmatch(path.parent.name):
                e=entity(code,path.parent.name)
                if e is not None:e['word_candidate']=path
    for path in reader.glob(c.queue_home/'packets','*/source_packet.json'):
        if path.parent.name.startswith('.'):continue
        packet=reader.json(path);task=packet.get('task',{})
        if not isinstance(task,dict):reader.errors.append('Неверная identity пакета AI');continue
        if task.get('workspace')==c.active:
            e=entity(task.get('subject_code'),task.get('lecture_key'))
            if e is not None:e['packets'].append(str(path))
    rows=[]
    for e in entities.values():
        try:rows.append(project(c,subjects,e,reader.errors))
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
            rows.append(dict(id=e['id'],course_id=e['course_id'],course_display_name=subjects.get(e['course_id'],{}).get('title',e['course_id']),
                             lecture_key=e['lecture_key'],lecture_date=None,lecture_date_source='unknown',status='problem',
                             status_text=LABELS['problem'],parts=0,members=[],paths={},stages={},reasons=['Повреждена запись: '+str(exc)],problems=[str(exc)]))
    return dict(workspace=c.active,items=filtered(rows),pending=sorted(pending,key=lambda r:(str(r['course_id']),r['id'])),errors=reader.errors)


def project(c,subjects,e,global_errors):
    code=e['course_id'];key=e['lecture_key'];s=subjects.get(code);problems=list(e['problems'])+list(global_errors)
    if s is None:problems.append('Курс отсутствует в config');s={}
    ready=e.get('ready',{});manifest=e.get('manifest',{});state=e.get('state',{});task=e.get('task',{})
    job=e.get('job',{});worker=e.get('worker',{});records=e['records'];reservation=next(iter(e['reservations']),{})
    if len(records)>1:problems.append('Несколько AI completion записей')
    record=records[0] if len(records)==1 else {}
    paths={};stages=dict(audio='unknown',ready='available' if ready else 'missing',raw='missing',ai=task.get('status','unknown'),word='missing',vocabulary=record.get('vocabulary_status','legacy' if record else 'unknown'))
    if record and not task:stages['ai']='completed'
    def present(path,label):
        if not path.is_file() or path.stat().st_size==0:problems.append(label+' отсутствует/пуст');return False
        return True
    if ready and ready.get('lecture')!=key:problems.append('READY identity не совпадает')
    if manifest and (manifest.get('lecture')!=key or manifest.get('subject_code')!=code):problems.append('Raw identity не совпадает')
    raw_ok=False
    if manifest:
        folder=e['manifest_path'].parent;paths['raw']=str(folder)
        names=[manifest['combined_txt']]
        for output in manifest['outputs']:
            names.append(output['srt'])
            if output.get('txt'):names.append(output['txt'])
        checks=[present(child(folder,name),'Raw '+name) for name in names]
        raw_ok=bool(manifest['outputs']) and all(checks)
        stages['raw']='available' if raw_ok else 'problem'
        if 'output_hashes' in manifest and set(manifest['output_hashes'])!=set(names):problems.append('Неполный raw hash contract')
        if not manifest['outputs']:problems.append('Raw не содержит частей')
        if state.get('status','').lower() not in ('completed','done'):problems.append('Raw опубликован, completed не подтверждён; восстановление VIC-12')
    elif state.get('status','').lower() in ('completed','done') or record or task:
        problems.append('Отсутствует raw manifest')
    raw_committed=raw_ok and state.get('status','').lower() in ('completed','done')
    source=ready.get('intake',{});members=source.get('members') or reservation.get('members') or []
    if members:
        members=[dict(name=Path(m['source_path']).name,path=m['source_path'],part=m.get('part_hint')) for m in members]
    elif ready.get('files'):
        members=[dict(name=f['name'],path=str(child(s['audio_dir'],f['name'])),part=i) for i,f in enumerate(ready['files'],1)]
    else:members=[dict(name=m.get('name') or m.get('source','неизвестно'),path=m.get('path'),part=i) for i,m in enumerate(manifest.get('sources') or state.get('sources') or manifest.get('outputs',[]),1)]
    if members and members[0].get('path'):paths['source']=str(Path(members[0]['path']).parent)
    if ready:
        audio=[child(s['audio_dir'],f['name']) for f in ready['files']]
        audio_ok=bool(audio) and all(p.is_file() for p in audio)
        stages['audio']='available' if audio_ok else 'missing'
        if not audio_ok and not raw_committed:problems.append('READY есть, управляемое аудио отсутствует')
    metadata=lecture_dates.metadata(dict(manifest or ready or reservation or state or task,lecture=key))
    dates=[]
    for value in (manifest,ready,reservation,state,task):
        if value:
            m=lecture_dates.metadata(value)
            if m['lecture_date']:dates.append(lecture_dates.day(m['lecture_date']))
    if len(set(dates))>1:problems.append('Authorities содержат разные даты лекции')
    if metadata['lecture_date']:lecture_dates.day(metadata['lecture_date'])
    word=None
    if record:
        if record.get('output_docx_local_path'):word=Path(record['output_docx_local_path'])
        elif record.get('output_docx_name') and s:word=child(s['ready_dir'],record['output_docx_name'])
        else:problems.append('AI completion не содержит путь Word')
    if word is None:word=e.get('word_candidate')
    word_ok=False
    if word:
        paths.update(word=str(word),result=str(word.parent));word_ok=present(word,'Word')
        stages['word']='available' if word_ok else 'problem'
        report_path=word.parent/'processing_report.json'
        if report_path.exists():
            report=read(report_path)
            hashes=report['output_hashes']
            if 'lecture.docx' not in hashes:problems.append('Word report без lecture.docx')
            committed_hash=record.get('output_provenance',{}).get('sha256')
            if committed_hash and hashes.get('lecture.docx')!=committed_hash:problems.append('Word report расходится с AI completion SHA-256')
            for name in hashes:present(child(word.parent,name),'Word '+name)
        if not record and task.get('status') not in ('building','vocabulary_pending'):
            problems.append('Word существует без подтверждения finalizer')
    elif record or task.get('status')=='completed':problems.append('Отсутствует завершённый Word')
    if task.get('status') and task['status'] not in AI_STATES:problems.append('Неизвестное состояние AI')
    if job.get('phase') and job['phase'] not in ('transcribing','publishing','done','error'):problems.append('Неизвестное состояние ASR job')
    if task.get('status')=='completed' and not record:problems.append('AI queue completed без AI ledger')
    if task.get('status')=='completed' and record.get('vocabulary_status')=='batch_pending':problems.append('AI queue и vocabulary расходятся')
    if task.get('source_packet'):
        packet=Path(task['source_packet']);paths['packet']=str(packet.parent);present(packet,'AI пакет')
    elif e['packets']:paths['packet']=str(Path(e['packets'][0]).parent)
    if task.get('status') in ('ai_result_ready','building','vocabulary_pending','completed') and task.get('ai_content'):
        present(Path(task['ai_content']),'Принятый результат AI')
    elif task.get('status') in ('ai_result_ready','building'):
        problems.append('AI результат отмечен принятым, но его путь отсутствует')
    if record.get('dictionary_provenance'):
        paths['dictionary']=record['dictionary_provenance'].get('path')
        if paths['dictionary'] and not Path(paths['dictionary']).is_file():problems.append('Связанный словарь недоступен')
    reasons=[str(r.get('error') or r.get('detail')) for r in [*e['reservations'],task,job,worker,state] if r.get('error') or (r.get('status')=='ERROR' and r.get('detail'))]
    recovery=[r['recovery_action'] for r in [*e['reservations'],task,job] if r.get('recovery_action')]
    review=any(r.get('review_required') or r.get('status')=='review' for r in e['reservations'])
    error=task.get('status')=='failed' or any(r.get('status')=='failed' for r in e['reservations'])
    # Prior transient worker errors/activity lose authority after a committed raw stage.
    if not raw_committed:error=error or job.get('phase')=='error' or worker.get('status')=='ERROR'
    elif worker.get('status')=='ERROR' and 'requires_review' in worker.get('detail',''):review=True
    final=bool(record and raw_committed and word_ok and record.get('vocabulary_status') in ('merged','completed'))
    if record and not record.get('vocabulary_status'):review=True;reasons.append('Старая запись: завершение словаря неизвестно')
    if record and record.get('vocabulary_status') not in (None,'merged','completed','batch_pending'):review=True;reasons.append('Неизвестный статус словаря')
    status=resolve_status(problems=problems,review=review,error=error,final=final,vocabulary=stages['vocabulary'],ai=task.get('status'),raw=raw_committed,job=job.get('phase'),ready=bool(ready))
    return dict(id=e['id'],course_id=code,course_display_name=s.get('title',code),lecture_key=key,
                **metadata,status=status,status_text=LABELS[status],parts=len(members),members=members,
                stages=stages,paths=paths,problems=problems,reasons=problems+reasons,recovery=recovery,
                integrity='Состояние из журналов; SHA-256 файлов при просмотре не пересчитывается')
