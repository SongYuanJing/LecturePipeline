"""Real PowerShell stop-file behavior; Scheduler calls are fixture substituted."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1] / 'src' / 'app'


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell required')
class FreshWorkerControlTests(unittest.TestCase):
    def test_missing_home_stop_force_stop_uninstall(self):
        for script, marker in [('WorkerControl.ps1', 'worker.stop'),
                               ('DialogueControl.ps1', 'stop')]:
            for action in ('Stop', 'ForceStop', 'Uninstall'):
                with self.subTest(script=script, action=action), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp) / 'App 课程'
                    root.mkdir()
                    shutil.copyfile(APP / script, root / script)
                    (root / 'Config.ps1').write_text('''
$homePath=Join-Path $PSScriptRoot 'never-started/worker'
$resolved=@{worker_home=$homePath; dialogue=@{home=$homePath}; tasks=@{lecture='fixture';dialogue='fixture'}}
function Disable-ScheduledTask { param($TaskName) }
function Stop-ScheduledTask { param($TaskName) }
function Get-ScheduledTask { param($TaskName,$ErrorAction) }
''', encoding='utf-8-sig')
                    home = root / 'never-started' / 'worker'
                    self.assertFalse(home.exists())
                    for _ in range(2):  # repeated stop must also be harmless
                        result = subprocess.run(
                            ['powershell.exe', '-NoProfile', '-NonInteractive',
                             '-ExecutionPolicy', 'Bypass', '-File', str(root / script),
                             '-Action', action], capture_output=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertTrue((home / marker).read_text().strip())


    def test_start_clears_stop_marker_and_requests_scheduler_start(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'isolated-app';root.mkdir()
            shutil.copyfile(APP/'WorkerControl.ps1',root/'WorkerControl.ps1')
            worker=root/'worker';worker.mkdir();stop=worker/'worker.stop';stop.write_text('Stopped')
            (root/'pipeline_config.py').write_text('pass',encoding='utf-8')
            def quote(path):return str(path).replace("'","''")
            # Use an existing interpreter from this DEV workspace, never a system worker.
            asr=Path(sys.executable)
            (root/'Config.ps1').write_text(
                "$resolved=@{worker_home='"+quote(worker)+"';tasks=@{lecture='fixture'};asr_python='"+quote(asr)+"'}\n"
                "function Enable-ScheduledTask { param($TaskName) Set-Content -LiteralPath '"+quote(root/'enabled.txt')+"' -Value $TaskName }\n"
                "function Start-ScheduledTask { param($TaskName) Set-Content -LiteralPath '"+quote(root/'started.txt')+"' -Value $TaskName }\n",
                encoding='utf-8-sig')
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive',
                                   '-ExecutionPolicy','Bypass','-File',str(root/'WorkerControl.ps1'),
                                   '-Action','Start'],capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(stop.exists())
            self.assertEqual((root/'enabled.txt').read_text().strip(),'fixture')
            self.assertEqual((root/'started.txt').read_text().strip(),'fixture')


if __name__ == '__main__':
    unittest.main()
