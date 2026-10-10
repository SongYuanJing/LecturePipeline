import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/app'))
from ai_queue import atomic


class JournalAtomicTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'journal.json';atomic(self.path,{'old':True})

    @unittest.skipUnless(os.name=='nt','Windows sharing contract')
    def test_real_windows_reader_release_allows_retry(self):
        reader=self.path.open('rb');released=threading.Event()
        def release():
            time.sleep(.08);reader.close();released.set()
        thread=threading.Thread(target=release);thread.start()
        try:
            with patch('ai_queue.os.replace',wraps=os.replace) as replace:
                atomic(self.path,{'new':True})
                self.assertGreater(replace.call_count,1)
        finally:thread.join();reader.close()
        self.assertTrue(released.is_set());self.assertEqual(json.loads(self.path.read_text()),{'new':True})
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])

    @unittest.skipUnless(os.name=='nt','Windows sharing contract')
    def test_persistent_denial_bounded_and_old_journal_retained(self):
        before=self.path.read_bytes()
        with self.path.open('rb'),patch('ai_queue.time.sleep') as sleep:
            with self.assertRaises(PermissionError):atomic(self.path,{'new':True})
        self.assertEqual(sleep.call_count,5);self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])

    def test_other_error_not_retried(self):
        with patch('ai_queue.os.replace',side_effect=OSError('disk error')) as replace:
            with self.assertRaisesRegex(OSError,'disk error'):atomic(self.path,{'new':True})
        self.assertEqual(replace.call_count,1);self.assertEqual(json.loads(self.path.read_text()),{'old':True})

    def test_concurrent_writers_use_distinct_staging_files(self):
        barrier=threading.Barrier(2);names=[];failures=[];original=os.replace
        lock=threading.Lock()
        def replace(src,dest):
            with lock:
                first=src not in names
                names.append(src)
            if first:barrier.wait(timeout=3)
            original(src,dest)
        def write(n):
            try:atomic(self.path,{'writer':n})
            except Exception as e:failures.append(e)
        with patch('ai_queue.os.replace',side_effect=replace):
            threads=[threading.Thread(target=write,args=(n,)) for n in (1,2)]
            for t in threads:t.start()
            for t in threads:t.join()
        self.assertFalse(failures);self.assertEqual(len(set(names)),2)
        self.assertIn(json.loads(self.path.read_text())['writer'],(1,2))


if __name__=='__main__':unittest.main()
