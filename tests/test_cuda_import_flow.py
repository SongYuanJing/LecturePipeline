"""Real disposable files through validation, staging, copy/hash and publish."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
import import_cuda

class CudaImportFlowTests(unittest.TestCase):
 def test_complete_import_preserves_source_and_is_idempotent(self):
  with tempfile.TemporaryDirectory() as temporary:
   base=Path(temporary);source=base/'WhisperLocal/cuda_runtime/v1.3';source.mkdir(parents=True)
   root=base/'Transcript Cn Ru UX';(root/'launcher').mkdir(parents=True)
   originals={'cublas64_12.dll':b'disposable cublas fixture','cudnn64_9.dll':b'disposable cudnn fixture'}
   for name,data in originals.items():(source/name).write_bytes(data)
   manifest=root/'launcher/cuda-manifest.json'
   manifest.write_text(json.dumps({'files':{name:hashlib.sha256(data).hexdigest() for name,data in originals.items()}}),encoding='utf8')
   self.assertEqual(import_cuda.install(source,root),'Imported private CUDA; driver unchanged')
   dest=root/'runtime/cuda/v1.3'
   self.assertFalse(dest.with_name('v1.3.pending').exists())
   for name,data in originals.items():
    self.assertEqual((source/name).read_bytes(),data)
    self.assertEqual((dest/name).read_bytes(),data)
   self.assertEqual((dest/'component.json').read_bytes(),manifest.read_bytes())
   before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in dest.iterdir()}
   self.assertEqual(import_cuda.install(source,root),'Existing CUDA component verified')
   self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in dest.iterdir()})

 def test_misspelled_source_fails_before_staging(self):
  with tempfile.TemporaryDirectory() as temporary:
   base=Path(temporary);source=base/'WhisperLocal/cuda_runtime/v1.3';source.mkdir(parents=True)
   (source/'cublas64_12.dll').write_bytes(b'existing file')
   root=base/'app';(root/'launcher').mkdir(parents=True)
   (root/'launcher/cuda-manifest.json').write_text(json.dumps({'files':{'cublas64_12.dll':hashlib.sha256(b'existing file').hexdigest()}}),encoding='utf8')
   with self.assertRaises(FileNotFoundError) as error:import_cuda.install(base/'WisperLocal/cuda_runtime/v1.3',root)
   self.assertIn('WisperLocal',str(error.exception))
   self.assertFalse((root/'runtime').exists())
   self.assertEqual((source/'cublas64_12.dll').read_bytes(),b'existing file')

if __name__=='__main__':unittest.main()
