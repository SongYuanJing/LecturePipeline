"""Real PowerShell stop-file behavior; Scheduler calls are fixture substituted."""
import os
from pathlib import Path
import shutil
import subprocess
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


if __name__ == '__main__':
    unittest.main()
