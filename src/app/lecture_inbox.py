"""Local course intake producer. READY and existing worker/AI ledgers own processing.

Scans never hash audio. A settled source is copied/sealed by human_ux.add_lecture.
No source moves/deletes, ASR engine, background service or new processing queue.
"""
import argparse
import copy
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_config import Config, need, read
from ai_queue import atomic
import human_ux
import lecture_dates


def hints(name, override=None):
    stem=Path(name).stem
    matches=list(lecture_dates.PATTERN.finditer(stem))
    tail=stem[matches[-1].end():] if matches else stem
    part = re.search(r'(?:[_ -](?:part|pt|p)?|part)(\d{1,3})$', tail, re.I)
    base=stem[:len(stem)-len(tail)+part.start()].rstrip(' _-') if part else stem
    session=unicodedata.normalize('NFC',base).casefold().strip()
    # Date-masked family is ONLY an ambiguity guard, never a merge key.
    family=lecture_dates.PATTERN.sub('{date}',session)
    resolved=lecture_dates.filename(name)
    if override is not None:resolved=lecture_dates.resolve([resolved],override=override)
    return dict(resolved,
                part_hint=int(part[1]) if part and int(part[1]) > 0 else None, recorded_at=None,
                session_stem=session, session_family=family)


def identity(workspace, course, path, signature):
    # Metadata generation, not a content digest: renamed/copied dedup is deferred.
    value = [workspace, course, os.path.normcase(str(path.resolve())), signature['size'], signature['mtime_ns']]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode('utf8')).hexdigest()


