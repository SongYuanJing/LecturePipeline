"""Targeted read-only boundary/contract tests. All mutations use disposable fixtures."""
from datetime import datetime, timezone
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/gui_web'))
from readonly_snapshot import SnapshotProvider, ReadFence
from readonly_host import handler_for
from visual_fixture import create_fixture, dump


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fingerprints(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='VIC28-disposable-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'DEV 演示'
        self.config = create_fixture(self.root)
        self.provider = SnapshotProvider(self.root, self.config)
        self.worker = self.root / 'app/run/workspaces/visual/worker_status.json'

    def row(self, value, key='01_2026-10-20'):
        return next(row for row in value['catalog'] if row['lecture_key'] == key)

    def test_existing_catalog_authority_and_unicode(self):
        value = self.provider.snapshot()
        self.assertTrue(value['available'])
        self.assertEqual(value['errors'], [])
        self.assertEqual(value['counts']['total'], 13)
        self.assertEqual(value['counts']['waiting_ai'], 1)
        self.assertEqual(value['counts']['done'], 1)
        self.assertIn('运筹学', self.row(value)['course_display_name'])
        self.assertEqual(self.row(value)['progress']['part_index'], 2)
        self.assertEqual(self.row(value)['progress']['part_count'], 3)
        self.assertEqual(self.row(value)['progress']['percent'], 57)
        self.assertEqual(value['device']['observed']['device'], 'cuda')
        self.assertEqual(value['pending'][0]['parts'], [1, 3])

    def test_all_catalog_stages_have_explicit_visual_examples(self):
        value = self.provider.snapshot()
        self.assertEqual({r['status'] for r in value['catalog']},
                         {'asr','ready','waiting_ai','raw','word','vocabulary','done','error',
                          'publishing','ai_ready','review','problem','waiting'})
        self.assertEqual(value['counts']['problems'], 3)
        self.assertTrue(self.row(value, '12_2026-10-10')['reasons'])

    def test_fixture_scenarios_use_backend_freshness_rules(self):
        for scenario in ('stale', 'unknown', 'preparing'):
            root = self.base / scenario
            config = create_fixture(root, scenario)
            value = SnapshotProvider(root, config, fixture=True).snapshot()
            self.assertEqual(value['errors'], [])
            progress = self.row(value)['progress']
            if scenario == 'stale':
                self.assertEqual(value['workers'][0]['health'], 'stale')
                self.assertIsNone(progress)
                self.assertIsNone(value['device']['observed'])
            else:
                self.assertEqual(progress['part_index'], 2)
                self.assertEqual(progress['part_count'], 3)
                self.assertIsNone(progress['percent'])
                self.assertIsNone(progress['eta_seconds'])
                self.assertEqual(progress['stage'], 'preparing' if scenario == 'preparing' else 'asr')

    def test_snapshot_has_zero_mutations_and_no_content_reads(self):
        before = fingerprints(self.root)
        first = self.provider.snapshot()
        self.provider.snapshot()
        self.assertEqual(before, fingerprints(self.root))
        self.assertFalse(first['read_audit']['mutations_allowed'])
        self.assertTrue(all(Path(p).suffix not in {'.wav', '.docx', '.xlsx'} for p in first['read_audit']['files']))

    def test_read_fence_blocks_writes_and_processes(self):
        path = self.root / 'attempt.txt'
        with ReadFence(self.root).active():
            with self.assertRaises(PermissionError):
                path.write_text('must not be written')
            with self.assertRaises(PermissionError):
                subprocess.Popen(['VIC28-no-such-program'])
        self.assertFalse(path.exists())

    def test_read_fence_does_not_open_dictionary_content(self):
        book = self.root / 'vocabulary.xlsx'
        book.write_bytes(b'protected disposable fixture')
        with ReadFence(self.root).active(), self.assertRaises(PermissionError):
            book.read_bytes()

    def test_missing_heartbeat_is_unknown_not_stopped(self):
        self.worker.unlink()
        value = self.provider.snapshot()
        worker = value['workers'][0]
        self.assertEqual(worker['health'], 'missing')
        self.assertIsNone(worker['reported_state'])
        self.assertIsNone(worker['scheduler_state'])
        self.assertIsNone(self.row(value)['progress'])
        self.assertIsNone(value['device']['observed'])

    def test_stale_heartbeat_hides_live_progress_and_device(self):
        worker = load(self.worker)
        worker['heartbeat'] = '2000-01-01T00:00:00+00:00'
        dump(self.worker, worker)
        value = self.provider.snapshot()
        self.assertEqual(self.row(value)['status'], 'asr')
        self.assertIsNone(self.row(value)['progress'])
        self.assertEqual(value['workers'][0]['health'], 'stale')
        self.assertIsNone(value['device']['observed'])

    def test_invalid_heartbeat_has_no_fresh_progress(self):
        worker = load(self.worker)
        worker['heartbeat'] = 'not-a-date'
        dump(self.worker, worker)
        value = self.provider.snapshot()
        self.assertEqual(value['workers'][0]['health'], 'invalid')
        self.assertIsNone(self.row(value)['progress'])

    def test_unknown_percent_eta_keep_verified_part_count(self):
        worker = load(self.worker)
        progress = next(iter(worker['lectures'].values()))['progress']
        progress.update(percent=None, eta_seconds=None, eta_available=False)
        dump(self.worker, worker)
        p = self.row(self.provider.snapshot())['progress']
        self.assertEqual((p['part_index'], p['part_count']), (2, 3))
        self.assertIsNone(p['percent'])
        self.assertIsNone(p['eta_seconds'])

    def test_word_before_vocabulary_is_not_done(self):
        row = self.row(self.provider.snapshot(), '06_2026-10-16')
        self.assertEqual(row['stages']['word'], 'available')
        self.assertEqual(row['status'], 'vocabulary')

    def test_missing_required_state_does_not_report_zero_counts(self):
        (self.root / 'data/visual/system/state.json').unlink()
        value = self.provider.snapshot()
        self.assertTrue(value['errors'])
        self.assertIsNone(value['counts'])

    def test_config_cannot_redirect_to_another_root(self):
        config = load(self.config)
        outside = self.base / 'NOT-DEV'
        outside.mkdir()
        config['data_root'] = str(outside)
        dump(self.config, config)
        value = self.provider.snapshot()
        self.assertFalse(value['available'])
        self.assertIsNone(value['counts'])
        self.assertTrue(value['errors'])

    def test_absolute_authority_paths_outside_dev_are_rejected(self):
        path = self.root / 'data/visual/system/ai_state.json'
        state = load(path)
        next(iter(state['processed'].values()))['output_docx_local_path'] = str(self.base / 'NOT-DEV/lecture.docx')
        dump(path, state)
        value = self.provider.snapshot()
        self.assertTrue(value['errors'])
        self.assertIsNone(value['counts'])

    def test_visual_fixture_is_explicit_and_frozen(self):
        provider = SnapshotProvider(self.root, self.config, fixture=True)
        first = provider.snapshot()
        self.assertEqual(first['source']['kind'], 'fixture')
        self.assertTrue(first['source']['frozen'])
        self.worker.unlink()
        self.assertIs(first, provider.snapshot())

    def test_fixture_cannot_overwrite_unowned_directory(self):
        folder = self.base / 'unowned'
        folder.mkdir()
        (folder / 'keep.txt').write_text('keep')
        with self.assertRaises(ValueError):
            create_fixture(folder)
        self.assertEqual((folder / 'keep.txt').read_text(), 'keep')

    def test_http_is_get_only_and_no_arbitrary_file_route(self):
        before = fingerprints(self.root)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.provider))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(server.server_address[1])
        try:
            with urlopen(url + '/api/v1/snapshot') as response:
                value = json.load(response)
            self.assertEqual(value['contract'], 'vic28.dashboard/1')
            for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                with self.assertRaises(HTTPError) as result:
                    urlopen(Request(url + '/api/v1/snapshot', data=b'{}', method=method))
                self.assertEqual(result.exception.code, 405)
            with self.assertRaises(HTTPError) as result:
                urlopen(url + '/../../config.json')
            self.assertEqual(result.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(before, fingerprints(self.root))


if __name__ == '__main__':
    unittest.main(verbosity=2)
