"""Course folder UX services. Config/worker transactions stay with GUI Manager."""
import copy
from contextlib import ExitStack
from datetime import datetime
import os
from pathlib import Path
import tempfile
import uuid

from pipeline_config import Config,need,read,child
from ai_queue import atomic
import human_ux as ux

FIELDS=('source_audio_folder','archive_audio_folder','raw_output_folder','final_output_folder')
LABELS=dict(zip(FIELDS,('Входящие аудио','Архив аудио (пока без переноса)','Черновики / TXT / SRT','Готовые лекции / Word')))
STATUS={'waiting_stable':'Ожидание стабильного файла','waiting_parts':'Ожидание частей / завершения копирования',
 'ready':'Готово к передаче','queued':'В очереди','processing':'Обработка','completed':'Готово',
 'review':'Нужна проверка','failed':'Ошибка','waiting_ai':'Ожидание результата ChatGPT',
 'ai_result_ready':'AI-результат принят','building':'Создание Word','vocabulary_pending':'Обновление словаря',
 'superseded':'Файл изменился; проверяется новая версия'}


def recommended(root):
    root=Path(root)
    need(root.is_absolute(),'Выберите абсолютный путь папки предмета')
    return dict(zip(FIELDS,map(str,(root/'Inbox',root/'Lectures/Audio',root/'Lectures/Raw',root/'Lectures/Final'))))


def detect(root):
    """Read-only, exact known presets; ambiguity always returns manual mode."""
    root=Path(root);need(root.is_dir(),'Папка предмета недоступна')
    proposals=[]
    generic=recommended(root)
    if all(Path(v).is_dir() for v in generic.values()):proposals.append(generic)
    def match(parent,prefix,words):
        return [p for p in parent.iterdir() if p.is_dir() and p.name.startswith(prefix) and
                any(word.casefold() in p.name.casefold() for word in words)]
    inbox=match(root,'00',('Входящие','待整理'))
    notes=match(root,'02',('Конспекты','разборы'))
    if len(inbox)==1 and len(notes)==1:
        audio=match(notes[0],'00',('Аудио лекций',))
        raw=match(notes[0],'01',('Черновые расшифровки',))
        final=match(notes[0],'02',('Готовые лекции',))
        if all(len(x)==1 for x in (audio,raw,final)):
            proposals.append(dict(zip(FIELDS,map(str,(inbox[0],audio[0],raw[0],final[0])))))
    return proposals[0] if len(proposals)==1 else None


def _create_tracked(path,created):
    missing=[];current=path
    while not current.exists():
        missing.append(current);current=current.parent
    for folder in reversed(missing):
        try:folder.mkdir()
        except FileExistsError:
            need(folder.is_dir(),'Вместо папки найден файл: '+str(folder))
        else:created.append(folder)


def check_directories(mapping,create=False):
    paths=[Path(v) for v in mapping.values() if v]
    for path in paths:
        need(path.is_absolute(),'Все пути должны быть абсолютными')
        for ancestor in (path,*path.parents):
            need(not ancestor.exists() or ancestor.is_dir(),'Вместо папки найден файл: '+str(ancestor))
        if not create:need(path.is_dir(),'Папка не существует: '+str(path))
    return paths


def validate_directories(mapping,create=False,probe=False,created=None):
    paths=check_directories(mapping,create)
    if create:
        for path in paths:_create_tracked(path,created if created is not None else [])
    source=Path(mapping['source_audio_folder'])
    with os.scandir(source) as entries:next(entries,None)
    if probe:
        for key in ('raw_output_folder','final_output_folder'):
            with tempfile.NamedTemporaryFile(prefix='.lp-write-probe-',dir=mapping[key]):pass


