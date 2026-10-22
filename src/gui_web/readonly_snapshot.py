"""VIC-28 read-only presentation boundary over the existing catalog. No pipeline commands."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time

sys.dont_write_bytecode = True
CODE_PARENT = Path(__file__).resolve().parents[1]
APP_ROOT = CODE_PARENT / 'app' if (CODE_PARENT / 'app' / 'pipeline_config.py').is_file() else CODE_PARENT
if not (APP_ROOT / 'pipeline_config.py').is_file():
    raise ImportError('Lecture Pipeline backend is missing beside the dashboard')
sys.path.insert(0, str(APP_ROOT))
import pipeline_config
import asr_device  # Preload without probing devices or loading ASR.
import lecture_catalog
import lecture_progress

CONTRACT = 'vic28.dashboard/1'
_context = threading.local()
_backend_read = pipeline_config.read
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_MUTATIONS = {'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown',
              'os.link', 'os.symlink', 'os.utime', 'os.truncate', 'subprocess.Popen', 'os.system'}
_MEDIA = {'.wav', '.mp3', '.m4a', '.mp4', '.aac', '.flac', '.ogg', '.opus', '.docx', '.xlsx'}


def contained(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


class ReadFence:
    """Thread-scoped I/O audit: deny writes/processes and reads outside configured roots."""
    def __init__(self, root, extra_roots=()):
        self.root = Path(root).resolve(strict=True)
        self.roots = (self.root, *(Path(path).resolve() for path in extra_roots))
        self.reads = set()

    def require_dev(self, path):
        path = Path(path).resolve()
        if not any(contained(path, root) for root in self.roots):
            raise PermissionError('Источник вне разрешённых папок; чтение отклонено')
        return path

    def audit_name(self, path):
        for index, root in enumerate(self.roots):
            if contained(path, root):
                relative = path.relative_to(root).as_posix()
                return relative if index == 0 else f'allowed{index}/{relative}'
        raise PermissionError('Источник вне разрешённых папок; чтение отклонено')

    def validate_paths(self, value):
        if isinstance(value, dict):
            for child in value.values():
                self.validate_paths(child)
        elif isinstance(value, list):
            for child in value:
                self.validate_paths(child)
        elif isinstance(value, str) and (re.match(r'^[A-Za-z]:[\\/]', value) or value.startswith('\\\\')):
            self.require_dev(value)

    @contextlib.contextmanager
    def active(self):
        previous = getattr(_context, 'fence', None)
        _context.fence = self
        try:
            yield self
        finally:
            _context.fence = previous


def _audit(event, args):
    fence = getattr(_context, 'fence', None)
    if fence is None:
        return
    if event in _MUTATIONS or event.startswith(('winreg.Set', 'winreg.Delete', 'winreg.Create')):
        raise PermissionError('VIC-28 snapshot запрещает запись и запуск процессов')
    if event == 'open':
        filename, mode, flags = args
        if flags & _WRITE_FLAGS or mode and any(char in mode for char in 'wax+'):
            raise PermissionError('VIC-28 snapshot запрещает запись файлов')
        if isinstance(filename, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(filename)).resolve()
            # Trusted Python module loads are not user data. Backend imports are preloaded.
            code = path.suffix in {'.py', '.pyc', '.pyd'} and any(
                contained(path, root) for root in (APP_ROOT.resolve(), Path(sys.base_prefix).resolve()))
            if not code:
                fence.require_dev(path)
                if path.suffix.lower() in _MEDIA:
                    raise PermissionError('VIC-28 не читает содержимое аудио, Word или словаря')
                fence.reads.add(fence.audit_name(path))
    elif event in {'os.scandir', 'pathlib.Path.glob', 'pathlib.Path.rglob'}:
        if args and isinstance(args[0], (str, bytes, os.PathLike)):
            fence.require_dev(os.fsdecode(args[0]))


sys.addaudithook(_audit)


def _guarded_read(path):
    fence = getattr(_context, 'fence', None)
    if fence:
        path = fence.require_dev(path)
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('JSON превышает лимит чтения UI (16 MiB)')
    value = _backend_read(path)
    if fence:
        fence.validate_paths(value)
    return value


# Process-local wrappers only; existing backend files and state resolver stay unchanged.
pipeline_config.read = _guarded_read
lecture_catalog.read = _guarded_read


def _utc():
    return datetime.now(timezone.utc).isoformat()


def worker_observation(name, path, fence, now):
    result = dict(id=name, label='Lecture worker' if name == 'lecture' else 'Dialogue worker',
                  reported_state=None, heartbeat_at=None, heartbeat_age_seconds=None,
                  health='missing', message='Heartbeat отсутствует. Состояние worker неизвестно.',
                  scheduler_state=None, observed_backend=None)
    path = fence.require_dev(path)
    if not path.exists():
        return result
    try:
        data = _guarded_read(path)
        if not isinstance(data, dict):
            raise ValueError('Heartbeat должен быть JSON-объектом')
        result['reported_state'] = data.get('worker')
        stamp = data.get('heartbeat')
        parsed = datetime.fromisoformat(stamp)
        if parsed.tzinfo is None:
            raise ValueError('Heartbeat без часового пояса')
        age = now - parsed.timestamp()
        if not math.isfinite(age) or age < 0:
            raise ValueError('Время heartbeat некорректно или находится в будущем')
        result.update(heartbeat_at=stamp, heartbeat_age_seconds=round(age, 1),
                      health='fresh' if age <= 90 else 'stale')
        result['message'] = ('Свежий heartbeat · ' + str(data.get('worker', 'состояние неизвестно'))
                             if age <= 90 else 'Heartbeat устарел. Текущий запуск не подтверждён.')
    except (OSError, ValueError, TypeError) as exc:
        result.update(health='invalid', message='Heartbeat не читается: ' + str(exc))
    return result


class SnapshotProvider:
    def __init__(self, dev_root, config_path, *, fixture=False, allowed_roots=(), source_kind='dev'):
        if source_kind not in ('dev', 'product'):
            raise ValueError('Unsupported dashboard source kind')
        self.root = Path(dev_root).resolve(strict=True)
        self.config_path = Path(config_path).resolve()
        self.fixture = fixture
        self.source_kind = source_kind
        self.allowed_roots = tuple(Path(path).resolve() for path in allowed_roots)
        self.lock = threading.Lock()
        self.frozen = None
        ReadFence(self.root).require_dev(self.config_path)

    def snapshot(self):
        with self.lock:
            if self.fixture and self.frozen is not None:
                return self.frozen
            data = self._read()
            if self.fixture:
                self.frozen = data
            return data

    def _read(self):
        started = time.monotonic()
        fence = ReadFence(self.root, self.allowed_roots)
        result = dict(contract=CONTRACT, available=False, captured_at=_utc(), revision=None,
                      source=dict(kind='fixture' if self.fixture else self.source_kind, frozen=self.fixture,
                                  config=str(self.config_path), dev_root=str(self.root)),
                      workspace=None, version=None, workers=[], courses=[], catalog=[], pending=[],
                      counts=None, errors=[], device=dict(configured=None, observed=None),
                      preflight=dict(status='not_run', message='Этот UI не запускает preflight или GPU probe.'),
                      capabilities=dict(read_only=True, commands=False, safe_open=False, tk_fallback=True))
        try:
            with fence.active():
                raw = _guarded_read(self.config_path)
                if not isinstance(raw, dict):
                    raise ValueError('Config должен быть объектом')
                # Check roots before constructing Config, which follows current.json.
                base = self.config_path.parent
                for name in ('application_home', 'install_root'):
                    fence.require_dev(base / raw.get(name, '.'))
                fence.require_dev(raw['data_root'])
                c = pipeline_config.Config(self.config_path)
                for path in (c.home, c.install, c.data_root, c.worker_home, c.dialogue_home,
                             c.queue_home, c.state, c.ai_state):
                    fence.require_dev(path)
                for subject in c.subjects(include_disabled=True).values():
                    for key in ('subject_dir', 'audio_dir', 'raw_dir', 'ready_dir', 'notes_dir'):
                        fence.require_dev(subject[key])
                for binding in c.courses().values():
                    for key in ('source_audio_folder', 'archive_audio_folder', 'raw_output_folder', 'final_output_folder'):
                        if binding.get(key):
                            fence.require_dev(binding[key])
                view = lecture_catalog.build(c)
                now = time.time()
                workers = [worker_observation('lecture', c.worker_home / 'worker_status.json', fence, now),
                           worker_observation('dialogue', c.dialogue_home / 'status.json', fence, now)]
                if workers[0]['health'] != 'fresh' or workers[0]['reported_state'] != 'RUNNING':
                    for row in view['items']:
                        row['progress'] = None
                        row['progress_view'] = lecture_progress.presentation(None)
                result.update(available=True, workspace=dict(id=c.active, name=c.workspace.get('name', c.active)),
                              workers=workers, catalog=view['items'], pending=view['pending'], errors=view['errors'],
                              version=c.install.name,
                              device=dict(configured=c.device_mode, observed=None))
                bindings = c.courses()
                result['courses'] = [dict(id=s['subject_code'], name=s['subject_name'], enabled=s['enabled'],
                                          language=s.get('default_language', c.data['languages']['lecture']),
                                          inbox_enabled=bindings.get(s['subject_code'], {}).get('enabled', False))
                                     for s in c.workspace['subjects']]
                observations = [row['progress'].get('backend') for row in view['items'] if row.get('progress')]
                result['device']['observed'] = observations[0] if len(observations) == 1 else None
                result['tk_fallback_entry'] = str(c.install / 'gui_v1.8' / 'app.py')
                if not view['errors']:
                    rows = view['items']
                    result['counts'] = dict(total=len(rows), ready=sum(r['status'] == 'ready' for r in rows),
                                            asr=sum(r['status'] in ('asr', 'publishing') for r in rows),
                                            raw=sum(r['stages'].get('raw') == 'available' for r in rows),
                                            waiting_ai=sum(r['status'] == 'waiting_ai' for r in rows),
                                            done=sum(r['status'] == 'done' for r in rows),
                                            problems=sum(r['status'] in ('problem', 'review', 'error') for r in rows),
                                            pending=len(view['pending']))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            result['errors'].append('Источник недоступен: ' + str(exc))
        result['read_audit'] = dict(files=sorted(fence.reads), file_count=len(fence.reads),
                                    content_excluded=['audio', 'Word', 'vocabulary'], mutations_allowed=False)
        result['read_duration_ms'] = round((time.monotonic() - started) * 1000, 1)
        # Revision identifies content, not time spent reading or capture time.
        stable = {key: value for key, value in result.items() if key not in ('captured_at', 'read_duration_ms', 'revision')}
        result['revision'] = hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
        return result
