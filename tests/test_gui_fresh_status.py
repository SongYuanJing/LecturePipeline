import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_local_finalize import fixture, dump, APP

sys.path.insert(0, str(APP / 'gui_v1.8'))
import adapter


class FreshStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.c = fixture(Path(self.temp.name))
        self.paths = [self.c.worker_home / 'worker_status.json',
                      self.c.dialogue_home / 'status.json']

    def snapshot(self):
        return adapter.snapshot(self.c.path, catalog={'items': []})

    def test_missing_observations_not_errors_or_created(self):
        before = self.c.path.read_bytes()
        view = self.snapshot()
        for path in self.paths:
            self.assertFalse(path.exists())
            self.assertFalse(any(str(path) in e for e in view['errors']))
        self.assertEqual(view['lecture_worker'], 'Нет heartbeat')
        self.assertEqual(view['dialogue_worker'], 'Нет heartbeat')
        self.assertEqual(self.c.path.read_bytes(), before)

    def test_corrupt_and_denied_observations_still_reported(self):
        for path in self.paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{broken', encoding='utf8')
        view = self.snapshot()
        for path in self.paths:
            self.assertTrue(any(str(path) in e for e in view['errors']))
        original = adapter.read
        def denied(path):
            if path in self.paths:
                raise PermissionError('denied')
            return original(path)
        with patch.object(adapter, 'read', side_effect=denied):
            view = self.snapshot()
        self.assertEqual(sum('denied' in e for e in view['errors']), 2)

    def test_missing_authoritative_ledger_still_reported(self):
        self.c.state.unlink()
        self.assertTrue(any(str(self.c.state) in e for e in self.snapshot()['errors']))

    def test_existing_heartbeat_preserved(self):
        from datetime import datetime, timezone
        for path in self.paths:
            dump(path, {'heartbeat': datetime.now(timezone.utc).isoformat(), 'worker': 'RUNNING'})
        view = self.snapshot()
        self.assertEqual(view['lecture_worker'], 'Работает')
        self.assertEqual(view['dialogue_worker'], 'Работает')
