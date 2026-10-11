import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_lecture_inbox as intake_tests
import test_worker as worker_tests
from test_local_finalize import fixture, dump, lecture
import human_ux as ux
import ai_queue as aq
import ai_finalize
from pipeline_config import Config


class DedupTests(unittest.TestCase):
    setUp=intake_tests.InboxTests.setUp
    new_inbox=intake_tests.InboxTests.new_inbox
    scan=intake_tests.InboxTests.scan
    settled=intake_tests.InboxTests.settled

    def test_same_course_copy_reviews_and_other_course_allows(self):
        original=self.source/'20261009.wav';original.write_bytes(b'unique source')
        self.settled()
        (self.source/'copy20261009.wav').write_bytes(original.read_bytes())
        rows=self.settled()['sources']
        self.assertEqual(sum(r['status']=='queued' for r in rows),1)
        self.assertTrue(any(r['status']=='review' and 'duplicate_source' in r.get('error','') for r in rows))
        d=copy.deepcopy(self.c.data);s=copy.deepcopy(d['workspaces'][self.c.active]['subjects'][0])
        s.update(subject_code='SECOND',folder='SECOND');s.pop('inbox',None)
        d['workspaces'][self.c.active]['subjects'].append(s);dump(self.c.path,d);self.c=Config(self.c.path)
        for key in ('audio_dir','raw_dir','ready_dir'):self.c.subjects()['SECOND'][key].mkdir(parents=True)
        self.assertEqual(ux.add_lecture(self.c,'SECOND','2026-10-09',1,[original]),'01_2026-10-09')

    def test_changed_accepted_source_reviews_without_new_key(self):
        f=self.source/'20261009.wav';f.write_bytes(b'original');self.settled()
        f.write_bytes(b'changed generation')
        rows=self.settled()['sources'];self.assertEqual(sum(bool(r.get('lecture_key')) for r in rows),1)
        self.assertTrue(any(r['status']=='review' and 'changed_source' in r.get('error','') for r in rows))
        self.assertEqual(len(list(self.c.subjects()['SUBJECT']['audio_dir'].glob('*.READY.json'))),1)

    def test_multipart_copy_keeps_review_reason_on_restart(self):
        for n in (1,2):(self.source/f'Original20261009_{n}.wav').write_bytes(bytes([n]))
        self.settled()
        for n in (1,2):(self.source/f'Copy20261009_{n}.wav').write_bytes(bytes([n]))
        self.settled();self.new_inbox();groups=self.settled()['groups']
        copied=next(g for g in groups if g['session_stem'].startswith('copy'))
        self.assertEqual(copied['status'],'review');self.assertIn('duplicate_source',copied['error'])

    def test_reservation_pins_hash_even_if_mtime_restored(self):
        f=self.source/'20261009.wav';f.write_bytes(b'original');saved=f.stat()
        p=ux.pipeline(self.c)
        with patch.object(ux.shutil,'copy2',side_effect=OSError('interrupted')):self.settled()
        f.write_bytes(b'CHANGED!');os.utime(f,ns=(saved.st_atime_ns,saved.st_mtime_ns))
        rows=self.settled()['sources']
        self.assertTrue(any(r['status']=='review' for r in rows))
        self.assertFalse(list(self.c.subjects()['SUBJECT']['audio_dir'].glob('*.READY.json')))


class RawRecoveryTests(unittest.TestCase):
    setUp=worker_tests.WorkerTests.setUp
    new_worker=worker_tests.WorkerTests.new_worker
    recognize=worker_tests.WorkerTests.recognize
    cycle=worker_tests.WorkerTests.cycle
    status=worker_tests.WorkerTests.status
    parts=worker_tests.WorkerTests.parts
    signal=worker_tests.WorkerTests.signal

    def complete(self):self.parts(1,2);self.signal();self.cycle();self.cycle(120)

    def test_corrupt_completed_raw_no_asr(self):
        self.complete();calls=self.calls
        (self.raw/self.key/(self.key+'_raw.txt')).write_text('corrupt')
        self.worker=self.new_worker();self.cycle(1000)
        self.assertEqual(self.status(),'ERROR');self.assertEqual(self.calls,calls)

    def test_valid_raw_survives_audio_removal(self):
        self.complete();calls=self.calls
        for f in self.audio.glob('*.m4a'):f.unlink()
        self.worker=self.new_worker();self.cycle(1000)
        self.assertEqual(self.status(),'DONE');self.assertEqual(self.calls,calls)

    def test_lost_phase_ack_reuses_plan(self):
        self.complete();calls=self.calls
        p=worker_tests.p;state=p.load_state(self.sf);state['lectures'].clear();p.save_state(self.sf,state)
        job=self.worker.journal['jobs'][self.identity];job['phase']='transcribing';self.worker.save()
        self.worker=self.new_worker();self.cycle(1000)
        self.assertEqual(self.status(),'DONE');self.assertEqual(self.calls,calls)

    def test_external_raw_without_completion_entry_recovers(self):
        self.complete();calls=self.calls
        p=worker_tests.p;state=p.load_state(self.sf);state['lectures'].clear();p.save_state(self.sf,state)
        self.worker.journal['jobs'].clear();self.worker.save();self.worker=self.new_worker();self.cycle(1000)
        self.assertEqual(self.status(),'DONE');self.assertEqual(self.calls,calls)

    def test_lost_spool_after_committed_raw_recovers(self):
        import shutil
        self.complete();calls=self.calls
        p=worker_tests.p;state=p.load_state(self.sf);state['lectures'].clear();p.save_state(self.sf,state)
        job=self.worker.journal['jobs'][self.identity];job['phase']='publishing';self.worker.save()
        spool=self.worker.spool(job).resolve();self.assertIn(self.root.resolve(),spool.parents)
        shutil.rmtree(spool)
        self.worker=self.new_worker();self.cycle(1000)
        self.assertEqual(self.status(),'DONE');self.assertEqual(self.calls,calls)


class AIRecoveryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.c=fixture(Path(self.tmp.name))

    def test_result_artifact_before_ack_recovers(self):
        identity,content,_=lecture(self.c,empty=True)
        with patch.object(aq,'persist',side_effect=OSError('lost ack')):
            with self.assertRaises(OSError):aq.accept_result(self.c,identity,content)
        result=aq.refresh(self.c)['tasks'][identity]
        self.assertEqual(result['status'],'ai_result_ready')
        self.assertEqual(result['recovery_action'],'recovered_ai_completion')

    def test_completed_word_corruption_is_visible(self):
        identity,content,_=lecture(self.c,empty=True);result=ai_finalize.finalize(self.c,identity,content)
        Path(result['word']).write_bytes(b'corrupt')
        task=aq.refresh(self.c)['tasks'][identity]
        self.assertEqual(task['status'],'failed');self.assertIn('changed',task['error'])

    def test_completed_raw_corruption_is_visible(self):
        identity,content,folder=lecture(self.c,empty=True);ai_finalize.finalize(self.c,identity,content)
        (folder/'part.srt').write_text('corrupt')
        self.assertEqual(aq.refresh(self.c)['tasks'][identity]['status'],'failed')


if __name__=='__main__':unittest.main()
