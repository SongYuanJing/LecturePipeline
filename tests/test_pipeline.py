import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import lecture_pipeline as p


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = self.root / 'audio'
        self.raw = self.root / 'raw'
        self.audio.mkdir()
        self.raw.mkdir()
        self.key = '05_2026-09-25'
        self.cfg = dict(audio_dir=self.audio, raw_dir=self.raw, title='test', prompt='', hotwords='')
        self.state = {'version': 1, 'lectures': {}}
        self.sf = self.root / 'state.json'
        p.save_state(self.sf, self.state)
        self.log = self.root / 'pipeline.log'

    def parts(self, numbers):
        for n in numbers:
            (self.audio / f'5_2026_09_25_{n}.m4a').write_bytes(f'audio {n}'.encode())
        return p.collect_lectures(self.audio)[self.key]

    def args(self, **kwargs):
        return SimpleNamespace(prepare_ready=None, parts=None, reprocess=[], dry_run=False, **kwargs)

    def run_pipeline(self, args, transcriber):
        with patch.object(p, 'discover_layout', return_value=(self.sf, self.log, {'01': self.cfg})), \
             patch.object(p, 'WhisperModel', return_value=object()), \
             patch.object(p, 'transcribe_one', side_effect=transcriber), patch.object(p, 'safe_print'):
            return p.run(args)

    def test_no_ready_does_not_transcribe(self):
        self.parts([1, 2])
        self.assertEqual(self.run_pipeline(self.args(), AssertionError('must not transcribe')), 0)

    def test_missing_1_3_even_if_ready_arrives_first(self):
        parts = self.parts([1, 2, 3, 4, 5])
        p.prepare_ready(self.cfg, self.key, 5)
        parts[0].unlink()
        parts[2].unlink()
        parts = p.collect_lectures(self.audio)[self.key]
        with self.assertRaisesRegex(ValueError, r'\[1, 3\]'):
            p.read_ready(self.cfg, self.key, parts)
        self.assertEqual(self.run_pipeline(self.args(), AssertionError()), 0)

    def test_full_pipeline_and_completed_no_repeat(self):
        parts = self.parts([1, 2, 3, 4, 5])
        p.prepare_ready(self.cfg, self.key, 5)
        result = ([(0.0, 1.0, '测试')], SimpleNamespace(language='zh'))
        self.assertEqual(self.run_pipeline(self.args(), lambda *a: result), 0)
        saved = p.load_state(self.sf)
        rec = saved['lectures']['01/' + self.key]
        self.assertEqual(rec['sources'], [p.source_signature(f) for f in parts])
        manifest = json.loads((self.raw / self.key / (self.key + '_manifest.json')).read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['outputs']), 5)
        self.assertEqual(len(list((self.raw / self.key).glob('*.srt'))), 5)
        with patch.object(p, 'MODEL_NAME', 'different-model'):
            self.assertEqual(self.run_pipeline(self.args(), AssertionError()), 0)
        args = self.args()
        args.reprocess = ['01/' + self.key]
        self.assertEqual(self.run_pipeline(args, lambda *a: result), 0)
        self.assertEqual(len(list((self.raw / '.history').iterdir())), 1)

    def test_duplicate_extra_zero_and_single(self):
        for numbers, count in [([1, 1], 2), ([1, 2, 3], 2), ([0, 1], 2)]:
            with self.assertRaises(ValueError):
                p.check_numbers([Path(f'5_2026_09_25_p{n}.wav') for n in numbers], count)
        p.check_numbers([Path('recording.wav')], 1)
        with self.assertRaises(ValueError):
            p.check_numbers([], 0)

    def test_same_size_changed_audio_rejected(self):
        parts = self.parts([1])
        p.prepare_ready(self.cfg, self.key, 1)
        parts[0].write_bytes(b'broken!')
        with self.assertRaises(ValueError):
            with p.verified_inputs(self.cfg, self.key, parts):
                self.fail('must not yield')

    def test_truncated_empty_and_malformed_ready(self):
        parts = self.parts([1])
        p.prepare_ready(self.cfg, self.key, 1)
        parts[0].write_bytes(b'')
        with self.assertRaises(ValueError):
            p.read_ready(self.cfg, self.key, parts)
        p.ready_path(self.cfg, self.key).write_text('{')
        with self.assertRaises(ValueError):
            p.read_ready(self.cfg, self.key, parts)

    def test_input_snapshot_is_independent(self):
        parts = self.parts([1])
        p.prepare_ready(self.cfg, self.key, 1)
        with p.verified_inputs(self.cfg, self.key, parts) as copies:
            original = copies[0].read_bytes()
            parts[0].write_bytes(b'changed during recognition')
            self.assertEqual(copies[0].read_bytes(), original)

    def test_completed_record_protects_missing_outputs_changed_sources(self):
        self.state['lectures']['01/' + self.key] = {'status': 'completed', 'model': 'old'}
        self.assertFalse(p.needs_processing(self.state, '01', self.key, [], self.raw))
        self.assertTrue(p.needs_processing(self.state, '01', self.key, [], self.raw, True))

    def test_four_completed_records_are_protected(self):
        state = {'version': 1, 'lectures': {f'SUBJECT/{i:02d}_2020-01-01': {'status': 'completed', 'model': 'old'} for i in range(1,5)}}
        self.assertEqual(len(state['lectures']), 4)
        with patch.object(p, 'MODEL_NAME', 'new-model'):
            for key in state['lectures']:
                code, lecture = key.split('/')
                self.assertFalse(p.needs_processing(state, code, lecture, [], self.raw))

    def test_missing_corrupt_and_invalid_state_fail_closed(self):
        self.sf.unlink()
        with self.assertRaises(FileNotFoundError):
            p.load_state(self.sf)
        for text in ['{', '{}', '{"lectures": []}', '{"lectures":{"a":null}}']:
            self.sf.write_text(text)
            with self.assertRaises((ValueError, TypeError)):
                p.load_state(self.sf)
            self.assertEqual(self.sf.read_text(), text)

    def test_reprocess_failure_preserves_previous_result_and_completed_state(self):
        parts = self.parts([1, 2])
        p.prepare_ready(self.cfg, self.key, 2)
        result = ([(0, 1, 'original')], SimpleNamespace(language='zh'))
        self.run_pipeline(self.args(), lambda *a: result)
        prior_state = self.sf.read_bytes()
        old = {f.name: f.read_bytes() for f in (self.raw / self.key).iterdir()}
        args = self.args()
        args.reprocess = ['01/' + self.key]
        self.assertEqual(self.run_pipeline(args, [result, RuntimeError('test failure')]), 1)
        self.assertEqual(prior_state, self.sf.read_bytes())
        self.assertEqual(old, {f.name: f.read_bytes() for f in (self.raw / self.key).iterdir()})

    def test_reprocess_does_not_bypass_ready(self):
        self.parts([1])
        args = self.args()
        args.reprocess = ['01/' + self.key]
        with self.assertRaisesRegex(ValueError, 'reprocess'):
            self.run_pipeline(args, AssertionError())

    def test_unknown_reprocess_rejected(self):
        args = self.args()
        args.reprocess = ['01/typo']
        with self.assertRaises(ValueError):
            self.run_pipeline(args, AssertionError())

    def test_dry_run_no_outputs_or_state_changes(self):
        self.parts([1])
        p.prepare_ready(self.cfg, self.key, 1)
        before = self.sf.read_bytes()
        args = self.args()
        args.dry_run = True
        self.assertEqual(self.run_pipeline(args, AssertionError()), 0)
        self.assertEqual(before, self.sf.read_bytes())
        self.assertEqual(list(self.raw.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
