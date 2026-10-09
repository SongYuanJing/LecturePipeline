import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_local_finalize import fixture,dump
import human_ux as ux
from lecture_inbox import Inbox,bind,hints


class MultipartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);c=fixture(self.base)
        self.source=self.base/'Audio 课程';self.source.mkdir()
        self.c=bind(c,'SUBJECT',self.source,self.base/'Results',settle=10,poll=5)
        self.clock=0;self.restart();self.p=ux.pipeline(self.c);self.subject=self.c.subjects()['SUBJECT']

    def restart(self):
        self.inbox=Inbox(self.c,monotonic=lambda:self.clock,now=lambda:'2026-10-10T00:00:00+00:00')

    def write(self,*names):
        for name in names:(self.source/name).write_bytes(name.encode('utf8'))

    def scan(self,n=1):
        for _ in range(n):self.clock+=5;result=self.inbox.scan()
        return result

    def ready(self):return list(self.subject['audio_dir'].glob('*.READY.json'))

    def assert_group(self,count=3):
        self.assertEqual(len(self.ready()),1)
        ready=json.loads(self.ready()[0].read_text(encoding='utf8'))
        self.assertEqual(ready['expected_parts'],count)
        members=ready['intake']['members']
        self.assertEqual([m['part_hint'] for m in members],list(range(1,count+1)))
        parts=self.p.collect_lectures(self.subject['audio_dir'])[ready['lecture']]
        for file,member in zip(parts,members):self.assertEqual(file.read_bytes(),Path(member['source_path']).read_bytes())
        return ready

    def test_unicode_basic_and_completed_restart(self):
        self.write('微观2026_10_09_3.wav','微观2026_10_09_1.wav','微观2026_10_09_2.wav')
        result=self.scan(5);ready=self.assert_group()
        self.assertEqual(ready['intake']['lecture_date'],'2026-10-09')
        self.assertTrue(ready['intake']['imported_at'].startswith('2026-10-10'))
        self.assertEqual(len(result['groups']),1)
        before={f.name:(ux.sha(f),f.stat().st_mtime_ns) for f in self.subject['audio_dir'].glob('*') if f.is_file()}
        self.restart()
        with patch.object(ux,'add_lecture',side_effect=AssertionError('duplicate')):self.scan(6)
        self.assertEqual(before,{f.name:(ux.sha(f),f.stat().st_mtime_ns) for f in self.subject['audio_dir'].glob('*') if f.is_file()})

    def test_other_style_and_part_equivalent(self):
        self.write('3- 2026_09_11_1.wav','3- 2026_09_11_part2.wav')
        self.scan(5);self.assert_group(2)

    def test_same_date_different_stem(self):
        self.write(*[f'{stem}-2026_10_09_{n}.wav' for stem in ('A','B') for n in (1,2)])
        self.scan(5);self.assertEqual(len(self.ready()),2)
        self.assertTrue(all(json.loads(f.read_text())['expected_parts']==2 for f in self.ready()))

    def test_slow_arrival_resets_group_window(self):
        self.write('foo20261009_1.wav');self.scan(3);self.assertFalse(self.ready())
        self.write('foo20261009_2.wav');self.scan(3);self.assertFalse(self.ready())
        self.write('foo20261009_3.wav');self.scan(4);self.assertFalse(self.ready())
        self.scan();self.assert_group()

    def test_missing_part_review_then_arrival(self):
        self.write('foo20261009_1.wav','foo20261009_3.wav')
        r=self.scan(5);self.assertFalse(self.ready());self.assertEqual(r['groups'][0]['status'],'review')
        self.assertIn('пропущены',r['groups'][0]['error'])
        self.restart();r=self.scan();self.assertEqual(r['groups'][0]['status'],'review')
        self.assertIn('пропущены',r['groups'][0]['error'])
        self.write('foo20261009_2.wav');self.scan(5);self.assert_group()

    def test_duplicate_hint_review(self):
        self.write('foo20261009_1.wav','foo20261009_part1.wav','foo20261009_2.wav')
        r=self.scan(5);self.assertFalse(self.ready());self.assertIn('Повторяющийся',r['groups'][0]['error'])

    def test_conflicting_dates_review_not_majority(self):
        self.write('foo2026_10_09_1.wav','foo2026_10_08_2.wav','foo2026_10_09_3.wav')
        r=self.scan(5);self.assertFalse(self.ready())
        self.assertTrue(all(g['status']=='review' and 'Конфликт дат' in g['error'] for g in r['groups']))

    def test_no_hint_remains_single_file(self):
        self.write('foo2026_10_09.wav');r=self.scan(3)
        self.assertEqual(len(self.ready()),1);self.assertEqual(r['groups'],[])

    def test_restart_accumulation_then_third_part(self):
        self.write('foo20261009_1.wav','foo20261009_2.wav');r=self.scan(3)
        gid=r['groups'][0]['group_id'];self.restart();self.write('foo20261009_3.wav')
        self.scan(4);self.assertFalse(self.ready());r=self.scan();self.assert_group()
        self.assertEqual(r['groups'][0]['group_id'],gid)

    def test_lost_ack_reuses_ready(self):
        self.write('foo20261009_1.wav','foo20261009_2.wav');self.scan(5)
        state=json.loads(self.inbox.path.read_text());group=next(iter(state['groups'].values()));group['status']='ready'
        for row in state['sources'].values():row['status']='ready';row.pop('lecture_key',None)
        dump(self.inbox.path,state);self.restart()
        with patch.object(ux.shutil,'copy2',side_effect=AssertionError('duplicate copy')):
            r=self.scan();self.assertEqual(r['groups'][0]['status'],'queued')
        self.assert_group(2)

    def test_interrupted_copy_recovers_reserved_key(self):
        self.write('foo20261009_1.wav','foo20261009_2.wav');self.scan(4)
        with patch.object(ux.shutil,'copy2',side_effect=OSError('interrupted')):r=self.scan()
        key=r['groups'][0]['lecture_key'];self.assertFalse(self.ready());self.restart()
        r=self.scan(5);self.assert_group(2);self.assertEqual(r['groups'][0]['lecture_key'],key)

    def test_member_change_after_reservation_requires_review(self):
        self.write('foo20261009_1.wav','foo20261009_2.wav');self.scan(4)
        with patch.object(ux.shutil,'copy2',side_effect=OSError('interrupted')):self.scan()
        self.write('foo20261009_3.wav');self.restart();r=self.scan(5)
        self.assertFalse(self.ready());self.assertIn('после начала',r['groups'][0]['error'])

    def test_failed_group_reservation_not_reused_by_other_group_or_manual(self):
        self.write('A20261009_1.wav','B20261009_1.wav');self.scan(4)
        original=ux.shutil.copy2
        def fail_a(source,target):
            if Path(source).name.startswith('A'):raise OSError('interrupted')
            return original(source,target)
        with patch.object(ux.shutil,'copy2',side_effect=fail_a):r=self.scan()
        a=next(g for g in r['groups'] if g['session_stem'].startswith('a'))
        b=next(g for g in r['groups'] if g['session_stem'].startswith('b'))
        self.assertNotEqual(a['lecture_key'],b['lecture_key'])
        manual=self.base/'manual.wav';manual.write_bytes(b'manual')
        with self.assertRaisesRegex(ValueError,'зарезервирован'):
            ux.add_lecture(self.c,'SUBJECT','2026-10-09',int(a['lecture_key'].split('_')[0]),[manual])
        self.restart();self.scan(5);self.assertEqual(len(self.ready()),2)

    def test_late_part_is_review_not_second_lecture(self):
        self.write('foo20261009_1.wav');self.scan(5);self.write('foo20261009_2.wav')
        self.restart();r=self.scan(5);self.assertEqual(len(self.ready()),1)
        late=next(x for x in r['sources'] if x['part_hint']==2)
        self.assertEqual(late['status'],'review');self.assertIn('Поздняя',late['error'])

    def test_disappeared_discovered_member_is_review(self):
        self.write('foo20261009_1.wav','foo20261009_2.wav');self.scan(3)
        (self.source/'foo20261009_2.wav').unlink();self.restart();r=self.scan(5)
        self.assertFalse(self.ready());self.assertIn('отсутствует',r['groups'][0]['error'])

    def test_open_writer_blocks_group(self):
        self.write('foo20261009_1.wav','foo20261009_2.wav')
        with (self.source/'foo20261009_2.wav').open('ab'):
            self.scan(6);self.assertFalse(self.ready())
        self.scan(3);self.assert_group(2)

    def test_manual_multipart_unchanged(self):
        a=self.base/'manual-a.wav';b=self.base/'manual-b.wav';a.write_bytes(b'a');b.write_bytes(b'b')
        key=ux.add_lecture(self.c,'SUBJECT','2026-10-09',1,[b,a])
        parts=self.p.collect_lectures(self.subject['audio_dir'])[key]
        self.assertEqual([x.read_bytes() for x in parts],[b'b',b'a'])
        self.assertEqual(self.p.read_ready(self.subject,key,parts)['expected_parts'],2)

    def test_existing_phase3a_publication_not_regrouped(self):
        self.write('foo20261009_1.wav');file=self.source/'foo20261009_1.wav'
        self.scan();state=json.loads(self.inbox.path.read_text());row=next(iter(state['sources'].values()))
        key=ux.add_lecture(self.c,'SUBJECT',row['lecture_date'],1,[file],intake=row)
        row.update(status='queued',lecture_key=key);state.pop('groups',None);dump(self.inbox.path,state)
        self.write('foo20261009_2.wav');self.restart();r=self.scan(5)
        self.assertEqual(len(self.ready()),1);self.assertEqual(r['groups'][0]['status'],'review')


if __name__=='__main__':unittest.main()
