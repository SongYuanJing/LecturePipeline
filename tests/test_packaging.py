import copy,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline_config import Config,ConfigError,preflight
from adapter import safe_open,Controls
REPO=Path(os.environ['PACKAGING_REPO']);C=Config();ROOT=C.home

def call(args,**kw):return subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',**kw)
class PackagingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
 def variant(self,edit):
  d=copy.deepcopy(C.data);d['install_root']=str(C.install);d['application_home']=str(C.home);edit(d)
  p=self.base/'config.json';p.write_text(json.dumps(d),encoding='utf8');return Config(p)
 def test_example_has_no_personal_defaults(self):
  d=json.loads((REPO/'config.example.json').read_text());self.assertEqual(d['data_root'],'REPLACE_WITH_ABSOLUTE_DATA_ROOT')
  self.assertTrue(all(not Path(v).is_absolute() for v in d['runtimes'].values()));self.assertNotIn('task_prefix',d)
 def test_owned_paths_outside_version(self):
  for p in [C.worker_home,C.dialogue_home,C.queue_home,C.runtime('asr_python',''),C.model_cache()]:self.assertNotIn(C.install,p.parents);self.assertIn(ROOT,p.parents)
  self.assertNotIn(ROOT,C.data_root.parents)
 def test_legacy_schema_one(self):
  d=copy.deepcopy(C.data);d.pop('application_home');d.pop('task_prefix');d['install_root']=str(C.install)
  p=self.base/'legacy.json';p.write_text(json.dumps(d));c=Config(p)
  self.assertEqual(c.home,c.install);self.assertEqual(c.task_names()['lecture'],'LecturePipelineWorker')
 def test_missing_model_diagnostic(self):
  c=self.variant(lambda d:d['runtimes'].update(model_cache=str(self.base/'no-model')));r=preflight(c,probe_gpu=False)
  self.assertFalse(r['ok']);self.assertEqual(next(x for x in r['checks'] if x['id']=='model')['status'],'error')
 def test_missing_gpu_fallback(self):
  c=self.variant(lambda d:d['runtimes'].update(cuda=str(self.base/'no-cuda')));r=preflight(c)
  x=next(x for x in r['checks'] if x['id']=='asr_backend');self.assertTrue(x['cpu_fallback']);self.assertFalse(x['gpu_available']);self.assertEqual(x['status'],'warning')
 def test_data_unavailable_no_reset(self):
  before=C.state.read_bytes();c=self.variant(lambda d:d.update(data_root=str(self.base/'not-mounted')));r=preflight(c,probe_gpu=False)
  self.assertFalse(r['ok']);self.assertFalse(c.data_root.exists());self.assertEqual(before,C.state.read_bytes())
 def test_overlap_rejected(self):
  with self.assertRaises(ConfigError):self.variant(lambda d:d.update(data_root=str(ROOT/'versions')))
 def test_task_identity_isolated(self):
  names=C.task_names();self.assertTrue(all(x.startswith('LP-') for x in names.values()));self.assertNotIn('LecturePipelineWorker',names.values())
  with self.assertRaises(ConfigError):self.variant(lambda d:d.update(task_prefix='LecturePipelineWorker')).task_names()
 def test_config_ps_relative_runtime(self):
  env=dict(os.environ,LECTURE_CONFIG=str(C.path));r=call(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',". '"+str(C.install/'Config.ps1')+"'; $resolved.asr_python"],env=env)
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn(str(ROOT/'runtime/asr/python.exe'),r.stdout)
 def test_profile_environment_ignored(self):
  env=dict(os.environ,USERPROFILE=str(self.base/'other-user'),PYTHONHOME=str(self.base/'invalid'),PYTHONPATH=str(self.base/'invalid'))
  r=call([ROOT/'runtime/asr/python.exe','-B','-c','import sys,ctranslate2,pipeline_config; print(sys.prefix); print(ctranslate2.__file__)'],env=env)
  self.assertEqual(r.returncode,0,r.stderr);self.assertNotIn(str(self.base),r.stdout);self.assertIn(str(ROOT/'runtime/asr'),r.stdout)
 def test_own_document_write(self):
  out=self.base/'roundtrip.docx';book=self.base/'roundtrip.xlsx'
  code=f"from docx import Document;from openpyxl import Workbook;d=Document();d.add_paragraph('дё­ж–‡ / English');d.save({str(out)!r});w=Workbook();w.save({str(book)!r})"
  r=call([ROOT/'runtime/document/python.exe','-B','-X','utf8','-c',code]);self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(out.is_file());self.assertTrue(book.is_file())
 def test_release_manifest_hashes(self):
  m=json.loads((C.install/'release.json').read_text());self.assertEqual(m['config_schema_version'],1);self.assertFalse(m['migration_required'])
  for name,h in m['files'].items():self.assertEqual(hashlib.sha256((C.install/name).read_bytes()).hexdigest(),h,name)
 def test_asr_h3_unchanged(self):
  for name in ('lecture_asr.py','atomic_publish.py','windows_publish.py','dictionary_merge.py','word_ai_v1.5/lecture_ai.py'):
   r=call(['git','-C',REPO,'show','v1.8.1:src/app/'+name]);self.assertEqual(r.returncode,0,r.stderr)
   self.assertEqual(r.stdout,(REPO/'src/app'/name).read_text(encoding='utf-8-sig'),name)
 def test_source_personal_paths_absent(self):
  prohibited=[value for value in (os.environ.get('USERPROFILE'),str(Path.home()),'codex-runtimes') if value]
  for folder in ('src','installer','scripts'):
   for p in (REPO/folder).rglob('*'):
    if p.is_file() and p.suffix in ('.py','.ps1','.json'):
     text=p.read_text(encoding='utf-8-sig')
     for value in prohibited:self.assertNotIn(value,text,str(p))
 def test_safe_open_new_log_root(self):
  p=ROOT/'logs';opened=[];safe_open(C,p,opened.append);self.assertEqual(opened,[str(p)])
 def test_controls_use_config_tasks(self):self.assertEqual(Controls(C).tasks,C.task_names())
 def test_first_run_refuses_existing_data(self):
  before=C.state.read_bytes();r=call([ROOT/'runtime/asr/python.exe','-B',ROOT/'launcher/setup.py','--data-root',C.data_root]);self.assertNotEqual(r.returncode,0);self.assertEqual(before,C.state.read_bytes())
 def test_uninstall_preserves_mutable_and_external(self):
  root=self.base/'app';(root/'launcher').mkdir(parents=True);(root/'versions/1').mkdir(parents=True)
  script=root/'launcher/Uninstall.ps1';script.write_bytes((REPO/'installer/Uninstall.ps1').read_bytes())
  owned=root/'versions/1/code.py';owned.write_text('pass')
  sentinels=[]
  for folder in ('config','models','run','logs','backups'):
   f=root/folder/'keep.txt';f.parent.mkdir();f.write_text('KEEP');sentinels.append(f)
  external=self.base/'external.xlsx';external.write_text('USER');sentinels.append(external)
  (root/'package-manifest.json').write_text(json.dumps({'files':{'versions/1/code.py':hashlib.sha256(owned.read_bytes()).hexdigest()}}))
  r=call(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',script,'-Apply']);self.assertEqual(r.returncode,0,r.stderr);self.assertFalse(owned.exists());self.assertTrue(all(f.exists() for f in sentinels))
 def test_uninstall_rejects_traversal_before_deleting(self):
  root=self.base/'app';(root/'launcher').mkdir(parents=True);script=root/'launcher/Uninstall.ps1';script.write_bytes((REPO/'installer/Uninstall.ps1').read_bytes());outside=self.base/'keep.txt';outside.write_text('KEEP')
  (root/'package-manifest.json').write_text(json.dumps({'files':{'../keep.txt':hashlib.sha256(outside.read_bytes()).hexdigest()}}))
  r=call(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',script,'-Apply']);self.assertNotEqual(r.returncode,0);self.assertEqual(outside.read_text(),'KEEP')
 def test_new_dictionary_roundtrip_merge(self):
  import dictionary_merge as dm
  batch={'schema_version':1,'source':{k:v for k,v in zip(('source_file_id','source_signature','subject_code','subject','lecture_id','source_file_name'),('fixture','signature','DEMO','Demo','01_2020-01-01','fixture.txt'))},'terms':[dict(chinese='жµ‹иЇ•',pinyin='ceshi',russian='С‚РµСЃС‚',occurrences=2)]}
  original=C.dictionary.read_bytes();merged,report=dm.merge(original,batch);self.assertEqual(report['words'],1)
  b=dm.Book(merged);row=next(iter(b.entries().values()))[0];b.put(dm.MAIN,f'A{row}','Р’С‹СѓС‡РµРЅРѕ');b.put(dm.MAIN,f'D{row}','СЂСѓС‡РЅРѕР№ РїРµСЂРµРІРѕРґ');edited=b.save()
  repeated,report=dm.merge(edited,batch);self.assertEqual(repeated,edited);self.assertEqual(report['status'],'already_merged');self.assertEqual(original,C.dictionary.read_bytes())
 def test_workspace_switch_uses_home_journal(self):
  from adapter import Manager
  d=copy.deepcopy(C.data);home=self.base/'application';app=home/'versions/code';app.mkdir(parents=True)
  d.update(install_root=str(app),application_home=str(home));w=copy.deepcopy(d['workspaces'][d['active_workspace']]);w.update(folder='second',worker_home='run/workspaces/second');d['workspaces']['second']=w
  cfg=home/'config.json';cfg.write_text(json.dumps(d));events=[]
  class Fake:
   def __init__(self,c):self.c=c
   def states(self):return {k:dict(running=False,enabled=False) for k in ('lecture','dialogue')}
   def action(self,k,a):events.append((k,a))
   def wait_stopped(self,k):pass
   def restore(self,s):pass
   def confirm_started(self,s):pass
  m=Manager(cfg,controls=Fake,check=lambda c:dict(ok=True,checks=[]));m.switch('second')
  self.assertEqual(Config(cfg).active,'second');self.assertEqual(m.journal,home/'run/gui/workspace-transaction.json');self.assertFalse((app/'run').exists());self.assertEqual(len(events),2)
 def test_workspace_failed_validation_keeps_config(self):
  from adapter import Manager
  d=copy.deepcopy(C.data);home=self.base/'application';app=home/'versions/code';app.mkdir(parents=True);d.update(install_root=str(app),application_home=str(home));w=copy.deepcopy(d['workspaces'][d['active_workspace']]);w.update(folder='second',worker_home='run/workspaces/second');d['workspaces']['second']=w
  cfg=home/'config.json';cfg.write_text(json.dumps(d));before=cfg.read_bytes()
  m=Manager(cfg,check=lambda c:dict(ok=False,checks=[dict(status='error',message='unavailable')]))
  with self.assertRaises(ConfigError):m.switch('second')
  self.assertEqual(before,cfg.read_bytes())
if __name__=='__main__':unittest.main()
