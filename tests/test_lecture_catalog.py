import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

APP=Path(__file__).resolve().parents[1]/'src/app'
sys.path[:0]=[str(APP),str(APP/'gui_v1.8')]
from pipeline_config import Config,read
import lecture_catalog as catalog


def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')


def fixture(base):
    d=json.loads((APP.parents[1]/'config.example.json').read_text(encoding='utf8'))
    home=base/'Программа';data=base/'Данные 课程';home.mkdir();data.mkdir()
    d.update(install_root='.',data_root=str(data));d.pop('application_home',None)
    template=d['workspaces'][d['active_workspace']]['subjects'][0]
    subjects=[]
    for code,title in [('ECON','Эконометрика'),('MICRO','Микроэкономика'),('RESEARCH','研究方法')]:
        s=copy.deepcopy(template);s.update(subject_code=code,subject_name=title,folder=code,enabled=True);s.pop('inbox',None);subjects.append(s)
    d['workspaces']={d['active_workspace']:{**d['workspaces'][d['active_workspace']],'subjects':subjects}}
    dump(home/'config.json',d);c=Config(home/'config.json')
    for s in c.subjects().values():
        for k in ('audio_dir','raw_dir','ready_dir'):s[k].mkdir(parents=True,exist_ok=True)
    dump(c.state,dict(lectures={}));dump(c.ai_state,dict(schema_version=1,processed={}))
    return c