class Inbox:
    def __init__(self, config, monotonic=time.monotonic, now=None):
        self.config = config
        self.clock = monotonic
        self.now = now or (lambda: datetime.now(timezone.utc).isoformat())
        self.observed = {}  # Restart always requires fresh stability observations.
        self.last = {}
        self.group_observed = {}
        self.path = config.worker_home/'inbox.json'
        self.marker = config.worker_home/'inbox.initialized'

    def load(self):
        if not self.path.exists():
            need(not self.marker.exists(), 'Inbox journal missing; restore it, do not reset dedup')
            return dict(schema_version=1, sources={}, courses={})
        state = read(self.path)
        need(state.get('schema_version') == 1 and isinstance(state.get('sources'), dict)
             and isinstance(state.get('courses'), dict), 'Invalid Inbox journal; no automatic reset')
        for key, row in state['sources'].items():
            need(isinstance(row,dict) and key == row.get('source_id') and
                 row.get('status') in {'waiting_stable','waiting_parts','review','ready','queued','failed','superseded'}, 'Invalid Inbox source')
        state.setdefault('groups',{})
        need(isinstance(state['groups'],dict),'Invalid Inbox groups')
        return state

    def save(self, state):
        atomic(self.path, state)
        if not self.marker.exists():
            self.marker.write_text('1', encoding='ascii')

    def scan(self):
        c = self.config; c.assert_current(); courses = c.courses()
        if not any(x['enabled'] for x in courses.values()):
            return self.status()
        c.worker_home.mkdir(parents=True, exist_ok=True)
        p = human_ux.pipeline(c)
        with p.pipeline_lock(c.worker_home/'inbox.lock'):
            state = self.load()
            for code, course in courses.items():
                if not course['enabled'] or self.clock()-self.last.get(code, -float('inf')) < course['poll_seconds']:
                    continue
                self.last[code] = self.clock()
                info = state['courses'].setdefault(code, {})
                info.update(last_scan=self.now(), error=None)
                try:
                    source = course['source_audio_folder']
                    need(source.is_dir() and not source.is_symlink(), 'Source folder unavailable: '+str(source))
                    multipart=[]
                    for path in sorted(source.iterdir()):
                        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in p.AUDIO_EXTENSIONS:
                            continue
                        signature = p.source_signature(path)
                        sid = identity(c.active, code, path, signature)
                        row = state['sources'].get(sid)
                        if row is None:
                            for previous in state['sources'].values():
                                if previous['course_id']==code and previous['source_path']==str(path.resolve()) and previous['status'] in ('waiting_stable','waiting_parts','review') and not previous.get('lecture_key'):
                                    previous['status']='superseded';self.observed.pop(previous['source_id'],None)
                            row = dict(source_id=sid, course_id=code, source_path=str(path.resolve()),
                                       signature=signature, imported_at=self.now(), status='waiting_stable', **hints(path.name))
                            prior=[r for r in state['sources'].values() if r['course_id']==code and os.path.normcase(r['source_path'])==os.path.normcase(str(path.resolve())) and
                                   (r.get('lecture_key') or state.get('groups',{}).get(r.get('group_id'),{}).get('lecture_key'))]
                            if prior:row.update(status='review',review_required=True,error='changed_source_requires_review: исходник изменён после резервирования/публикации')
                            state['sources'][sid] = row
                            self.save(state)
                        if row.pop('reset_stability',False):self.observed.pop(sid,None)
                        if row.get('review_required'):continue
                        if row.get('part_hint') is not None:
                            row.update({k:v for k,v in hints(path.name).items() if k in ('session_stem','session_family')})
                            multipart.append(row)
                            continue
                        if row['status'] in ('queued','failed'):
                            continue
                        # A committed READY is enough to replay a lost intake acknowledgement.
                        key = row.get('lecture_key')
                        if key and p.ready_path(c.subjects()[code],key).exists():
                            human_ux.add_lecture(c,code,row['lecture_date'],None,[path],intake=row)
                            row['status']='queued';row.pop('error',None);self.save(state);continue
                        old = self.observed.get(sid)
                        if old is None:
                            old = [self.clock(),0]; self.observed[sid] = old
                        old[1] += 1
                        if signature['size'] <= 0 or old[1] < course['stable_observations'] or self.clock()-old[0] < course['settle_seconds']:
                            continue
                        if row['lecture_date'] is None:
                            row['status']='review';row['error']='Конфликт дат; требуется ручная проверка' if row.get('date_resolution')=='conflict' else 'Дата неизвестна; требуется ручная проверка'
                            continue
                        try:
                            # Reuse Windows deny-writer access from the existing worker.
                            from lecture_worker import closed_writer_read
                            with closed_writer_read(path) as stream:
                                stream.read(1)
                                need(p.source_signature(path)==signature,'Source changed before handoff')
                                row['status']='ready';self.save(state)
                                def reserve(key):
                                    row['lecture_key']=key;self.save(state)
                                key=human_ux.add_lecture(c,code,row['lecture_date'],None,[path],intake=row,reserve=reserve)
                                row.update(status='queued',lecture_key=key);row.pop('error',None)
                                self.save(state)
                        except OSError as error:
                            # Includes an open writer/sharing violation: restart settling.
                            self.observed.pop(sid,None);row.update(status='waiting_stable',error=str(error))
                        except human_ux.SourceReview as error:
                            row.update(status='review',review_required=True,error=str(error))
                        except (ValueError,KeyError) as error:
                            row.update(status='failed',error=str(error))
                    self.multipart(state,code,course,multipart)
                except (OSError, ValueError) as error:
                    info['error']=str(error)
                self.save(state)
        return self.status()

    def multipart(self,state,code,course,rows):
        """Accumulate intake only; one ordered add_lecture call seals each session."""
        c=self.config;p=human_ux.pipeline(c);groups=state.setdefault('groups',{})
        candidates={}
        for row in rows:
            stem=row['session_stem']
            gid=hashlib.sha256(json.dumps([c.active,code,str(course['source_audio_folder']),stem],ensure_ascii=False).encode()).hexdigest()
            candidates.setdefault(gid,[]).append(row)
        # Missing/renamed members invalidate a pending group, even after restart.
        for gid,g in groups.items():
            if g['course_id']==code and g['status']!='queued' and gid not in candidates:
                if any(state['sources'][sid].get('review_required') for sid in g['member_ids']):continue
                g.update(status='review',error='Исходные части группы отсутствуют')
                self.group_observed.pop(gid,None)
        families={}
        for row in rows:
            if row['status']!='queued':
                families.setdefault(row['session_family'],{}).setdefault(row['session_stem'],set()).add(row['part_hint'])
        for gid,items in candidates.items():
            items.sort(key=lambda r:(r['part_hint'],r['source_path']))
            g=groups.setdefault(gid,dict(source_id=gid,group_id=gid,course_id=code,
                session_stem=items[0]['session_stem'],status='waiting_parts',member_ids=[],
                imported_at=min(r['imported_at'] for r in items),recorded_at=None))
            ids=[r['source_id'] for r in items]
            if g.pop('reset_stability',False):self.group_observed.pop(gid,None)
            def mark(status,error=None):
                g.update(status=status,error=error)
                for r in items:
                    if r['status']!='queued':r.update(status=status,error=error,group_id=gid)
            if g['status']=='queued':
                for r in items:
                    if r['source_id'] not in g['member_ids']:
                        r.update(status='review',group_id=gid,error='Поздняя/изменённая часть уже опубликованной группы')
                continue
            # Old Phase 3a single-part publication must never be silently regrouped.
            if any(r['status']=='queued' or (r.get('lecture_key') and not r.get('group_id')) for r in items):
                mark('review','Часть уже импортирована отдельно; требуется ручная проверка');continue
            if g.get('lecture_key') and g['member_ids']!=ids:
                mark('review','Набор частей изменился после начала handoff');continue
            # Recovery uses exactly the common READY acknowledgement replay.
            if g.get('lecture_key') and p.ready_path(c.subjects()[code],g['lecture_key']).exists():
                try:
                    human_ux.add_lecture(c,code,g['lecture_date'],None,[Path(r['source_path']) for r in items],intake=g)
                    mark('queued')
                    for r in items:r['lecture_key']=g['lecture_key']
                    self.save(state)
                except (OSError,ValueError,KeyError) as error:mark('review',str(error))
                continue
            changed=g['member_ids']!=ids
            present={r['source_path'] for r in items}
            if any(state['sources'][sid]['source_path'] not in present for sid in g['member_ids']):
                self.group_observed.pop(gid,None)
                mark('review','Ранее обнаруженная часть отсутствует');continue
            if changed:
                g['member_ids']=ids;self.group_observed.pop(gid,None);mark('waiting_parts')
            stable=True
            for row in items:
                observed=self.observed.setdefault(row['source_id'],[self.clock(),0]);observed[1]+=1
                if row['signature']['size']<=0 or observed[1]<course['stable_observations'] or self.clock()-observed[0]<course['settle_seconds']:
                    stable=False
            if not stable:
                self.group_observed.pop(gid,None)
                if g['status']!='review':mark('waiting_parts')
                continue
            try:
                from lecture_worker import closed_writer_read
                with ExitStack() as stack:
                    for row in items:
                        path=Path(row['source_path']);stack.enter_context(closed_writer_read(path)).read(1)
                        need(p.source_signature(path)==row['signature'],'Часть изменяется')
                    quiet=self.group_observed.setdefault(gid,self.clock())
                    if self.clock()-quiet<course['settle_seconds']:
                        if g['status']!='review':mark('waiting_parts')
                        continue
                    numbers=[r['part_hint'] for r in items]
                    resolved=lecture_dates.resolve(items,imported_at=g['imported_at'])
                    g.update(resolved)
                    error=None
                    # Reused course prefixes are normal across dates. Overlapping
                    # part numbers distinguish those independent sessions; disjoint
                    # dated fragments still require review rather than guessing.
                    siblings=families[items[0]['session_family']]
                    ambiguous=any(stem!=g['session_stem'] and set(numbers).isdisjoint(parts)
                                  for stem,parts in siblings.items())
                    if ambiguous or resolved['date_resolution']=='conflict':
                        error='Конфликт дат частей; требуется ручная проверка'
                    elif resolved['lecture_date'] is None:error='Дата неизвестна; требуется ручная проверка'
                    elif len(set(numbers))!=len(numbers):error='Повторяющийся номер части'
                    elif numbers!=list(range(1,(g.get('expected_parts') or max(numbers))+1)):error='Неполная группа: состав не совпадает с ожидаемыми частями' if g.get('expected_parts') else 'Неполная группа: пропущены части'
                    if error:mark('review',error);continue
                    g.update(members=[{k:r[k] for k in ('source_id','source_path','signature','part_hint')} for r in items])
                    mark('ready');self.save(state)
                    def reserve(key):
                        g['lecture_key']=key;self.save(state)
                    key=human_ux.add_lecture(c,code,g['lecture_date'],None,[Path(r['source_path']) for r in items],intake=g,reserve=reserve)
                    mark('queued')
                    for r in items:r['lecture_key']=key
                    self.save(state)
            except OSError as error:
                self.group_observed.pop(gid,None);mark('waiting_parts',str(error))
            except human_ux.SourceReview as error:
                mark('review',str(error))
                for r in items:r['review_required']=True
            except (ValueError,KeyError) as error:mark('review',str(error))

    def review(self,identity,*,lecture_date=None,expected_parts=None,retry=False):
        """Explicit user override before publication, serialized with the producer."""
        c=self.config;c.assert_current();p=human_ux.pipeline(c)
        c.worker_home.mkdir(parents=True,exist_ok=True)
        with p.pipeline_lock(c.worker_home/'inbox.lock'):
            state=self.load();group=state.get('groups',{}).get(identity)
            row=group or state['sources'].get(identity)
            need(row is not None,'Запись больше не существует')
            need(not row.get('review_required') and not any(state['sources'][sid].get('review_required') for sid in row.get('member_ids',[])),
                 'Нужна ручная проверка изменённого или повторного источника; повторный импорт не разрешён')
            owner=state.get('groups',{}).get(row.get('group_id'))
            need(row['status']!='queued' and not (owner and owner['status']=='queued'),'Лекция уже передана. Поздние части требуют ручной проверки.')
            need(not row.get('lecture_key') or (lecture_date is None and expected_parts is None),'Передача уже началась: дату и состав менять нельзя')
            members=[state['sources'][sid] for sid in group['member_ids']] if group else [row]
            targets=[row,*[r for r in members if r is not row]]
            if lecture_date is not None:
                for r in targets:
                    r.update(lecture_dates.resolve([r],override=lecture_date,imported_at=r.get('imported_at')))
            if expected_parts is not None:
                need(group is not None,'Число частей задаётся только для группы')
                need(type(expected_parts) is int and 0<=expected_parts<=999,'Число частей: Auto или 1–999')
                row['expected_parts']=expected_parts or None
            need(retry or lecture_date is not None or expected_parts is not None,'Выберите действие')
            for r in targets:
                r.update(status='waiting_parts' if group else 'waiting_stable',reset_stability=True);r.pop('error',None)
            self.save(state)
        return 'Изменения сохранены. Worker повторно проверит исходные файлы.'

    def status(self):
        state = self.load(); c = self.config
        processing = read(c.state)['lectures']
        workers = read(c.worker_home/'worker_jobs.json').get('jobs',{}) if (c.worker_home/'worker_jobs.json').exists() else {}
        ai = read(c.queue_home/'queue.json').get('tasks',{}) if (c.queue_home/'queue.json').exists() else {}
        rows=[]
        for item in state['sources'].values():
            row=dict(item);key=row['course_id']+'/'+row.get('lecture_key','')
            if row['status']=='queued':
                task=ai.get(c.active+'/'+key,{})
                if task.get('status')=='completed':row['status']='completed'
                elif processing.get(key,{}).get('status') in ('completed','done'):row['status']=task.get('status','waiting_ai')
                elif workers.get(key,{}).get('phase') in ('transcribing','publishing'):row['status']='processing'
                elif workers.get(key,{}).get('phase')=='error':row['status']='failed'
            rows.append(row)
        courses=[]
        for code,course in c.courses().items():
            courses.append(dict(course_id=code,display_name=course['display_name'],enabled=course['enabled'],
                source_audio_folder=str(course['source_audio_folder']),output_folder=str(course['output_folder']) if course['output_folder'] else None,
                raw_output_folder=str(course['raw_output_folder']),final_output_folder=str(course['final_output_folder']),
                archive_audio_folder=str(course['archive_audio_folder']) if course['archive_audio_folder'] else None,
                **state['courses'].get(code,{}),pending_count=sum(r['course_id']==code and r['status'] not in ('completed','superseded') for r in rows)))
        groups=[]
        for item in state.get('groups',{}).values():
            group=dict(item)
            if group['status']=='queued':
                member=next((r for r in rows if r.get('group_id')==group['group_id'] and r.get('lecture_key')==group.get('lecture_key')),None)
                if member:group['status']=member['status']
            groups.append(group)
        return dict(courses=courses,sources=rows,groups=groups)


