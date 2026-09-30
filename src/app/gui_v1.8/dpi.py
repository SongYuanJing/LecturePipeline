"""Windows system-DPI sizing for the Tk control panel; no pipeline imports."""
import sys
from tkinter import font

def enable_system_dpi():
 if sys.platform!='win32':return
 import ctypes
 try:
  # A first-run Tk window may already have existed in this process. Set the
  # GUI thread's awareness before creating the main root, not after HWND creation.
  fn=ctypes.windll.user32.SetThreadDpiAwarenessContext
  fn.argtypes=[ctypes.c_void_p];fn.restype=ctypes.c_void_p
  if fn(ctypes.c_void_p(-2)):return # SYSTEM_AWARE, compatible with Tk 8.6
 except (AttributeError,OSError):pass
 try:ctypes.windll.shcore.SetProcessDpiAwareness(1)
 except (AttributeError,OSError):pass

def dimensions(dpi,work_width,work_height):
 scale=max(1.0,float(dpi)/96)
 px=lambda n:max(1,round(n*scale))
 width=min(px(1180),max(320,work_width-px(48)))
 height=min(px(800),max(240,work_height-px(64)))
 return scale,(width,height),(min(px(940),width),min(px(620),height))

def configure_root(root):
 dpi=root.winfo_fpixels('1i');work_width=root.winfo_screenwidth();work_height=root.winfo_screenheight()
 if sys.platform=='win32':
  import ctypes
  from ctypes import wintypes
  try:
   dpi=ctypes.windll.user32.GetDpiForSystem()
   rect=wintypes.RECT()
   if ctypes.windll.user32.SystemParametersInfoW(48,0,ctypes.byref(rect),0):
    work_width=rect.right-rect.left;work_height=rect.bottom-rect.top
  except (AttributeError,OSError):pass
 root.tk.call('tk','scaling',dpi/72.0)
 for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkCaptionFont','TkSmallCaptionFont','TkIconFont','TkTooltipFont'):
  font.nametofont(name,root=root).configure(family='Segoe UI',size=11)
 scale,size,minimum=dimensions(dpi,work_width,work_height)
 root.geometry(f'{size[0]}x{size[1]}');root.minsize(*minimum)
 return lambda n:max(1,round(n*scale))
