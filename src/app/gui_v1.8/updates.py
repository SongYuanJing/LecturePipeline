"""Manual UI only. The installed stable updater owns all update decisions."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import tkinter as tk
from tkinter import ttk


class UpdateControls:
    def __init__(self, app, parent):
        self.app = app
        self.tag = None
        self.pending = False
        bar = ttk.Frame(parent)
        bar.pack(fill='x', padx=22, pady=8)
        self.check_button = ttk.Button(bar, text='Проверить обновления', command=self.check)
        self.check_button.pack(side='left')
        self.apply_button = ttk.Button(bar, text='Обновить', command=self.apply, state='disabled')
        self.apply_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='')
        ttk.Label(bar, textvariable=self.status, wraplength=680).pack(side='left', padx=8)

    def home(self):
        from pipeline_config import Config
        home = Config(self.app.path).home
        if not (home/'launcher/update_gui.py').is_file():
            raise RuntimeError('Для обновлений требуется новая установка через Setup.')
        return home

    def check(self):
        if self.pending or self.app.controls_busy:
            return
        self.pending = True
        self.tag = None
        self.check_button.configure(state='disabled')
        self.apply_button.configure(state='disabled')
        self.status.set('Проверка...')
        def work():
            home = self.home()
            result = subprocess.run([str(home/'runtime/asr/python.exe'), '-B', '-X', 'utf8',
                str(home/'launcher/updater.py'), 'check'], capture_output=True, encoding='utf8',
                timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or 'Проверка не завершена')
            return json.loads(result.stdout)
        self.app.submit(work, self.checked)

    def checked(self, result, error):
        self.pending = False
        self.check_button.configure(state='normal')
        if error:
            self.status.set('Не удалось проверить обновления. Повторите проверку. '+error)
        elif result['status'] == 'no-update':
            self.status.set('Установлена последняя версия')
        else:
            self.tag = result['tag']
            self.status.set('Текущая: '+result['current']+' → новая: '+self.tag.lstrip('v'))
            self.apply_button.configure(state='normal')

    def apply(self):
        if not self.tag or self.pending or self.app.controls_busy:
            return
        self.pending = True
        self.app.controls_busy = True
        self.check_button.configure(state='disabled')
        self.apply_button.configure(state='disabled')
        self.status.set('Открытие окна обновления. Приложение будет перезапущено…')
        def work():
            home = self.home()
            token = uuid.uuid4().hex
            ready = home/'run'/('update-ui-'+token+'.json')
            process = subprocess.Popen([str(home/'runtime/asr/pythonw.exe'), '-B', '-X', 'utf8',
                str(home/'launcher/update_gui.py'), '--tag', self.tag, '--parent', str(os.getpid()),
                '--ready', token], cwd=home)
            try:
                deadline = time.monotonic()+30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Окно обновления не запустилось. Текущая версия сохранена.')
                    if ready.exists():
                        if json.loads(ready.read_text()) != {'pid': process.pid}:
                            raise RuntimeError('Некорректное подтверждение окна обновления')
                        return True
                    time.sleep(.1)
                raise RuntimeError('Окно обновления не ответило. Повторите попытку.')
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                raise
            finally:
                ready.unlink(missing_ok=True)
        self.app.submit(work, self.handed_off)

    def handed_off(self, result, error):
        self.app.controls_busy = False
        self.pending = False
        if error:
            self.status.set(str(error))
            self.check_button.configure(state='normal')
            self.apply_button.configure(state='normal')
        else:
            self.app.close()
