import copy
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

from test_course_setup import fixture
from adapter import Controls,Manager,START_CONFIRM_TIMEOUT


class WorkerConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.c=fixture(Path(self.tmp.name))
        self.controls=Controls.__new__(Controls)
        self.controls.c=self.c;self.controls.tasks=self.c.task_names()
        self.request=datetime.now(timezone.utc)-timedelta(seconds=2)
        self.controls.starts={'lecture':self.request}
        self.status=self.c.worker_home/'worker_status.json'
        self.status.parent.mkdir(parents=True,exist_ok=True)
        self.tick=0

    def publish(self,started,beat=None):
        self.status.write_text(json.dumps(dict(worker='RUNNING',started_at=started.isoformat(),
                                               heartbeat=(beat or datetime.now(timezone.utc)).isoformat())))

    def scheduler(self,running=True,enabled=True,last_result=0):
        return {'lecture':dict(state='Running' if running else 'Ready',running=running,
                               enabled=enabled,last_result=last_result,last_run='fixture')}

    def wait(self,step):self.tick+=step
    def confirm(self,timeout=5):
        return self.controls.confirm_started({'lecture':{'running':True}},timeout=timeout,
                                             clock=lambda:self.tick,pause=self.wait)

    def test_successful_start_requires_scheduler_and_new_session(self):
        self.publish(self.request+timedelta(seconds=1))
        self.controls.states=lambda:self.scheduler()
        self.confirm()
        self.assertEqual(self.tick,0)

    def test_delayed_scheduler_retry_is_not_reported_as_failure(self):
        self.request=datetime.now(timezone.utc)-timedelta(seconds=80)
        self.controls.starts['lecture']=self.request
        self.publish(self.request+timedelta(seconds=70))
        self.controls.states=lambda:self.scheduler(running=self.tick>=70)
        self.confirm(timeout=START_CONFIRM_TIMEOUT)
        self.assertEqual(self.tick,70)

    def test_failed_start_reports_scheduler_result_and_old_session(self):
        self.publish(self.request-timedelta(minutes=5))
        self.controls.states=lambda:self.scheduler(running=False,last_result=267009)
        with self.assertRaisesRegex(RuntimeError,'267009') as error:self.confirm(timeout=3)
        self.assertIn('started_at',str(error.exception))

    def test_restart_rejects_fresh_heartbeat_from_previous_session(self):
        self.publish(self.request-timedelta(minutes=5))
        self.controls.states=lambda:self.scheduler()
        def advance(step):
            self.tick+=step
            if self.tick==2:self.publish(self.request+timedelta(seconds=1))
        self.controls.confirm_started({'lecture':{'running':True}},timeout=4,
                                      clock=lambda:self.tick,pause=advance)
        self.assertEqual(self.tick,2)

    def test_running_task_waits_for_delayed_fresh_heartbeat(self):
        self.publish(self.request+timedelta(seconds=1),self.request)
        self.controls.states=lambda:self.scheduler()
        def advance(step):
            self.tick+=step
            if self.tick==50:self.publish(self.request+timedelta(seconds=1))
        self.controls.confirm_started({'lecture':{'running':True}},timeout=100,
                                      clock=lambda:self.tick,pause=advance)
        self.assertEqual(self.tick,50)

    def test_failed_transaction_confirmation_restores_old_config(self):
        before=self.c.path.read_bytes();data=copy.deepcopy(self.c.data)
        data['languages']['lecture']='en'
        events=[]
        class FixtureControls:
            confirmations=0
            def __init__(inner,config):pass
            def states(inner):return {'lecture':dict(running=True,enabled=True),
                                      'dialogue':dict(running=False,enabled=False)}
            def action(inner,kind,action):events.append((kind,action))
            def wait_stopped(inner,kinds):pass
            def restore(inner,previous):events.append(('restore','state'))
            def confirm_started(inner,previous):
                FixtureControls.confirmations+=1
                if FixtureControls.confirmations==1:raise RuntimeError('new worker not confirmed')
        manager=Manager(self.c.path,FixtureControls,lambda config:dict(ok=True,checks=[]))
        with self.assertRaisesRegex(RuntimeError,'исходный config восстановлен'):
            manager.apply_config(data)
        self.assertEqual(self.c.path.read_bytes(),before)
        self.assertIsNone(manager.pending())
        self.assertEqual(FixtureControls.confirmations,2)
        self.assertGreaterEqual(events.count(('restore','state')),2)

    def test_just_previous_session_cannot_confirm_restart(self):
        self.publish(self.request-timedelta(seconds=1))
        self.controls.states=lambda:self.scheduler()
        with self.assertRaisesRegex(RuntimeError,'не подтвердил'):self.confirm(timeout=2)

    def test_disabled_task_fails_with_diagnostic(self):
        self.controls.states=lambda:self.scheduler(running=False,enabled=False)
        with self.assertRaisesRegex(RuntimeError,'отключено'):self.confirm()

    @unittest.skipUnless(os.name=='nt','PowerShell fixture requires Windows')
    def test_scheduler_snapshot_reads_last_result_without_real_tasks(self):
        prefix=("function Get-ScheduledTask { param($TaskName) "
                "$state=if($TaskName -like '*Dialogue*'){'Ready'}else{'Running'}; "
                "[pscustomobject]@{State=$state;Settings=[pscustomobject]@{Enabled=$true}} }; "
                "function Get-ScheduledTaskInfo { param($TaskName) "
                "[pscustomobject]@{LastTaskResult=267009;LastRunTime=[datetime]'2026-01-01'} }; ")
        def fixture_ps(command,extra):
            environment=dict(os.environ,**extra)
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',prefix+command],
                                  env=environment,capture_output=True,encoding='utf-8',errors='replace',timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout.strip()
        self.controls.ps=fixture_ps
        states=self.controls.states()
        self.assertTrue(states['lecture']['running'],states)
        self.assertFalse(states['dialogue']['running'])
        self.assertEqual(states['lecture']['last_result'],267009)
        self.assertIn('2026',states['lecture']['last_run'])

    def test_start_request_is_recorded_before_launcher_returns(self):
        observed=[]
        self.controls.ps=lambda code,extra:observed.append(self.controls.starts.get('lecture'))
        self.controls.action('lecture','Start')
        self.assertIsNotNone(observed[0])


if __name__=='__main__':unittest.main()
