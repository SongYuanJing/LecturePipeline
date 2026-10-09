import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from test_local_finalize import fixture,dump,APP,lecture
sys.path.insert(0,str(APP/'gui_v1.8'))
from adapter import Manager
from pipeline_config import Config
import course_setup as cs
import human_ux as ux
from lecture_inbox import Inbox,bind


class FixtureControls:
    """No OS tasks are touched by disposable acceptance fixtures."""
    def __init__(self,c):self.c=c
    def states(self):return {k:dict(running=False) for k in ('lecture','dialogue')}
    def action(self,*a):pass
    def wait_stopped(self,*a):pass
    def restore(self,*a):pass
    def confirm_started(self,*a):pass


def manager(c):return Manager(c.path,FixtureControls,lambda c:dict(ok=True,checks=[]))


def university(root):
    paths=dict(zip(cs.FIELDS,map(str,(root/'00 — Входящие',root/'02 — Конспекты и разборы/00 — Аудио лекций',
        root/'02 — Конспекты и разборы/01 — Черновые расшифровки',root/'02 — Конспекты и разборы/02 — Готовые лекции'))))
    for value in paths.values():Path(value).mkdir(parents=True)
    return paths


class CourseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.c=fixture(self.root);self.mapping=cs.recommended(self.root/'Drive Desktop 大学')

    def save(self,**kw):
        code=cs.save_course(self.c,manager(self.c),'微观',self.mapping,create=True,**kw);self.c=Config(self.c.path);return code

    def test_legacy_output_mapping(self):
        source=self.root/'source';source.mkdir();c=bind(self.c,'SUBJECT',source,self.root/'out')
        self.assertEqual(c.subjects()['SUBJECT']['raw_dir'],self.root/'out/raw')
        self.assertEqual(c.subjects()['SUBJECT']['ready_dir'],self.root/'out/word')
        self.assertEqual(c.subjects()['SUBJECT']['notes_dir'],self.root/'out')
        from adapter import safe_open
        safe_open(c,self.root/'out',opener=lambda p:None)

    def test_split_precedence_and_partial_rejected(self):
        code=self.save();data=self.c.data;subject=next(s for s in data['workspaces'][self.c.active]['subjects'] if s['subject_code']==code)
        subject['inbox']['output_folder']=str(self.root/'ignored');dump(self.c.path,data)
        self.assertEqual(Config(self.c.path).subjects()[code]['raw_dir'],Path(self.mapping['raw_output_folder']))
        del subject['inbox']['final_output_folder'];dump(self.c.path,data)
        with self.assertRaises(ValueError):Config(self.c.path)

    def test_split_actual_raw_and_word_finalize(self):
        cs.save_course(self.c,manager(self.c),'微观',self.mapping,course_id='SUBJECT',create=True);c=Config(self.c.path)
        source=self.root/'input.wav';source.write_bytes(b'audio');p=ux.pipeline(c)
        key=ux.add_lecture(c,'SUBJECT','2026-10-09',1,[source]);s=c.subjects()['SUBJECT']
        with patch.object(p,'transcribe_one',return_value=([(0,1,'测试内容')],SimpleNamespace(language='zh'))),patch.object(p,'safe_print'):
            p.process_lecture(object(),'SUBJECT',s,key,p.collect_lectures(s['audio_dir'])[key],p.load_state(c.state),c.state,self.root/'log')
        self.assertTrue((Path(self.mapping['raw_output_folder'])/key/(key+'_manifest.json')).is_file())
        import ai_finalize
        identity,content,_=lecture(c,'02_2026-10-09')
        result=ai_finalize.finalize(c,identity,content)
        self.assertTrue(Path(result['word']).is_relative_to(Path(self.mapping['final_output_folder'])))

    def test_name_and_safe_mapping_keep_identity(self):
        code=self.save();self.mapping=cs.recommended(self.root/'Elsewhere')
        cs.save_course(self.c,manager(self.c),'Новое имя',self.mapping,course_id=code,create=True)
        c=Config(self.c.path);self.assertIn(code,c.subjects());self.assertEqual(c.subjects()[code]['title'],'Новое имя')

    def test_relocation_with_data_rejected(self):
        code=self.save();(self.c.subjects()[code]['raw_dir']/'keep').write_text('keep')
        before=self.c.path.read_bytes();other=cs.recommended(self.root/'other')
        with self.assertRaisesRegex(ValueError,'Перенос'):cs.save_course(self.c,manager(self.c),'x',other,course_id=code,create=True)
        self.assertEqual(before,self.c.path.read_bytes());self.assertFalse((self.root/'other').exists())

    def test_readonly_detector_and_ambiguity(self):
        root=self.root/'university';mapping=university(root)
        before={str(p):p.stat().st_mtime_ns for p in root.rglob('*')}
        self.assertEqual(cs.detect(root),mapping)
        self.assertEqual(before,{str(p):p.stat().st_mtime_ns for p in root.rglob('*')})
        (root/'00 — Входящие вторая').mkdir();self.assertIsNone(cs.detect(root))

    def test_preview_create_partial_idempotent(self):
        self.assertFalse(Path(self.mapping['source_audio_folder']).exists())
        Path(self.mapping['source_audio_folder']).mkdir(parents=True)
        keep=Path(self.mapping['source_audio_folder'])/'keep.txt';keep.write_text('keep');stamp=keep.stat().st_mtime_ns
        code=self.save();cs.save_course(self.c,manager(self.c),'微观',self.mapping,course_id=code,create=True)
        self.assertEqual(keep.read_text(),'keep');self.assertEqual(stamp,keep.stat().st_mtime_ns)
        self.assertTrue(all(Path(p).is_dir() for p in self.mapping.values()))
        self.assertFalse(list((self.root/'Drive Desktop 大学').rglob('.lp-write-probe-*')))

    def test_existing_manual_missing_no_creation(self):
        before=self.c.path.read_bytes()
        with self.assertRaises(ValueError):cs.save_course(self.c,manager(self.c),'x',self.mapping)
        self.assertEqual(before,self.c.path.read_bytes());self.assertFalse((self.root/'Drive Desktop 大学').exists())

    def test_existing_file_collision_no_partial_creation(self):
        root=self.root/'Drive Desktop 大学';root.mkdir();(root/'Lectures').write_text('keep')
        with self.assertRaises(ValueError):self.save()
        self.assertFalse((root/'Inbox').exists());self.assertEqual((root/'Lectures').read_text(),'keep')

    def test_unsafe_paths(self):
        for bad in (self.mapping['source_audio_folder'],str(Path(self.mapping['source_audio_folder'])/'child'),str(self.c.home),str(self.c.worker_home)):
            with self.subTest(bad=bad):
                m=dict(self.mapping,final_output_folder=bad)
                with self.assertRaises(ValueError):cs.save_course(self.c,manager(self.c),'x',m,create=True)
        m=dict(self.mapping,source_audio_folder='relative')
        with self.assertRaises(ValueError):cs.save_course(self.c,manager(self.c),'x',m,create=True)

    def test_write_failure_does_not_commit_config(self):
        before=self.c.path.read_bytes()
        with patch.object(cs.tempfile,'NamedTemporaryFile',side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):self.save()
        self.assertEqual(before,self.c.path.read_bytes())

    def test_producer_lock_blocks_config_save(self):
        code=self.save();before=self.c.path.read_bytes();p=ux.pipeline(self.c);self.c.worker_home.mkdir(parents=True,exist_ok=True)
        with p.pipeline_lock(self.c.worker_home/'inbox.lock'):
            with self.assertRaises(RuntimeError):cs.save_course(self.c,manager(self.c),'rename',self.mapping,course_id=code)
        self.assertEqual(before,self.c.path.read_bytes())

    def test_override_retry_expected_and_status(self):
        code=self.save();data=self.c.data;s=next(s for s in data['workspaces'][self.c.active]['subjects'] if s['subject_code']==code)
        s['inbox'].update(settle_seconds=10,poll_seconds=5);dump(self.c.path,data);c=Config(self.c.path)
        clock=[0];inbox=Inbox(c,monotonic=lambda:clock[0]);source=Path(self.mapping['source_audio_folder'])
        (source/'unknown.wav').write_bytes(b'audio')
        def scan(n):
            for _ in range(n):clock[0]+=5;r=inbox.scan()
            return r
        r=scan(3);row=r['sources'][0];self.assertEqual(cs.view(c)['items'][0]['status_text'],'Нужна проверка')
        inbox.review(row['source_id'],lecture_date='2026-10-08');r=scan(3)
        self.assertEqual(r['sources'][0]['lecture_date_source'],'explicit')
        self.assertEqual(r['sources'][0]['status'],'queued')
        with self.assertRaises(ValueError):inbox.review(row['source_id'],retry=True)
        (source/'foo20261009_1.wav').write_bytes(b'one');r=scan(1);gid=r['groups'][0]['group_id']
        inbox.review(gid,expected_parts=3,retry=True);r=scan(5)
        self.assertEqual(r['groups'][0]['status'],'review');self.assertIn('ожидаемыми',r['groups'][0]['error'])
        for n in (2,3):(source/f'foo20261009_{n}.wav').write_bytes(str(n).encode())
        inbox.review(gid,retry=True);r=scan(5);self.assertEqual(r['groups'][0]['status'],'queued')
        self.assertEqual(len(list(c.subjects()[code]['audio_dir'].glob('*.READY.json'))),2)

    def test_manager_rollback_after_guard_failure(self):
        before=self.c.path.read_bytes();data=copy.deepcopy(self.c.data)
        with self.assertRaises(RuntimeError):manager(self.c).apply_config(data,before_commit=lambda:(_ for _ in ()).throw(ValueError('changed')))
        self.assertEqual(before,self.c.path.read_bytes())

    def test_permanent_intake_failure_explicit_retry(self):
        code=self.save();data=self.c.data
        next(s for s in data['workspaces'][self.c.active]['subjects'] if s['subject_code']==code)['inbox'].update(settle_seconds=10,poll_seconds=5)
        dump(self.c.path,data);c=Config(self.c.path);clock=[0];inbox=Inbox(c,monotonic=lambda:clock[0])
        (Path(self.mapping['source_audio_folder'])/'20261009.wav').write_bytes(b'audio')
        def scan():clock[0]+=5;return inbox.scan()
        scan();scan()
        with patch.object(ux,'add_lecture',side_effect=ValueError('Исправьте входной файл')):result=scan()
        row=result['sources'][0];self.assertEqual(row['status'],'failed')
        self.assertEqual(cs.view(c)['items'][0]['status_text'],'Ошибка')
        inbox.review(row['source_id'],retry=True);scan();scan();result=scan()
        self.assertEqual(result['sources'][0]['status'],'queued')
        self.assertEqual(len(list(c.subjects()[code]['audio_dir'].glob('*.READY.json'))),1)


if __name__=='__main__':unittest.main()
