import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_local_finalize import fixture, dump
from pipeline_config import Config
import human_ux as ux
from lecture_inbox import Inbox, bind, hints


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.c=fixture(self.base)
        self.source=self.base/'Audio 课程';self.source.mkdir()
        self.c=bind(self.c,'SUBJECT',self.source,self.base/'Results 课程',settle=10,poll=5)
        self.time=0
        self.new_inbox()

    def new_inbox(self):
        self.inbox=Inbox(self.c,monotonic=lambda:self.time,now=lambda:'2026-10-10T10:00:00+00:00')

    def scan(self,seconds=5):
        self.time+=seconds
        return self.inbox.scan()

    def settled(self):
        self.scan();self.scan();return self.scan()

    def test_parser_hints_and_unknown(self):
        for stamp in ('2026_09_11','2026-09-11','20260911'):
            self.assertEqual(hints(stamp+'.m4a')['lecture_date'],'2026-09-11')
            self.assertIsNone(hints(stamp+'.m4a')['part_hint'])
            self.assertEqual(hints('微观'+stamp+'_2.m4a')['part_hint'],2)
        self.assertEqual(hints('微观 第4次 2026-10-16_part2.m4a')['part_hint'],2)
        self.assertIsNone(hints('recording.m4a')['lecture_date'])
        self.assertIsNone(hints('2026-02-30.m4a')['lecture_date'])
        self.assertEqual(hints('2026-09-11.wav','2026-09-12')['lecture_date_source'],'explicit')

    def test_binding_dates_queue_repeated_scan_and_restart(self):
        for name in ('3- 2026_09_11_1.m4a','微观2026_10_09_1.m4a'):
            (self.source/name).write_bytes(b'fixture audio')
        result=self.settled();rows=result['sources']
        self.assertEqual({r['course_id'] for r in rows},{'SUBJECT'})
        self.assertEqual({r['lecture_date'] for r in rows},{'2026-09-11','2026-10-09'})
        self.assertTrue(all(r['status']=='queued' and r['imported_at'].startswith('2026-10-10') for r in rows))
        p=ux.pipeline(self.c);s=self.c.subjects()['SUBJECT']
        for row in rows:
            ready=p.read_ready(s,row['lecture_key'],p.collect_lectures(s['audio_dir'])[row['lecture_key']])
            self.assertEqual(ready['intake']['source_id'],row['source_id'])
            self.assertEqual(ready['intake']['lecture_date_source'],'filename')
        with patch.object(ux,'add_lecture',side_effect=AssertionError('duplicate')):
            self.scan();self.new_inbox();self.scan()
        self.assertEqual(len(list(s['audio_dir'].glob('*.READY.json'))),2)
        self.assertEqual(len(list(self.source.iterdir())),2)

    def test_changing_file_and_open_writer_never_queue(self):
        file=self.source/'20261009_1.wav';file.write_bytes(b'a')
        self.scan();file.write_bytes(b'changed');self.scan();self.scan()
        self.assertFalse(list(self.c.subjects()['SUBJECT']['audio_dir'].glob('*.READY.json')))
        with file.open('ab'):
            result=self.scan()
            self.assertFalse(any(r['status']=='queued' for r in result['sources']))
        self.settled()
        self.assertEqual(len(list(self.c.subjects()['SUBJECT']['audio_dir'].glob('*.READY.json'))),1)

    def test_restart_requires_fresh_stability(self):
        (self.source/'20261009.wav').write_bytes(b'fixture')
        self.scan();self.scan();self.new_inbox()
        self.assertEqual(self.scan()['sources'][0]['status'],'waiting_stable')
        self.scan();self.assertEqual(self.scan()['sources'][0]['status'],'queued')

    def test_unknown_is_review_not_import_date(self):
        (self.source/'unfamiliar.wav').write_bytes(b'fixture')
        row=self.settled()['sources'][0]
        self.assertEqual(row['status'],'review');self.assertIsNone(row['lecture_date'])
        self.assertEqual(row['lecture_date_source'],'unknown');self.assertIsNone(row['recorded_at'])
        self.assertFalse(list(self.c.subjects()['SUBJECT']['audio_dir'].glob('*.READY.json')))

    def test_crash_after_ready_reconciles_without_second_copy(self):
        (self.source/'20261009.wav').write_bytes(b'fixture')
        self.settled()
        journal=json.loads(self.inbox.path.read_text());row=next(iter(journal['sources'].values()));row['status']='ready'
        dump(self.inbox.path,journal);self.new_inbox()
        with patch.object(ux.shutil,'copy2',side_effect=AssertionError('must reuse READY')):
            self.assertEqual(self.scan()['sources'][0]['status'],'queued')

    def test_crash_after_reservation_reuses_key(self):
        (self.source/'20261009.wav').write_bytes(b'fixture')
        self.scan();self.scan()
        with patch.object(ux.shutil,'copy2',side_effect=OSError('interrupted')):
            result=self.scan()
        key=result['sources'][0]['lecture_key'];self.new_inbox()
        result=self.settled()
        self.assertEqual(result['sources'][0]['lecture_key'],key)
        self.assertEqual(result['sources'][0]['status'],'queued')

    def test_missing_journal_fails_closed(self):
        (self.source/'20261009.wav').write_bytes(b'fixture');self.settled()
        self.inbox.path.unlink()
        with self.assertRaisesRegex(ValueError,'journal missing'):self.scan()

    def test_manual_path_and_output_binding(self):
        source=self.base/'manual.wav';source.write_bytes(b'fixture')
        key=ux.add_lecture(self.c,'SUBJECT','2026-09-01',1,[source])
        s=self.c.subjects()['SUBJECT'];p=ux.pipeline(self.c)
        self.assertEqual(s['raw_dir'],self.base/'Results 课程/raw')
        ready=p.read_ready(s,key,p.collect_lectures(s['audio_dir'])[key])
        self.assertEqual(ready['intake']['lecture_date_source'],'explicit')
        with self.assertRaisesRegex(ValueError,'migration'):
            bind(self.c,'SUBJECT',self.source,self.base/'Other')

    def test_intake_provenance_reaches_existing_asr_manifest_and_ai_packet(self):
        from types import SimpleNamespace
        import ai_queue
        (self.source/'微观2026_10_09_1.wav').write_bytes(b'fixture')
        row=self.settled()['sources'][0];p=ux.pipeline(self.c);s=self.c.subjects()['SUBJECT'];key=row['lecture_key']
        with patch.object(p,'transcribe_one',return_value=([(0,1,'测试内容')],SimpleNamespace(language='zh'))),patch.object(p,'safe_print'):
            p.process_lecture(object(),'SUBJECT',s,key,p.collect_lectures(s['audio_dir'])[key],
                              p.load_state(self.c.state),self.c.state,self.base/'test.log')
        manifest=json.loads((s['raw_dir']/key/(key+'_manifest.json')).read_text(encoding='utf8'))
        self.assertEqual(manifest['intake']['source_id'],row['source_id'])
        task=ai_queue.refresh(self.c)['tasks'][self.c.active+'/SUBJECT/'+key]
        self.assertEqual(task['lecture_date'],'2026-10-09')
        self.assertEqual(task['lecture_date_source'],'filename')
        self.assertEqual(task['status'],'waiting_ai')

    def test_legacy_disabled_and_overlap_rejected(self):
        data=copy.deepcopy(self.c.data);data['workspaces'][self.c.active]['subjects'][0].pop('inbox');dump(self.c.path,data)
        self.assertEqual(Config(self.c.path).courses(),{})
        with self.assertRaisesRegex(ValueError,'пересек'):
            bind(Config(self.c.path),'SUBJECT',self.source,self.source)

    def test_display_name_and_source_rebind_keep_course_identity(self):
        data=copy.deepcopy(self.c.data);data['workspaces'][self.c.active]['subjects'][0]['subject_name']='中级微观经济学';dump(self.c.path,data)
        renamed=self.base/'Renamed';self.source.rename(renamed)
        self.c=bind(Config(self.c.path),'SUBJECT',renamed,self.base/'Results 课程')
        self.assertEqual(self.c.courses()['SUBJECT']['display_name'],'中级微观经济学')
        self.assertEqual(self.c.courses()['SUBJECT']['course_id'],'SUBJECT')


if __name__=='__main__':unittest.main()
