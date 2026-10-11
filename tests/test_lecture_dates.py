import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_local_finalize import fixture, dump
import lecture_dates as dates
import human_ux as ux
import ai_queue as aq
import ai_finalize


class DateResolverTests(unittest.TestCase):
    def test_filename_raw(self):
        r=dates.resolve(['foo_2026_10_09_1.m4a'],imported_at='2026-10-10T10:00:00+08:00')
        self.assertEqual((r['lecture_date'],r['lecture_date_source'],r['lecture_date_raw']),('2026-10-09','filename','2026_10_09'))
        self.assertEqual(r['imported_at'],'2026-10-10T02:00:00+00:00')
        self.assertIsNone(r['recorded_at'])

    def test_unknown(self):
        r=dates.resolve(['audio.wav'],imported_at='2026-10-10T00:00:00Z')
        self.assertIsNone(r['lecture_date']);self.assertEqual(r['lecture_date_source'],'unknown')
        self.assertIsNotNone(r['imported_at'])

    def test_explicit_override_conflicting_filename(self):
        r=dates.resolve(['2026_10_09.wav','2026_10_07.wav'],override='2026-10-08')
        self.assertEqual((r['lecture_date'],r['lecture_date_source']),('2026-10-08','explicit'))
        self.assertTrue(r['date_override']);self.assertEqual(len(r['date_evidence']),2)

    def test_multipart_agreement(self):
        r=dates.resolve(['x20261009_1.wav','x20261009_2.wav'])
        self.assertEqual(r['lecture_date'],'2026-10-09')

    def test_conflict_not_majority(self):
        r=dates.resolve(['x20261009_1.wav','x20261009_2.wav','x20261008_3.wav'])
        self.assertEqual(r['date_resolution'],'conflict');self.assertIsNone(r['lecture_date'])

    def test_multiple_dates_in_one_name_conflict(self):
        self.assertEqual(dates.filename('20261009-to-20261008.wav')['date_resolution'],'conflict')

    def test_partial_hints_only_same_session(self):
        rows=['x20261009_1.wav','x_2.wav']
        r=dates.resolve(rows,same_session=True)
        self.assertEqual(r['lecture_date'],'2026-10-09');self.assertIsNone(r['date_evidence'][1]['lecture_date'])
        self.assertIsNone(dates.resolve(rows,same_session=False)['lecture_date'])

    def test_legacy_read_no_mutation(self):
        m={'lecture':'01_2026-10-09'};before=json.dumps(m)
        r=dates.metadata(m)
        self.assertEqual((r['lecture_date'],r['lecture_date_source']),('2026-10-09','legacy'))
        self.assertIsNone(r['imported_at']);self.assertEqual(json.dumps(m),before)
        self.assertIsNone(dates.metadata({'lecture':'unknown'})['lecture_date'])
        self.assertIsNone(dates.metadata({'lecture':'01_2026-10-09','intake':{'lecture_date':None}})['lecture_date'])

    def test_timezone_required(self):
        with self.assertRaises(ValueError):dates.timestamp('2026-10-09T12:00:00')
        self.assertEqual(dates.timestamp('2026-10-09T23:00:00-03:00'),'2026-10-10T02:00:00+00:00')

    def test_strict_calendar(self):
        for value in ('20261009','2026-02-30','today'):
            with self.assertRaises(ValueError):dates.day(value)


class DatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.c=fixture(Path(self.tmp.name));self.code=next(iter(self.c.subjects()))
        os.environ['LECTURE_CONFIG']=str(self.c.path)

    def test_manual_inference_mtime_and_unknown(self):
        source=self.c.home/'foo_2026_10_09_1.wav';source.write_bytes(b'audio')
        os.utime(source,(0,0));p=ux.pipeline(self.c)
        key=ux.add_lecture(self.c,self.code,None,1,[source])
        self.assertEqual(key,'01_2026-10-09')
        s=self.c.subjects()[self.code];r=aq.read(p.ready_path(s,key))['intake']
        self.assertEqual(r['lecture_date_source'],'filename');self.assertNotEqual(r['imported_at'][:10],'1970-01-01')
        unknown=self.c.home/'unknown.wav';unknown.write_bytes(b'audio')
        with self.assertRaisesRegex(ValueError,'ручная проверка'):ux.add_lecture(self.c,self.code,None,2,[unknown])
        self.assertEqual(len(list(s['audio_dir'].glob('*.READY.json'))),1)

    def test_manual_explicit_raw_packet_word_same_date(self):
        source=self.c.home/'foo20261009.wav';source.write_bytes(b'fixture audio')
        key=ux.add_lecture(self.c,self.code,'2026-10-08',1,[source])
        p=ux.pipeline(self.c);s=self.c.subjects()[self.code]
        with patch.object(p,'transcribe_one',return_value=([(0,1,'测试内容')],SimpleNamespace(language='zh'))),patch.object(p,'safe_print'):
            p.process_lecture(object(),self.code,s,key,p.collect_lectures(s['audio_dir'])[key],aq.read(self.c.state),self.c.state,self.c.home/'gate.log')
        manifest=aq.read(s['raw_dir']/key/(key+'_manifest.json'))
        expected=dates.metadata(manifest)
        self.assertEqual(expected['lecture_date'],'2026-10-08')
        identity=self.c.active+'/'+self.code+'/'+key
        task=aq.refresh(self.c)['tasks'][identity];packet=aq.verify_packet(Path(task['source_packet']).parent)
        for field in dates.FIELDS:self.assertEqual(packet['task'][field],expected[field])
        block=dict(text='Тест',basis='transcript',refs=[dict(start='1:1',end='1:1')])
        word=aq.module(self.c)
        content=dict(schema_version=1,input_hashes=packet['input_hashes'],title='Тест',organization={k:dict(status='not_found',items=[]) for k in word.ORG},summary=[block],notes=[block],definitions=[block],formulas=[],emphasis=[block],uncertainties=[],part_review=[dict(part=1,status='usable',note='fixture')],vocabulary=[])
        answer=self.c.home/'answer.json';dump(answer,content)
        result=ai_finalize.finalize(self.c,identity,answer)
        from docx import Document
        text='\n'.join(p.text for p in Document(result['word']).paragraphs)
        self.assertIn('Дата лекции: 2026-10-08',text)
        record=next(iter(aq.read(self.c.ai_state)['processed'].values()))
        for field in dates.FIELDS:self.assertEqual(record[field],expected[field])


if __name__=='__main__':unittest.main()
