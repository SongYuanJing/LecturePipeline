import sys,tempfile,unittest,zipfile,json,os
from pathlib import Path
from unittest.mock import patch
from test_local_finalize import fixture,lecture,dump,APP,REPO
sys.path.insert(0,str(APP/'gui_v1.8'))
import human_ux as ux
import ai_queue as aq
from pipeline_config import Config
from adapter import Manager

class HumanUXTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.c=fixture(Path(self.tmp.name));os.environ['LECTURE_CONFIG']=str(self.c.path)
 def test_ingest_while_worker_lock_held(self):
  p=ux.pipeline(self.c);code=next(iter(self.c.subjects()));source=self.c.home/'audio.wav';source.write_bytes(b'disposable audio')
  self.c.worker_home.mkdir(parents=True)
  with p.pipeline_lock(self.c.worker_home/'lecture_pipeline.lock'):
   key=ux.add_lecture(self.c,code,'2030-01-01',1,[source])
  s=self.c.subjects()[code];parts=p.collect_lectures(s['audio_dir'])[key];self.assertIsNotNone(p.read_ready(s,key,parts));self.assertEqual(ux.next_number(self.c,code),2)
  with self.assertRaisesRegex(ValueError,'существует'):ux.add_lecture(self.c,code,'2030-01-01',1,[source])
  self.assertEqual(source.read_bytes(),b'disposable audio')
 def test_empty_or_changed_file_never_ready(self):
  p=ux.pipeline(self.c);code=next(iter(self.c.subjects()));source=self.c.home/'empty.wav';source.touch()
  with self.assertRaises(ValueError):ux.add_lecture(self.c,code,'2030-01-01',1,[source])
  self.assertFalse(p.ready_path(self.c.subjects()[code],'01_2030-01-01').exists())
 def test_packet_export_exact(self):
  identity,_,_=lecture(self.c);out=self.c.home/'export.zip';ux.export_packet(self.c,identity,out)
  packet=Path(aq.load_queue(self.c)['tasks'][identity]['source_packet']).parent
  with zipfile.ZipFile(out) as z:
   self.assertIsNone(z.testzip())
   for p in packet.iterdir():self.assertEqual(z.read(p.name),p.read_bytes())
  with self.assertRaises(ValueError):ux.export_packet(self.c,identity,out)
 def test_invalid_quote_has_path_and_no_mutation(self):
  identity,path,_=lecture(self.c);content=aq.read(path);content['summary'][0]['refs'][0]['quote']='not in source';dump(path,content)
  before={p:p.read_bytes() for p in (self.c.state,self.c.ai_state,self.c.dictionary,self.c.queue_home/'queue.json')}
  with self.assertRaisesRegex(ValueError,r'summary\[0\].refs\[0\].quote'):ux.import_result(self.c,identity,path)
  self.assertTrue(all(p.read_bytes()==b for p,b in before.items()));self.assertFalse((self.c.queue_home/'imports').exists())
 def test_progress_not_fabricated(self):
  self.assertEqual(ux.progress_view({}),dict(progress=None,eta=None))
  self.assertIsNone(ux.progress_view(dict(audio_duration_sec=100,processed_audio_sec=5,elapsed_sec=1))['eta'])
  self.assertEqual(ux.progress_view(dict(audio_duration_sec=100,processed_audio_sec=50,elapsed_sec=20)),dict(progress=.5,eta=20))
  self.assertEqual(ux.progress_view(dict(audio_duration_sec=100,processed_audio_sec=110,elapsed_sec=20)),dict(progress=1,eta=None))
 def test_subject_and_workspace_transaction(self):
  class Controls:
   def __init__(self,c):pass
   def states(self):return {k:dict(running=False,enabled=False) for k in ('lecture','dialogue')}
   def action(self,*a):pass
   def wait_stopped(self,*a):pass
   def restore(self,*a):pass
   def confirm_started(self,*a):pass
  manager=Manager(self.c.path,Controls,lambda c:dict(ok=True))
  old=self.c.state.read_bytes();ux.edit_subject(self.c,'NEW','New subject','en',manager,True);c=Config(self.c.path)
  self.assertEqual(c.subjects()['NEW']['default_language'],'en');self.assertEqual(c.state.read_bytes(),old)
  ux.add_workspace(c,'Next semester',manager);new=Config(c.path);self.assertNotEqual(new.active,c.active);self.assertEqual(new.subjects(),{})
  manager.switch(c.active);self.assertEqual(Config(c.path).state.read_bytes(),old)

class IntegrationContract(unittest.TestCase):
 def test_exact_task_only(self):
  import subprocess
  script=REPO/'installer/Integrate.ps1'
  command="$ast=[System.Management.Automation.Language.Parser]::ParseFile($env:LP_SCRIPT,[ref]$null,[ref]$null);$fn=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-ExpectedTask'},$true);Invoke-Expression $fn.Extent.Text;$task=[pscustomobject]@{Actions=@([pscustomobject]@{Execute='candidate/pythonw.exe';Arguments='launch gui';WorkingDirectory='candidate'})};if(-not(Test-ExpectedTask $task 'candidate/pythonw.exe' 'launch gui' 'candidate')){throw 'exact rejected'};foreach($field in @('Execute','Arguments','WorkingDirectory')){$old=$task.Actions[0].$field;$task.Actions[0].$field='conflict';if(Test-ExpectedTask $task 'candidate/pythonw.exe' 'launch gui' 'candidate'){throw 'conflict accepted'};$task.Actions[0].$field=$old}"
  p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],env=dict(os.environ,LP_SCRIPT=str(script)),capture_output=True,text=True,creationflags=0x08000000)
  self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':unittest.main()
