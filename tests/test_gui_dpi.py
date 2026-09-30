import sys,unittest,ast
from pathlib import Path
from unittest.mock import Mock,patch
GUI=Path(__file__).resolve().parents[1]/'src/app/gui_v1.8'
sys.path.insert(0,str(GUI))
import dpi

class GuiDpiTests(unittest.TestCase):
 def test_100_percent_window_fits(self):
  scale,size,minimum=dpi.dimensions(96,1920,1040)
  self.assertEqual((scale,size,minimum),(1.0,(1180,800),(940,620)))
 def test_high_dpi_pixel_dimensions_scale_and_fit(self):
  for value,width,height in [(144,2560,1400),(192,3840,2080),(192,1920,1040)]:
   scale,size,minimum=dpi.dimensions(value,width,height)
   self.assertEqual(scale,value/96)
   self.assertLess(size[0],width);self.assertLess(size[1],height)
   self.assertLessEqual(minimum[0],size[0]);self.assertLessEqual(minimum[1],size[1])
 def test_fonts_and_tk_share_system_scale(self):
  for value in (96,144,192):
   root=Mock();root.winfo_fpixels.return_value=value;root.winfo_screenwidth.return_value=3840;root.winfo_screenheight.return_value=2160
   with patch.object(dpi.sys,'platform','test'),patch.object(dpi.font,'nametofont') as named:
    px=dpi.configure_root(root)
    root.tk.call.assert_called_once_with('tk','scaling',value/72)
    self.assertEqual(px(34),round(34*value/96))
    self.assertEqual(named.call_count,8)
    named.return_value.configure.assert_called_with(family='Segoe UI',size=11)
 def test_main_awareness_precedes_root(self):
  tree=ast.parse((GUI/'app.py').read_text(encoding='utf8'))
  main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
  text=ast.unparse(main)
  self.assertLess(text.index('enable_system_dpi()'),text.index('tk.Tk()'))

if __name__=='__main__':unittest.main()