def save_course(c,manager,name,mapping,*,course_id=None,enabled=True,create=False,language='zh'):
    """Called only after preview/confirmation. No automatic output migration."""
    c.assert_current();need(bool(name.strip()),'Введите название предмета')
    need(language in ('zh','en','auto'),'Недопустимый язык')
    data=copy.deepcopy(c.data);subjects=data['workspaces'][c.active]['subjects']
    new=course_id is None;code=course_id or 'course-'+uuid.uuid4().hex[:12]
    subject=next((s for s in subjects if s['subject_code']==code),None)
    if new:
        subject=dict(subject_code=code,subject_name=name.strip(),folder=code,enabled=True,
                     default_language=language,paths=dict(audio='audio',raw='raw',ready='word'))
        subjects.append(subject)
    need(subject is not None,'Предмет больше не существует')
    subject.update(subject_name=name.strip(),default_language=language)
    binding=dict(subject.get('inbox',{}));binding.pop('output_folder',None)
    for field in FIELDS:
        value=mapping.get(field)
        need(field=='archive_audio_folder' or bool(value),'Выберите папку: '+LABELS[field])
        binding[field]=str(Path(value).resolve()) if value and Path(value).is_absolute() else value
    binding['enabled']=bool(enabled);subject['inbox']=binding
    probe=c.path.with_name('.course-validation-'+uuid.uuid4().hex+'.json')
    created=[]
    try:
        atomic(probe,data);candidate=Config(probe) # validate boundaries without creating folders
        old=c.subjects().get(code);target=candidate.subjects()[code]
        def relocation_check():
            if old and any(old[k]!=target[k] for k in ('raw_dir','ready_dir')):
                need(not any(x.name!='.ingest.lock' for x in old['audio_dir'].glob('*')) and not any(old['raw_dir'].glob('*')) and
                     not any(old['ready_dir'].glob('*')) and
                     not any(k.startswith(code+'/') for k in read(c.state)['lectures']),
                     'У предмета уже есть аудио или результаты. Перенос результатов сейчас не поддерживается.')
        relocation_check()
        check_directories({k:binding[k] for k in FIELDS},create=create)
        with ExitStack() as locks:
            def guard():
                # Workers are stopped; producer locks remain held through config publication.
                pipeline=ux.pipeline(c);c.worker_home.mkdir(parents=True,exist_ok=True)
                locks.enter_context(pipeline.pipeline_lock(c.worker_home/'inbox.lock'))
                if old:locks.enter_context(pipeline.pipeline_lock(old['audio_dir']/'.ingest.lock'))
                relocation_check()
                validate_directories({k:binding[k] for k in FIELDS},create=create,probe=True,created=created)
                if new:
                    for key in ('audio','raw','ready'):
                        _create_tracked(child(child(c.workspace_root,code),subject['paths'][key]),created)
            # The new course's internal folders do not exist before guard runs.
            manager.apply_config(data,before_commit=guard,defer_new_preflight=True)
    except Exception:
        # Only remove directories created by this attempt, and only after config rollback.
        try:
            rolled_back=(c.path.read_bytes()==c.bytes and
                         (not hasattr(manager,'pending') or manager.pending() is None))
        except (OSError,ValueError):rolled_back=False
        if rolled_back:
            for folder in reversed(created):
                try:folder.rmdir()
                except OSError:pass # A nonempty/raced directory belongs to the user now.
        raise
    finally:probe.unlink(missing_ok=True)
    return code


def view(c):
    from lecture_inbox import Inbox
    state=Inbox(c).status();groups={g['group_id']:g for g in state['groups']}
    items=[]
    for g in groups.values():
        found=[state_row.get('part_hint') for sid in g['member_ids'] for state_row in state['sources'] if state_row['source_id']==sid]
        items.append(dict(g,id=g['group_id'],kind='group',name=g['session_stem'],parts=found))
    for r in state['sources']:
        g=groups.get(r.get('group_id'))
        if r['status']=='superseded':continue
        if g and r['source_id'] in g['member_ids']:continue
        items.append(dict(r,id=r['source_id'],kind='source',name=Path(r['source_path']).name,parts=[r.get('part_hint')]))
    courses=[];bindings={r['course_id']:r for r in state['courses']}
    for code,s in c.subjects().items():
        b=bindings.get(code,{});related=[r for r in items if r['course_id']==code]
        try:last_scan=datetime.fromisoformat(b['last_scan']).astimezone().strftime('%d.%m %H:%M')
        except (KeyError,ValueError,TypeError):last_scan='Ещё не сканировалось'
        courses.append(dict(id=code,name=s['title'],status='Включён' if b.get('enabled') else 'Выключен / не настроен',
            pending=sum(r['status']!='completed' for r in related),last_scan=last_scan,
            problems=sum(r['status'] in ('review','failed') for r in related)+(1 if b.get('error') else 0),error=b.get('error')))
    for r in items:r['status_text']=STATUS.get(r['status'],'Требуется проверка')
    return dict(courses=courses,items=items)
