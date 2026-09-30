import os, tempfile, unittest, zipfile, shutil
from pathlib import Path
from dialogue_worker import Worker, DIRS, write, load, digest, metadata, single_instance

class DialogueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'drive'
  for d in DIRS:(self.root/d).mkdir(parents=True)
  self.cfg=dict(root=str(self.root),home=str(self.base/'home'),asr_home=str(self.base/'absent'),stable_seconds=120,hash_interval=15,retry_seconds=0)
  self.t=0;self.calls=0;self.words=0;self.w=self.worker()
 def tearDown(self):self.tmp.cleanup()
 def asr(self,p,lang):
  self.calls+=1
  return dict(segments=[dict(start=0,end=1,text='Hello')],duration=1,detected_language='en',elapsed_asr_seconds=0)
 def word(self,p,out):
  self.words+=1
  with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml','<document/>')
  return {}
 def worker(self):return Worker(self.cfg,asr=self.asr,word=self.word,clock=lambda:self.t)
 def audio(self,name='ordinary.wav',data=b'audio'):
  p=self.root/DIRS[0]/name;p.write_bytes(data);return p
 def process(self,p):self.w.process(p,digest(p),metadata(p),'auto')
 def job(self):return next(iter(self.w.state['jobs'].values()))
 def test_stability_and_upload(self):
  p=self.audio();self.w.tick();self.t=119;self.w.tick();self.assertEqual(self.calls,0)
  p.write_bytes(b'longer');self.w.tick();self.t=239;self.w.tick();self.assertEqual(self.calls,0)
  self.t=255;self.w.tick();self.assertEqual(self.calls,1)
 def test_hash_change_same_metadata(self):
  p=self.audio(data=b'abc');self.w.stable(p);self.t=120;self.w.stable(p);s=p.stat();p.write_bytes(b'xyz');os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns));self.t=136
  self.assertIsNone(self.w.stable(p));self.t=200;self.assertIsNone(self.w.stable(p));self.t=257;self.assertIsNotNone(self.w.stable(p))
 def test_duplicate_and_restart(self):
  p=self.audio();self.process(p);self.w=self.worker();self.process(self.audio('renamed.wav'));self.assertEqual(self.calls,1);self.assertEqual(len(self.w.state['jobs']),1)
 def test_changed_same_name_versions(self):
  p=self.audio();self.process(p);first=self.job()['output_name'];p.write_bytes(b'new');self.process(p)
  self.assertEqual(self.calls,2);self.assertEqual(len({j['output_name'] for j in self.w.state['jobs'].values()}),2);self.assertTrue((self.root/DIRS[2]/(first+'.docx')).exists())
 def test_asr_error_queue_continues(self):
  def fail(p,lang):
   if p.read_bytes()==b'bad':raise RuntimeError('ASR injected failure')
   return self.asr(p,lang)
  self.w.asr=fail;self.audio('a.wav',b'bad');self.audio('b.wav',b'good');self.w.tick();self.t=120;self.w.tick();self.t=136;self.w.tick()
  self.assertEqual(sorted(j['status'] for j in self.w.state['jobs'].values()),['completed','failed'])
 def test_word_failure_restart_uses_cached_asr(self):
  p=self.audio();self.w.word=lambda *a:(_ for _ in ()).throw(RuntimeError('Word injected failure'));self.process(p)
  self.assertEqual(self.job()['status'],'failed');self.assertEqual(list((self.root/DIRS[2]).iterdir()),[]);self.assertEqual(list((self.root/DIRS[1]).iterdir()),[])
  self.w=self.worker();self.process(p);self.assertEqual(self.calls,1);self.assertEqual(self.job()['status'],'completed')
 def test_partial_publish_restart(self):
  p=self.audio();original=self.w.complete
  def crash(j,spool):
   raw,_=self.w.paths(j);raw.mkdir();shutil.copy2(spool/'outputs'/'transcript.txt',raw/'transcript.txt');shutil.copy2(spool/'outputs'/'transcript.srt',raw/'transcript.srt');raise OSError('Crash before Word rename')
  self.w.complete=crash;self.process(p);self.assertEqual(self.job()['status'],'publishing');self.w=self.worker();self.process(p)
  self.assertEqual(self.calls,1);self.assertEqual(self.job()['status'],'completed')
 def test_manual_output_never_overwritten(self):
  p=self.audio();self.process(p);_,doc=self.w.paths(self.job());doc.write_bytes(b'manual');self.process(p);self.assertEqual(doc.read_bytes(),b'manual');self.assertEqual(self.calls,1)
 def test_changed_during_asr_no_publication(self):
  p=self.audio()
  def change(copy,lang):p.write_bytes(b'changed');return self.asr(copy,lang)
  self.w.asr=change;self.process(p);self.assertEqual(self.job()['status'],'source_changed');self.assertEqual(list((self.root/DIRS[2]).iterdir()),[])
 def test_missing_state_fail_closed(self):
  self.w.statefile.unlink()
  with self.assertRaises(ValueError):self.worker()
 def test_corrupt_state_fail_closed(self):
  self.w.statefile.write_text('{')
  with self.assertRaises(ValueError):self.worker()
 def test_single_instance(self):
  with single_instance(self.cfg['home']):
   with self.assertRaises(OSError):
    with single_instance(self.cfg['home']):pass
 def test_language_and_default(self):
  self.assertEqual(self.w.language('a.wav'),'auto');write(self.root/DIRS[3]/'task_options.json',{'files':{'a.wav':{'language':'zh'}}});self.assertEqual(self.w.language('a.wav'),'zh')
 def test_empty_file_waits(self):
  p=self.audio(data=b'');self.w.stable(p);self.t=1000;self.assertIsNone(self.w.stable(p))
 def test_invalid_word_not_published(self):
  self.w.word=lambda p,o:o.write_bytes(b'bad');self.process(self.audio());self.assertEqual(self.job()['status'],'failed');self.assertFalse(any((self.root/DIRS[2]).iterdir()))
 def test_lecture_busy(self):
  Path(self.cfg['asr_home']).mkdir();write(Path(self.cfg['asr_home'])/'worker_status.json',{'lectures':{'one':{'status':'TRANSCRIBING'}}});self.assertTrue(self.w.busy_lecture())

if __name__=='__main__':unittest.main()
