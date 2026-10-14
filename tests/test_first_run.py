import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
REPO=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('setup_candidate',REPO/'installer/setup.py');setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class FirstRunPrerequisites(unittest.TestCase):
 def test_missing_document_runtime_creates_no_data(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'app';data=Path(td)/'data';root.mkdir()
   with patch.object(setup,'app_root',return_value=root/'versions/code'),patch.object(setup.subprocess,'run',side_effect=[SimpleNamespace(returncode=0),FileNotFoundError('document python missing')]):
    with self.assertRaisesRegex(RuntimeError,'document runtime unavailable'):setup.configure(root,data,'term','DEMO')
   self.assertFalse(data.exists());self.assertFalse((root/'config').exists())
 def test_native_import_failure_precedes_writes(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'app';data=Path(td)/'data';root.mkdir()
   with patch.object(setup,'app_root',return_value=root/'versions/code'),patch.object(setup.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr='DLL load failed')):
    with self.assertRaisesRegex(RuntimeError,'Visual C'):setup.configure(root,data,'term','DEMO')
   self.assertFalse(data.exists())
 def test_existing_config_never_probes_or_overwrites(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'app';(root/'config').mkdir(parents=True);cfg=root/'config/config.json';cfg.write_text('KEEP')
   with patch.object(setup,'app_root',return_value=root/'versions/code'),patch.object(setup,'validate_runtimes') as probe:
    with self.assertRaises(ValueError):setup.configure(root,Path(td)/'data','term','DEMO')
    probe.assert_not_called()
   self.assertEqual(cfg.read_text(),'KEEP')
class NoticeUninstall(unittest.TestCase):
 def test_notice_files_removed_and_config_preserved(self):
  import subprocess,hashlib
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'app';(root/'launcher').mkdir(parents=True);(root/'third_party/licenses').mkdir(parents=True);(root/'config').mkdir();(root/'docs').mkdir()
   script=root/'launcher/Uninstall.ps1';script.write_bytes((REPO/'installer/Uninstall.ps1').read_bytes());cfg=root/'config/keep.json';cfg.write_text('KEEP')
   files={}
   for name in ('THIRD_PARTY_NOTICES.md','third_party/licenses/LICENSE','docs/PREREQUISITES.md','ARCHITECTURE.md','DEVELOPMENT_PLAYBOOK.md'):
    p=root/name;p.write_text('notice');files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
   (root/'package-manifest.json').write_text(json.dumps(dict(files=files)))
   p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Apply'],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(all(not(root/n).exists() for n in files));self.assertEqual(cfg.read_text(),'KEEP')

class IntegrationEncoding(unittest.TestCase):
 def test_native_shortcut_unicode_roundtrip(self):
  import os,subprocess
  if os.name!='nt':self.skipTest('Windows shell link COM required')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'Программа 课程';root.mkdir()
   target=root/'private python.exe';target.write_bytes(b'fixture target; never executed')
   env=dict(os.environ,LP_LINK_SOURCE=str(REPO/'installer/ShellShortcut.cs'),LP_LINK_ROOT=str(root))
   command=r'''$ErrorActionPreference='Stop'
Add-Type -Path $env:LP_LINK_SOURCE
$root=$env:LP_LINK_ROOT
$path=Join-Path $root 'Lecture Pipeline.lnk'
$target=Join-Path $root 'private python.exe'
$arguments='-B -X utf8 "'+(Join-Path $root 'launch.py')+'" gui'
$link=New-Object LecturePipeline.Setup.ShellShortcut
try {$link.Target=$target;$link.Arguments=$arguments;$link.Directory=$root;$link.Save($path)} finally {$link.Dispose()}
$link=New-Object LecturePipeline.Setup.ShellShortcut($path)
try {
 if($link.Target -cne $target -or $link.Arguments -cne $arguments -or $link.Directory -cne $root){throw 'Unicode shortcut roundtrip mismatch'}
} finally {$link.Dispose()}
'''
   p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],env=env,capture_output=True,text=True,encoding='utf8',errors='replace')
   self.assertEqual(p.returncode,0,p.stderr+p.stdout)
   self.assertTrue((root/'Lecture Pipeline.lnk').is_file())
 def test_unicode_plan_without_python_encoding_environment(self):
  import os,subprocess
  if not os.environ.get('LP_DEPLOYMENT_ROOT'):self.skipTest('Set LP_DEPLOYMENT_ROOT to a disposable configured package')
  root=Path(os.environ['LP_DEPLOYMENT_ROOT']);env=dict(os.environ);env.pop('PYTHONIOENCODING',None);env['PYTHONUTF8']='0';env.pop('LECTURE_CONFIG',None)
  p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'launcher/Integrate.ps1')],env=env,capture_output=True,text=True,encoding='utf8',errors='replace')
  self.assertEqual(p.returncode,0,p.stderr+p.stdout)
  plan=json.loads((root/'logs/integration-plan.json').read_text(encoding='utf-8-sig'))
  self.assertEqual(Path(plan['execute']),root/'runtime/asr/pythonw.exe')
  self.assertEqual(Path(plan['launcher']),root/'launcher/launch.py')

if __name__=='__main__':unittest.main()
