import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import lecture_pipeline as p
import lecture_worker as w


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'local'
        self.audio = self.root / 'Drive' / 'audio'
        self.audio.mkdir(parents=True)
        self.raw = self.root / 'Drive' / 'raw'
        self.raw.mkdir()
        self.sf = self.root / 'Drive' / 'state.json'
        p.save_state(self.sf, {'version': 1, 'lectures': {}})
        self.cfg = dict(audio_dir=self.audio, raw_dir=self.raw, title='test', prompt='', hotwords='')
        self.key = '05_2026-09-25'
        self.identity = '01/' + self.key
        self.now = 1000.0
        self.worker = self.new_worker()
        self.calls = 0
        self.patchers = [patch.object(p, 'discover_layout', return_value=(self.sf, self.root / 'pipeline.log', {'01': self.cfg})),
                         patch.object(p, 'WhisperModel', return_value=object()),
                         patch.object(p, 'transcribe_one', side_effect=self.recognize), patch.object(p, 'safe_print')]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def new_worker(self):
        return w.Worker(self.home, clock=lambda: self.now, monotonic=lambda: self.now)

    def recognize(self, *args):
        self.calls += 1
        return [(0, 1, '测试')], SimpleNamespace(language='zh')

    def parts(self, *numbers):
        for n in numbers:
            (self.audio / f'5_2026_09_25_{n}.m4a').write_bytes(f'audio {n}'.encode())

    def signal(self, count=2, suffix=''):
        (self.audio / f'READY {self.key} {count}{suffix}').mkdir(exist_ok=True)

    def cycle(self, advance=0):
        self.now += advance
        self.worker.safe_cycle()

    def status(self):
        return self.worker.rows[self.identity]['status']

    def test_signal_before_audio_then_missing_then_complete(self):
        self.signal(5)
        self.cycle()
        self.assertEqual(self.status(), 'WAITING')
        self.parts(2, 4, 5)
        self.cycle(1000)
        self.assertIn('[1, 3]', self.worker.rows[self.identity]['detail'])
        self.assertEqual(self.calls, 0)
        self.parts(1, 3)
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.status(), 'DONE')
        self.assertEqual(self.calls, 5)

    def test_signal_after_files_stability_starts_at_signal(self):
        self.parts(1, 2)
        self.cycle()
        self.assertEqual(self.status(), 'COLLECTING')
        self.signal()
        self.cycle(1000)
        self.assertEqual(self.calls, 0)
        self.cycle(119)
        self.assertEqual(self.calls, 0)
        self.cycle(1)
        self.assertEqual(self.calls, 2)

    def test_changing_file_same_size_and_restored_timestamp(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        path = self.audio / '5_2026_09_25_1.m4a'
        import os
        st = path.stat()
        path.write_bytes(b'changed')
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.cycle(120)
        self.assertEqual(self.calls, 0)
        self.cycle(120)
        self.assertEqual(self.calls, 2)

    def test_restart_waits_full_interval_again(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        self.worker = self.new_worker()
        self.cycle(120)
        self.assertEqual(self.calls, 0)
        self.cycle(120)
        self.assertEqual(self.calls, 2)

    def test_duplicate_ready_and_restart_no_repeat(self):
        self.parts(1, 2)
        self.signal()
        self.signal(suffix=' (1)')
        self.cycle()
        self.cycle(120)
        self.worker = self.new_worker()
        self.cycle(1000)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.status(), 'DONE')

    def test_completed_ignores_signal_model_and_missing_audio(self):
        p.save_state(self.sf, {'version': 1, 'lectures': {self.identity: {'status': 'completed', 'model': 'old'}}})
        self.signal()
        self.cycle()
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.status(), 'DONE')

    def test_whisper_error_backoff_restart_then_recover(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        with patch.object(p, 'transcribe_one', side_effect=RuntimeError('Whisper failed')):
            self.cycle(120)
        self.assertEqual(self.status(), 'ERROR')
        self.worker = self.new_worker()
        self.cycle(299)
        self.assertEqual(self.calls, 0)
        self.cycle(1)
        self.cycle(120)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.status(), 'DONE')

    def test_publish_failure_resume_without_whisper(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        original = w.shutil.copyfile
        def fail_drive(source, target, *args, **kwargs):
            if self.raw in Path(target).parents:
                raise OSError('Drive temporarily unavailable')
            return original(source, target, *args, **kwargs)
        with patch.object(w.shutil, 'copyfile', side_effect=fail_drive):
            self.cycle(120)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.worker.journal['jobs'][self.identity]['phase'], 'publishing')
        self.worker = self.new_worker()
        self.cycle(300)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.status(), 'DONE')

    def test_state_commit_failure_resume_after_raw_exists(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        original = p.save_state
        def fail_state(path, data):
            if path == self.sf:
                raise OSError('state write failed')
            original(path, data)
        with patch.object(p, 'save_state', side_effect=fail_state):
            self.cycle(120)
        self.assertTrue((self.raw / self.key / f'{self.key}_raw.txt').exists())
        self.worker = self.new_worker()
        self.cycle(300)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.status(), 'DONE')

    def test_drive_disappears_and_returns(self):
        with patch.object(p, 'discover_layout', side_effect=OSError('Drive offline')):
            self.cycle()
        self.assertEqual(self.worker.worker_state, 'ERROR')
        self.parts(1, 2)
        self.signal()
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.calls, 2)

    def test_strict_state_no_reset_and_recovery(self):
        self.parts(1, 2)
        self.signal()
        saved = self.sf.read_bytes()
        self.sf.write_text('{')
        self.cycle()
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.sf.read_text(), '{')
        self.sf.write_bytes(saved)
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.calls, 2)

    def test_existing_sha_ready_never_rewritten(self):
        self.parts(1, 2)
        p.prepare_ready(self.cfg, self.key, 2)
        saved = p.ready_path(self.cfg, self.key).read_bytes()
        (self.audio / '5_2026_09_25_1.m4a').write_bytes(b'changed')
        self.signal()
        self.cycle()
        self.cycle(1000)
        self.assertEqual(self.calls, 0)
        self.assertEqual(p.ready_path(self.cfg, self.key).read_bytes(), saved)

    def test_conflicting_counts_and_extra_parts_block(self):
        self.parts(1, 2, 3)
        self.signal(2)
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.calls, 0)
        self.signal(3)
        self.cycle(120)
        self.assertIn('конфликт', self.worker.rows[self.identity]['detail'])

    def test_legacy_ready_without_remote_folder(self):
        self.parts(1, 2)
        p.prepare_ready(self.cfg, self.key, 2)
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.status(), 'DONE')

    def test_transcribing_crash_recovered_on_restart(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        with patch.object(p, 'transcribe_one', side_effect=SystemExit('simulated kill')):
            with self.assertRaises(SystemExit):
                self.cycle(120)
        self.worker = self.new_worker()
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.status(), 'DONE')

    def test_corrupt_journal_not_reset(self):
        self.worker.journal_path.write_text('{')
        with self.assertRaises(ValueError):
            self.new_worker()

    def test_paused_open_writer_blocks_even_after_stability_time(self):
        self.parts(1, 2)
        self.signal()
        path = self.audio / '5_2026_09_25_1.m4a'
        with path.open('ab') as writer:
            self.cycle()
            self.cycle(1000)
            self.assertEqual(self.calls, 0)
        self.cycle()
        self.cycle(120)
        self.assertEqual(self.calls, 2)

    def test_owned_ready_recovers_if_sync_changes_after_seal(self):
        self.parts(1, 2)
        self.signal()
        self.cycle()
        with patch.object(p, 'verified_inputs', side_effect=OSError('sync changed before snapshot')):
            self.cycle(120)
        (self.audio / '5_2026_09_25_1.m4a').write_bytes(b'updated audio')
        self.worker = self.new_worker()
        self.cycle(300)
        self.cycle(120)
        self.assertEqual(self.calls, 2)
        self.assertEqual(self.status(), 'DONE')

    def test_lock_excludes_second_worker_and_cli(self):
        lock = self.home / 'lecture_pipeline.lock'
        with p.pipeline_lock(lock):
            with self.assertRaises(OSError):
                with p.pipeline_lock(lock):
                    self.fail('duplicate lock')
        with p.pipeline_lock(lock):
            pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
