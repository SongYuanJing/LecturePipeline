"""Real files and deterministic HTTP streams; no installed app or supplier traffic."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installer'))
import download_components as d

URL = 'https://huggingface.co/pinned/revision/model.bin'
DATA = b'0123456789abcdef'
SHA = hashlib.sha256(DATA).hexdigest()


class Cancelled(RuntimeError):
    pass


class Response(io.BytesIO):
    def __init__(self, body=DATA, status=200, headers=None, fail=False):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Length': str(len(body)), 'ETag': '"pinned"', **(headers or {})}
        self.fail = fail

    def geturl(self):
        return URL

    def read(self, size):
        if self.fail and self.tell():
            raise TimeoutError('network timeout')
        return super().read(min(size, 4))


def ranged(offset=4, **kwargs):
    return Response(DATA[offset:], 206,
        {'Content-Range': f'bytes {offset}-{len(DATA)-1}/{len(DATA)}', **kwargs})


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.target = self.cache / SHA / 'model.bin'
        self.partial = self.target.parent / '.partial'
        self.metadata = self.target.parent / '.partial.json'
        threshold = patch.object(d, 'RESUME_THRESHOLD', 1)
        threshold.start(); self.addCleanup(threshold.stop)
        sleep = patch.object(d.time, 'sleep')
        sleep.start(); self.addCleanup(sleep.stop)

    def fetch(self, **kwargs):
        return d.fetch(URL, SHA, 'model.bin', self.cache, limit=len(DATA), expected_size=len(DATA), **kwargs)

    def interrupted(self):
        def cancel(*_):
            raise Cancelled('user cancel')
        with patch.object(d, 'open_url', return_value=Response()):
            with self.assertRaises(Cancelled):
                self.fetch(transfer=cancel)
        self.assertEqual(self.partial.read_bytes(), DATA[:4])
        self.assertFalse(self.target.exists())

    def test_cancel_then_successful_resume_and_cache_hit(self):
        self.interrupted()
        with patch.object(d, 'open_url', return_value=ranged()) as network:
            self.assertEqual(self.fetch().read_bytes(), DATA)
            self.assertEqual(network.call_args.args[1]['Range'], 'bytes=4-')
            self.assertEqual(network.call_args.args[1]['If-Range'], '"pinned"')
            self.fetch()
            network.assert_called_once()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.metadata.exists())

    def test_server_ignores_range_replaces_prefix(self):
        self.interrupted()
        with patch.object(d, 'open_url', return_value=Response()) as network:
            self.assertEqual(self.fetch().read_bytes(), DATA)
            network.assert_called_once()

    def test_wrong_content_range_or_identity_restarts_without_append(self):
        for change in ({'Content-Range': 'bytes 5-15/16'},
                       {'Content-Range': 'bytes 4-15/17'},
                       {'ETag': '"changed"'}, {'Content-Length': '500'}):
            with self.subTest(change=change):
                self.target.unlink(missing_ok=True)
                self.interrupted()
                with patch.object(d, 'open_url', side_effect=[ranged(**change), Response()]) as network:
                    self.assertEqual(self.fetch().read_bytes(), DATA)
                    self.assertNotIn('Range', network.call_args.args[1])

    def test_corrupt_oversized_or_mismatched_partial_rejected(self):
        for kind in ('corrupt', 'oversized', 'identity'):
            with self.subTest(kind=kind):
                self.target.unlink(missing_ok=True)
                self.interrupted()
                if kind == 'corrupt':
                    self.partial.write_bytes(b'xxxx')
                elif kind == 'oversized':
                    self.partial.write_bytes(DATA * 2)
                else:
                    state = json.loads(self.metadata.read_text()); state['url'] = URL + '/other'
                    self.metadata.write_text(json.dumps(state))
                with patch.object(d, 'open_url', return_value=Response()) as network:
                    self.assertEqual(self.fetch().read_bytes(), DATA)
                    self.assertNotIn('Range', network.call_args.args[1])

    def test_timeout_resumes_in_bounded_retry(self):
        with patch.object(d, 'open_url', side_effect=[Response(fail=True), ranged()]) as network:
            self.assertEqual(self.fetch().read_bytes(), DATA)
            self.assertEqual(network.call_count, 2)
            self.assertEqual(network.call_args.args[1]['Range'], 'bytes=4-')

    def test_retry_exhaustion_preserves_partial_for_next_invocation(self):
        with patch.object(d, 'open_url', side_effect=[Response(fail=True), TimeoutError(), TimeoutError()]) as network:
            with self.assertRaises(TimeoutError):
                self.fetch()
            self.assertEqual(network.call_count, 3)
        self.assertEqual(self.partial.read_bytes(), DATA[:4])
        with patch.object(d, 'open_url', return_value=ranged()):
            self.assertEqual(self.fetch().read_bytes(), DATA)

    def test_final_sha_mismatch_discards_partial_without_publication(self):
        self.interrupted()
        with patch.object(d, 'open_url', return_value=Response(b'x' * 12, 206,
                {'Content-Range': 'bytes 4-15/16'})):
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                self.fetch()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.metadata.exists())

    def test_crash_tail_truncated_to_checksummed_offset(self):
        self.interrupted()
        with self.partial.open('ab') as stream:
            stream.write(b'unknown')
        with patch.object(d, 'open_url', return_value=ranged()) as network:
            self.assertEqual(self.fetch().read_bytes(), DATA)
            self.assertEqual(network.call_args.args[1]['Range'], 'bytes=4-')

    def test_wrong_full_size_and_oversized_body_never_publish(self):
        for response in (Response(DATA, headers={'Content-Length': '17'}),
                         Response(DATA + b'x', headers={'Content-Length': '16'})):
            with self.subTest(response=response), patch.object(d, 'open_url', return_value=response):
                with self.assertRaisesRegex(ValueError, 'size'):
                    self.fetch()
                self.assertFalse(self.target.exists())
                self.assertFalse(self.partial.exists())


if __name__ == '__main__':
    unittest.main()