def add(c,code='ECON',key='01_2026-10-09',stage='done',parts=1):
    s=c.subjects()[code];identity=code+'/'+key;full=c.active+'/'+identity
    files=[];members=[]
    for i in range(1,parts+1):
        name=f'{key}_{i}.wav';p=s['audio_dir']/name;p.write_bytes(b'fixture audio')
        files.append(dict(name=name,size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        members.append(dict(source_path=str(p),part_hint=i))
    metadata=dict(lecture_date=key.split('_',1)[1],lecture_date_source='filename',imported_at='2026-10-10T01:00:00+00:00',recorded_at=None)
    dump(s['audio_dir']/(key+'.READY.json'),dict(lecture=key,files=files,intake=dict(metadata,members=members)))
    if stage=='ready':return identity
    folder=s['raw_dir']/key;folder.mkdir();(folder/'raw.txt').write_text('文本',encoding='utf8');(folder/'part.srt').write_text('fixture srt',encoding='utf8')
    dump(folder/(key+'_manifest.json'),dict(lecture=key,subject_code=code,combined_txt='raw.txt',outputs=[dict(srt='part.srt')],sources=[dict(name=m['name']) for m in files],**metadata))
    state=read(c.state);state['lectures'][identity]=dict(status='completed',**metadata);dump(c.state,state)
    if stage=='raw':return identity
    q=read(c.queue_home/'queue.json') if (c.queue_home/'queue.json').exists() else dict(schema_version=1,tasks={})
    result=c.queue_home/'results'/code/key/'ai_content.json';dump(result,dict(schema_version=1))
    q['tasks'][full]=dict(id=full,workspace=c.active,subject_code=code,lecture_key=key,status=stage if stage in catalog.AI_STATES else 'completed',ai_content=str(result));dump(c.queue_home/'queue.json',q)
    if stage in ('waiting_ai','ai_result_ready','building'):return identity
    out=s['ready_dir']/key;out.mkdir();(out/'lecture.docx').write_bytes(b'fixture docx, presence-only projection')
    ai=read(c.ai_state);ai['processed'][full]=dict(subject_code=code,lecture_id=key,output_docx_local_path=str(out/'lecture.docx'),vocabulary_status='merged');dump(c.ai_state,ai)
    return identity


def fingerprints(base):
    return {str(p.relative_to(base)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in base.rglob('*') if p.is_file()}


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='LP-vic13-test-');self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.c=fixture(self.base)
    def rows(self):return catalog.build(self.c)['items']
    def test_completed_single_one_entity(self):
        add(self.c);rows=self.rows();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'done')
    def test_eight_parts_one_entity_order(self):
        add(self.c,parts=8);r=self.rows()[0];self.assertEqual(r['parts'],8);self.assertEqual([m['part'] for m in r['members']],list(range(1,9)))
    def test_multiple_dates(self):
        add(self.c);add(self.c,key='02_2026-10-10');self.assertEqual(len(self.rows()),2)
    def test_cross_course_same_bytes(self):
        add(self.c);add(self.c,'MICRO');self.assertEqual(len(self.rows()),2)
    def test_ready_without_worker(self):
        add(self.c,stage='ready');self.assertEqual(self.rows()[0]['status'],'ready')
    def test_raw_ai_pending(self):
        add(self.c,stage='waiting_ai');self.assertEqual(self.rows()[0]['status'],'waiting_ai')
    def test_ai_ready_word_pending(self):
        add(self.c,stage='ai_result_ready');self.assertEqual(self.rows()[0]['status'],'ai_ready')
    def test_raw_no_queue(self):
        add(self.c,stage='raw');self.assertEqual(self.rows()[0]['status'],'raw')
    def test_pending_groups_not_lectures(self):
        sources={str(i):dict(course_id='ECON',source_path=f'part{i}.wav',part_hint=i,status='waiting_parts') for i in (1,3)}
        groups={'group':dict(course_id='ECON',session_stem='课程',member_ids=['1','3'],status='review',error='Не хватает части 2',lecture_date=None,date_resolution='conflict')}
        dump(self.c.worker_home/'inbox.json',dict(sources=sources,groups=groups));v=catalog.build(self.c)
        self.assertEqual(v['items'],[]);self.assertEqual(len(v['pending']),1);self.assertEqual(v['pending'][0]['parts'],[1,3]);self.assertIn('2',v['pending'][0]['reason']);self.assertEqual(v['pending'][0]['date_resolution'],'conflict')
    def test_changed_and_copy_review(self):
        sources={reason:dict(course_id='ECON',source_path=reason+'.wav',status='review',review_required=True,error=reason,lecture_date=None) for reason in ('changed_source_requires_review','duplicate_source_requires_review')}
        dump(self.c.worker_home/'inbox.json',dict(sources=sources,groups={}));v=catalog.build(self.c)
        self.assertEqual(len(v['pending']),2);self.assertFalse(v['items'])
    def test_reservation_joins_ready(self):
        add(self.c,stage='ready');dump(self.c.worker_home/'inbox.json',dict(groups={},sources={'s':dict(course_id='ECON',lecture_key='01_2026-10-09',status='queued',source_path='original.wav')}))
        self.assertEqual(len(self.rows()),1)
    def test_legacy_no_migration(self):
        add(self.c);s=self.c.subjects()['ECON'];p=s['raw_dir']/'01_2026-10-09/01_2026-10-09_manifest.json';m=read(p)
        for k in ('lecture_date','lecture_date_source','imported_at','recorded_at'):m.pop(k)
        dump(p,m);r=self.rows()[0];self.assertEqual(r['lecture_date_source'],'legacy');self.assertEqual(r['lecture_date'],'2026-10-09')
    def test_missing_word_problem(self):
        add(self.c);(self.c.subjects()['ECON']['ready_dir']/'01_2026-10-09/lecture.docx').unlink();self.assertEqual(self.rows()[0]['status'],'problem')
    def test_missing_raw_part_problem(self):
        add(self.c);(self.c.subjects()['ECON']['raw_dir']/'01_2026-10-09/part.srt').unlink();self.assertEqual(self.rows()[0]['status'],'problem')
    def test_ambiguous_ai(self):
        add(self.c);ai=read(self.c.ai_state);ai['processed']['duplicate']=next(iter(ai['processed'].values()));dump(self.c.ai_state,ai);self.assertEqual(self.rows()[0]['status'],'problem')
    def test_course_rename_and_disabled(self):
        add(self.c);d=read(self.c.path);s=d['workspaces'][self.c.active]['subjects'][0];s.update(subject_name='Новый курс 新',enabled=False);dump(self.c.path,d)
        r=catalog.build(Config(self.c.path))['items'];self.assertEqual(len(r),1);self.assertEqual(r[0]['course_display_name'],'Новый курс 新')
    def test_rebuild_and_zero_mutation(self):
        add(self.c);before=fingerprints(self.base);first=catalog.build(self.c)
        del first
        second=catalog.build(Config(self.c.path));self.assertEqual(second,catalog.build(self.c));self.assertEqual(before,fingerprints(self.base))
    def test_stale_processing_does_not_override_done(self):
        identity=add(self.c);dump(self.c.worker_home/'worker_jobs.json',dict(jobs={identity:dict(phase='transcribing')}));self.assertEqual(self.rows()[0]['status'],'done')
    def test_word_alone_not_done(self):
        s=self.c.subjects()['ECON'];out=s['ready_dir']/'01_2026-10-09';out.mkdir();(out/'lecture.docx').write_bytes(b'orphan');self.assertEqual(self.rows()[0]['status'],'problem')
    def test_corrupt_authority_surfaces(self):
        add(self.c);self.c.ai_state.write_text('{bad');self.assertEqual(self.rows()[0]['status'],'problem')
    def test_unknown_fields_and_date(self):
        add(self.c,stage='ready');p=self.c.subjects()['ECON']['audio_dir']/'01_2026-10-09.READY.json';r=read(p);r['intake'].update(lecture_date=None,unknown_future=True);dump(p,r)
        self.assertIsNone(self.rows()[0]['lecture_date'])
    def test_filter_sort_unknown_last(self):
        add(self.c);add(self.c,key='02_2026-10-10');add(self.c,'MICRO',stage='ready');rows=self.rows()
        self.assertEqual(len(catalog.filtered(rows,course='ECON')),2);self.assertEqual(len(catalog.filtered(rows,status='ready')),1)
        self.assertEqual(catalog.filtered(rows,newest=False)[0]['lecture_date'],'2026-10-09')
    def test_split_and_legacy_output_mappings(self):
        d=read(self.c.path);subject=d['workspaces'][self.c.active]['subjects'][0]
        subject['inbox']=dict(enabled=False,source_audio_folder=str(self.base/'external/Audio'),output_folder=str(self.base/'external/Output'))
        dump(self.c.path,d);self.c=Config(self.c.path)
        for k in ('raw_dir','ready_dir'):self.c.subjects()['ECON'][k].mkdir(parents=True)
        add(self.c);self.assertEqual(self.rows()[0]['status'],'done')
        b=subject['inbox'];b.update(raw_output_folder=str(self.base/'external/Output/raw'),final_output_folder=str(self.base/'external/Output/word'));b.pop('output_folder');dump(self.c.path,d)
        self.assertEqual(catalog.build(Config(self.c.path))['items'][0]['status'],'done')
    def test_300_entities_performance(self):
        for n in range(1,301):add(self.c,key=f'{n:03d}_2026-10-09',stage='ready')
        start=time.perf_counter();rows=self.rows();elapsed=time.perf_counter()-start
        self.assertEqual(len(rows),300);self.assertLess(elapsed,10);print(f'Catalog 300 entities: {elapsed:.3f}s')

    def test_manual_reservation_only(self):
        s=self.c.subjects()['ECON'];dump(s['audio_dir']/'.manual-handoff-test.json',dict(course_id='ECON',lecture_key='01_2026-10-09',lecture_date='2026-10-09',lecture_date_source='explicit',members=[dict(source_path='original.wav',part_hint=1)]))
        rows=self.rows();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'waiting');self.assertEqual(rows[0]['lecture_date_source'],'explicit')
    def test_missing_initialized_inbox(self):
        add(self.c);self.c.worker_home.mkdir(parents=True);(self.c.worker_home/'inbox.initialized').write_text('1');self.assertEqual(self.rows()[0]['status'],'problem')
    def test_corrupt_manifest_does_not_hide_other_rows(self):
        add(self.c);add(self.c,'MICRO');p=self.c.subjects()['ECON']['raw_dir']/'01_2026-10-09/01_2026-10-09_manifest.json';p.write_text('{bad')
        rows={r['course_id']:r for r in self.rows()};self.assertEqual(rows['ECON']['status'],'problem');self.assertEqual(rows['MICRO']['status'],'done')
    def test_missing_accepted_ai_result(self):
        add(self.c,stage='ai_result_ready');q=read(self.c.queue_home/'queue.json');Path(next(iter(q['tasks'].values()))['ai_content']).unlink();self.assertEqual(self.rows()[0]['status'],'problem')
    def test_unknown_job_phase(self):
        identity=add(self.c,stage='ready');dump(self.c.worker_home/'worker_jobs.json',dict(jobs={identity:dict(phase='future-state')}));self.assertEqual(self.rows()[0]['status'],'problem')
    def test_known_hash_disagreement(self):
        add(self.c);out=self.c.subjects()['ECON']['ready_dir']/'01_2026-10-09';dump(out/'processing_report.json',dict(output_hashes={'lecture.docx':'aaa'}))
        ai=read(self.c.ai_state);next(iter(ai['processed'].values()))['output_provenance']=dict(sha256='bbb');dump(self.c.ai_state,ai);self.assertEqual(self.rows()[0]['status'],'problem')
    def test_legacy_parts_from_outputs_and_ai_ledger(self):
        add(self.c);p=self.c.subjects()['ECON']['raw_dir']/'01_2026-10-09/01_2026-10-09_manifest.json';m=read(p);m.pop('sources');dump(p,m)
        (self.c.subjects()['ECON']['audio_dir']/'01_2026-10-09.READY.json').unlink();(self.c.queue_home/'queue.json').unlink()
        row=self.rows()[0];self.assertEqual(row['parts'],1);self.assertEqual(row['stages']['ai'],'completed');self.assertEqual(row['status'],'done')


if __name__=='__main__':unittest.main()