def bind(config, course, source, output, archive=None, enabled=True, settle=120, poll=10):
    """Explicit configuration operation; refuses running worker and output relocation."""
    c=config;p=human_ux.pipeline(c);c.worker_home.mkdir(parents=True,exist_ok=True)
    with p.pipeline_lock(c.worker_home/'lecture_pipeline.lock'), p.pipeline_lock(c.worker_home/'inbox.lock'):
        c.assert_current();data=copy.deepcopy(c.data)
        subject=next((s for s in data['workspaces'][c.active]['subjects'] if s['subject_code']==course),None)
        need(subject is not None,'Create/select an existing subject/course first')
        old=c.subjects()[course]
        output=Path(output).resolve()
        if output/'raw' != old['raw_dir']:
            need(not any(old['audio_dir'].iterdir()) and not any(old['raw_dir'].iterdir()) and not any(old['ready_dir'].iterdir())
                 and not any(k.startswith(course+'/') for k in read(c.state)['lectures']),
                 'Course already has audio/results; output migration is not part of Inbox')
            need(not output.exists() or not any(output.iterdir()),'Select a new empty output folder')
        subject['inbox']=dict(enabled=enabled,source_audio_folder=str(Path(source).resolve()),output_folder=str(output),
            archive_audio_folder=str(Path(archive).resolve()) if archive else None,settle_seconds=settle,poll_seconds=poll)
        # Validate in memory via an owned sibling config; never publish invalid bytes.
        temporary=c.path.with_name(c.path.name+'.inbox-validation')
        need(not temporary.exists(),'Stale binding validation file; inspect before retry')
        try:
            atomic(temporary,data);Config(temporary)
            (output/'raw').mkdir(parents=True,exist_ok=True);(output/'word').mkdir(exist_ok=True)
            c.assert_current();atomic(c.path,data)
        finally:
            temporary.unlink(missing_ok=True)
    return Config(c.path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('command',choices=['scan','status','bind'])
    parser.add_argument('--course');parser.add_argument('--source');parser.add_argument('--output');parser.add_argument('--archive')
    parser.add_argument('--disabled',action='store_true');parser.add_argument('--settle',type=int,default=120);parser.add_argument('--poll',type=int,default=10)
    a=parser.parse_args();c=Config(a.config)
    if a.command=='bind':
        need(a.course and a.source and a.output,'bind requires --course, --source and --output')
        c=bind(c,a.course,a.source,a.output,a.archive,not a.disabled,a.settle,a.poll)
    inbox=Inbox(c)
    print(json.dumps(inbox.scan() if a.command=='scan' else inbox.status(),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
