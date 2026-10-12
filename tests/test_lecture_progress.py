import copy
from datetime import datetime,timezone
import math
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_lecture_catalog as fixtures
import lecture_progress as p


class ProgressTests(unittest.TestCase):
    def tracker(self,durations=(100,)):
        self.now=100.;self.rows=[]
        t=p.Tracker('ECON/01_2026-10-09',durations,self.rows.append,clock=lambda:self.now,wall=lambda:self.now)
        t.begin(1);return t
    def update(self,t,audio,seconds=1,**kw):
        self.now+=seconds;t.observe(dict(phase='transcribe',processed_audio_sec=audio,backend='cuda',session='child',**kw))
        return self.rows[-1]
    def test_single(self):
        t=self.tracker();r=self.update(t,25);self.assertEqual((r['part_index'],r['part_count'],r['percent']),(1,1,25))
    def test_eight_parts_order(self):
        t=self.tracker([60]*8)
        for i in range(1,9):
            t.begin(i);r=self.update(t,30)
            self.assertEqual(r['part_index'],i);self.assertEqual(r['percent'],((i-1)*60+30)/480*100)
    def test_unequal_durations(self):
        t=self.tracker([3600,300]);t.complete_part(3600)
        self.assertAlmostEqual(self.rows[-1]['percent'],3600/3900*100)
    def test_current_timestamp_total(self):
        t=self.tracker([60,120]);t.begin(2);r=self.update(t,30)
        self.assertEqual(r['percent'],50)
    def test_clamp(self):
        t=self.tracker();self.assertEqual(self.update(t,-10)['percent'],0)
        self.assertEqual(self.update(t,1000)['percent'],100)
    def test_unknown_duration(self):
        t=self.tracker([None,60]);r=self.update(t,20)
        self.assertIsNone(r['percent']);self.assertEqual(r['part_count'],2)
    def test_invalid_duration(self):
        for d in (0,-1,float('nan'),float('inf'),'broken'):
            t=self.tracker([d]);self.assertIsNone(self.update(t,10)['percent'])
    def test_actual_duration_replaces_metadata(self):
        t=self.tracker([101]);self.assertEqual(self.update(t,50,audio_duration_sec=100)['percent'],50)
    def test_throttle(self):
        t=self.tracker()
        for i in range(10000):t.observe(dict(phase='transcribe',processed_audio_sec=20,backend='cpu'))
        self.assertEqual(len(self.rows),1)
        self.update(t,30);self.assertEqual(len(self.rows),2)
    def test_eta_early_hidden(self):
        t=self.tracker([1000]);self.assertIsNone(self.update(t,50)['eta_seconds'])
    def test_eta_throughput(self):
        t=self.tracker([1000]);self.update(t,0)
        for n in range(1,31):r=self.update(t,n*2)
        self.assertAlmostEqual(r['eta_seconds'],470)
    def test_eta_low_fraction_hidden(self):
        t=self.tracker([10000]);self.update(t,0)
        for n in range(1,31):r=self.update(t,n*2)
        self.assertIsNone(r['eta_seconds'])
    def test_smoothing(self):
        t=self.tracker([1000]);self.update(t,0)
        for n in range(1,31):self.update(t,n*2)
        before=self.rows[-1]['eta_seconds'];after=self.update(t,70)['eta_seconds']
        self.assertLess(abs(after-before),100)
    def test_stalled_timeline_hides_eta(self):
        t=self.tracker([1000]);self.update(t,0)
        for n in range(1,31):self.update(t,n*2)
        self.assertIsNotNone(self.rows[-1]['eta_seconds'])
        self.assertIsNone(self.update(t,60,seconds=16)['eta_seconds'])
    def test_child_restart_resets_eta_even_same_device(self):
        t=self.tracker([1000]);self.update(t,0)
        for n in range(1,31):self.update(t,n*2)
        self.now+=1;t.observe(dict(phase='transcribe',processed_audio_sec=0,backend='cuda',session='new'))
        self.assertIsNone(self.rows[-1]['eta_seconds']);self.assertEqual(self.rows[-1]['percent'],0)
    def test_new_attempt_resets(self):
        first=self.tracker();token=first.token
        t=self.tracker();self.assertNotEqual(token,t.token);self.assertIsNone(self.update(t,10)['eta_seconds'])
    def test_backend_reset(self):
        t=self.tracker([1000]);self.update(t,0)
        for n in range(1,31):self.update(t,n*2)
        self.now+=1;t.observe(dict(phase='transcribe',processed_audio_sec=10,backend='cpu',session='fallback'))
        self.assertIsNone(self.rows[-1]['eta_seconds']);self.assertEqual(self.rows[-1]['processed_audio_seconds'],10)
    def test_publish_failure_nonfatal(self):
        t=self.tracker();t.publish=lambda v:(_ for _ in ()).throw(OSError('fixture'))
        with self.assertLogs(level='ERROR'):self.update(t,30)
    def test_independent_identity(self):
        t=self.tracker();other=p.Tracker('OTHER/01_2026-10-09',[200],self.rows.append);other.begin(1)
        self.assertNotEqual(self.rows[0]['identity'],self.rows[1]['identity'])
    def test_missing_metadata(self):
        self.assertIsNone(p.media_duration('nonexistent-fixture.wav'))
    def test_presentation_scope(self):
        t=self.tracker();r=self.update(t,5);v=p.presentation(r)
        self.assertIn('ETA ASR: рассчитывается',v['details']);self.assertEqual(v['fraction'],.05)


class CatalogProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.c=fixtures.fixture(Path(self.temp.name));self.id=fixtures.add(self.c,stage='ready')
        self.now=time.time();self.observations=[]
        t=p.Tracker(self.id,[100],self.observations.append,wall=lambda:self.now);t.begin(1)
        self.value=dict(self.observations[-1],worker_started_at='session',job_token='token',stage='asr',percent=63.)
        self.worker=dict(worker='RUNNING',heartbeat=datetime.now(timezone.utc).isoformat(),started_at='session',lectures={self.id:dict(status='TRANSCRIBING',progress=self.value)})
        self.job=dict(phase='transcribing',token='token');self.save()
    def save(self):
        fixtures.dump(self.c.worker_home/'worker_status.json',self.worker)
        fixtures.dump(self.c.worker_home/'worker_jobs.json',dict(jobs={self.id:self.job}))
    def row(self):return fixtures.catalog.build(self.c)['items'][0]
    def test_live_readonly(self):
        before=fixtures.fingerprints(Path(self.temp.name));self.assertEqual(self.row()['progress']['percent'],63)
        self.assertEqual(before,fixtures.fingerprints(Path(self.temp.name)))
    def test_stale_heartbeat(self):
        self.worker['heartbeat']='2000-01-01T00:00:00+00:00';self.save();self.assertIsNone(self.row()['progress'])
    def test_stale_observation(self):
        self.value['updated_at']-=11;self.save();self.assertIsNone(self.row()['progress'])
    def test_restart_session(self):
        self.worker['started_at']='new';self.save();self.assertIsNone(self.row()['progress'])
    def test_legacy(self):
        self.worker['lectures'][self.id].pop('progress');self.save();self.assertIsNone(self.row()['progress'])
    def test_committed_raw_wins(self):
        fixtures.add(self.c,stage='raw');self.assertIsNone(self.row()['progress'])
    def test_ai_pending_no_fake_progress(self):
        fixtures.add(self.c,stage='waiting_ai');r=self.row();self.assertEqual(r['status'],'waiting_ai');self.assertIsNone(r['progress'])
    def test_done_no_eta(self):
        fixtures.add(self.c);r=self.row();self.assertEqual(r['status'],'done');self.assertIsNone(r['progress'])
    def test_malformed_observation(self):
        self.value['percent']=float('nan');self.save();self.assertIsNone(self.row()['progress'])
    def test_dashboard_shared_projection_and_dialogue(self):
        import adapter
        fixtures.dump(self.c.dialogue_home/'status.json',dict(worker='RUNNING',active='fixture.wav',files={'fixture.wav':'processing'}))
        fixtures.dump(self.c.dialogue_home/'dialogue_state.json',dict(jobs={}))
        (self.c.dialogue_root/'00 — Входящие аудио').mkdir(parents=True)
        catalog=fixtures.catalog.build(self.c)
        view=adapter.snapshot(self.c.path,catalog=catalog)
        self.assertIs(view['catalog'],catalog)
        self.assertEqual(view['progress'],.63)
        self.assertIn(catalog['items'][0]['progress_view']['details'],view['current'])
        self.assertIn('Dialogue: fixture.wav',view['current'])
