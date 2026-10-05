"""Progress window for the existing engine; no session lock, downloader or resolver."""
import argparse
import ctypes
from ctypes import wintypes
import os
import queue
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

import updater
from update_state import atomic


def parent_handle(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel, handle


def progress_text(text):
    for prefix, label in [('Downloading: ', 'Загрузка: '), ('Verified download: ', 'Проверено: '),
                          ('Verified cache: ', 'Проверенный кэш: ')]:
        if text.startswith(prefix):
            return label+text[len(prefix):]
    return text


def perform_update(kernel, handle, tag, events):
    try:
        if kernel.WaitForSingleObject(handle, 30000) != 0:
            raise RuntimeError('Приложение не закрылось. Текущая версия сохранена.')
        events.put(('progress', 'Проверка GitHub Release…'))
        result = updater.apply_tag(updater.ROOT, tag, lambda text: events.put(('progress', progress_text(text))))
        events.put(('success', result))
    except Exception as error:
        events.put(('error', str(error)))
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--parent', type=int, required=True)
    parser.add_argument('--ready', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{32}', args.ready):
        raise ValueError('Invalid handoff token')
    kernel, handle = parent_handle(args.parent)  # Capture identity before acknowledging GUI exit.
    root = tk.Tk()
    root.title('Lecture Pipeline — Обновление')
    root.geometry('660x300')
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Обновление до '+args.tag.lstrip('v'), font=('Segoe UI', 16)).pack(anchor='w')
    status = tk.StringVar(value='Ожидание закрытия приложения…')
    ttk.Label(frame, textvariable=status, wraplength=600).pack(fill='x', pady=20)
    bar = ttk.Progressbar(frame, mode='indeterminate')
    bar.pack(fill='x'); bar.start()
    events = queue.Queue()
    running = [True]
    root.protocol('WM_DELETE_WINDOW', lambda: None if running[0] else root.destroy())
    ready = updater.ROOT/'run'/('update-ui-'+args.ready+'.json')
    def reopen():
        subprocess.Popen([str(updater.ROOT/'runtime/asr/pythonw.exe'), '-B', '-X', 'utf8',
            str(updater.ROOT/'launcher/launch.py'), 'gui'], cwd=updater.ROOT)
        root.destroy()
    def pump():
        while not events.empty():
            kind, value = events.get()
            if kind == 'progress':
                status.set(value)
            else:
                running[0] = False; bar.stop()
                atomic(updater.ROOT/'logs/update-ui-result.json', dict(status=kind, result=value))
                if kind == 'success':
                    if value['status'] == 'no-update':
                        reopen()
                    else:
                        root.destroy()
                    return
                status.set('Обновление не завершено. Предыдущая версия сохранена.\n'+value)
                ttk.Button(frame, text='Открыть приложение', command=reopen).pack(pady=10)
                ttk.Button(frame, text='Закрыть', command=root.destroy).pack()
        root.after(100, pump)
    def start():
        atomic(ready, dict(pid=os.getpid()))
        threading.Thread(target=perform_update, args=(kernel,handle,args.tag,events), daemon=True).start()
        pump()
    root.after_idle(start)
    root.mainloop()
    ready.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
