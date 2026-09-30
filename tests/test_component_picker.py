"""GPU source selection through the real command adapter; no GUI or imports run."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
import setup_gui as gui

class ComponentPickerTests(unittest.TestCase):
 def test_model_then_gpu_exact_source_reaches_cuda_process(self):
  home=Path(r'C:\Test World\Transcript Cn Ru UX')
  model=r'C:\different-model\snapshot'
  cuda=r'C:\WhisperLocal\cuda_runtime\v1.3'
  jobs=[]
  panel=SimpleNamespace(home=home,status=Mock(),refresh=Mock(),async_=SimpleNamespace(busy=False,run=lambda fn,done:jobs.append(fn)))
  dialog=Mock();dialog.show.return_value=model
  with patch.object(gui.filedialog,'Directory',return_value=dialog) as model_picker,patch.object(gui.simpledialog,'askstring',return_value=cuda) as gpu_picker,patch.object(gui.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='OK')) as process:
   gui.Components.choose(panel,'import_model.py',True)
   gui.Components.choose(panel,'import_cuda.py',True)
   jobs[1]();jobs[0]()
   args=process.call_args_list[0].args[0]
   self.assertEqual(args[-2],str(home/'launcher/import_cuda.py'))
   self.assertEqual(args[-1],cuda)
   self.assertNotEqual(args[-1],str(home));self.assertNotEqual(args[-1],model)
   self.assertEqual(process.call_args_list[1].args[0][-1],model)
   model_picker.assert_called_once();gpu_picker.assert_called_once()
   self.assertNotIn('initialvalue',gpu_picker.call_args.kwargs)

if __name__=='__main__':unittest.main()
