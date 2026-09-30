"""Windows/Drive polling worker. The v1.1 pipeline remains the transcription engine."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time
import uuid
from contextlib import contextmanager

import lecture_pipeline as p

BASE = p.CONFIG.worker_home
SIGNAL = re.compile(r'^READY\s+(\d{1,3}_\d{4}-\d{2}-\d{2})\s+([1-9]\d{0,2})(?:\s*\(\d+\))?$', re.I)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def remote_signals(audio_dir):
    found, invalid = {}, []
    for path in audio_dir.iterdir():
        if not path.is_dir() or not path.name.upper().startswith('READY'):
            continue
        m = SIGNAL.fullmatch(path.name)
        if not m:
            invalid.append(path.name)
            continue
        key, part = p.lecture_key_from_stem(m[1])
        if key != m[1] or part != 0:
            invalid.append(path.name)
            continue
        found.setdefault(key, set()).add(int(m[2]))
    return found, invalid


@contextmanager
def closed_writer_read(path):
    """On Windows refuse files that a writer still has open, even if size is paused."""
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(path), 0x80000000, 1, None, 3, 0x08000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except Exception:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, 'rb') as stream:
        yield stream


def fingerprint(parts):
    before = [p.source_signature(f) for f in parts]
    entries = []
    for path in parts:
        h = hashlib.sha256()
        with closed_writer_read(path) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
        entries.append({'name': path.name, 'size': path.stat().st_size, 'sha256': h.hexdigest()})
    if any(f['size'] <= 0 for f in entries) or before != [p.source_signature(f) for f in parts]:
        raise ValueError('файл пуст или изменяется во время чтения')
    return entries, before


class Worker:
    def __init__(self, home=BASE, stable_seconds=120, clock=time.time, monotonic=time.monotonic):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.home / 'worker_jobs.json'
        if self.journal_path.exists():
            self.journal = json.loads(self.journal_path.read_text(encoding='utf-8'))
            if (self.journal.get('version') != 1 or not isinstance(self.journal.get('jobs'), dict)
                    or any(not isinstance(j, dict) or j.get('phase') not in
                           {'transcribing', 'publishing', 'error', 'done'}
                           or not re.fullmatch('[0-9a-f]{32}', str(j.get('token', '')))
                           for j in self.journal['jobs'].values())):
                raise ValueError('повреждён worker_jobs.json; автоматический сброс запрещён')
        else:
            # An existing spool without its journal cannot be safely inferred.
            spool = self.home / 'worker_spool'
            if spool.exists() and any(spool.iterdir()):
                raise ValueError('worker_jobs.json отсутствует при наличии worker_spool')
            self.journal = {'version': 1, 'jobs': {}}
        self.stable_seconds = stable_seconds
        self.clock, self.monotonic = clock, monotonic
        self.observed = {}  # Restart deliberately requires a fresh full stability interval.
        self.rows = {}
        self.status_path = None
        self.model = None
        self.status_lock = threading.RLock()
        self.started = p.now_iso()
        self.worker_state = 'RUNNING'
        self.worker_message = 'Проверяю Google Drive'
        if not isinstance(self.journal.get('generated_ready', {}), dict):
            raise ValueError('повреждён generated_ready в worker_jobs.json')

    def save(self):
        atomic_json(self.journal_path, self.journal)

    def report(self, key, status, detail):
        with self.status_lock:
            previous = self.rows.get(key, {})
            changed = previous.get('status') != status or previous.get('detail') != detail
            self.rows[key] = {'status': status, 'detail': detail,
                              'updated_at': p.now_iso() if changed else previous['updated_at']}
            self.publish_status()

    def publish_status(self):
        with self.status_lock:
            data = {'version': 1, 'worker': self.worker_state, 'message': self.worker_message,
                    'started_at': self.started, 'heartbeat': p.now_iso(), 'lectures': copy.deepcopy(self.rows)}
            atomic_json(self.home / 'worker_status.json', data)
            if self.status_path:
                atomic_json(self.status_path.with_suffix('.json'), data)
                text = [f'Lecture worker: {data["worker"]}', f'Последняя связь: {data["heartbeat"]}',
                        data['message'], '', 'Если время не обновляется более 3 минут, worker/Drive недоступен.', '']
                text += [f'{key}: {row["status"]} — {row["detail"]}' for key, row in sorted(data['lectures'].items())]
                tmp = self.status_path.with_suffix('.pending')
                tmp.write_text('\n'.join(text) + '\n', encoding='utf-8-sig')
                tmp.replace(self.status_path)

    def stable_ready(self, cfg, key, parts, counts):
        identity = str(cfg['audio_dir']) + '/' + key
        try:
            if len(counts) > 1:
                raise ValueError('конфликт READY: указаны разные количества частей')
            ready_file = p.ready_path(cfg, key)
            data = json.loads(ready_file.read_text(encoding='utf-8-sig')) if ready_file.exists() else None
            owned = (data is not None and counts and
                     self.journal.get('generated_ready', {}).get(identity) == data)
            if data is not None and not owned:
                data = p.read_ready(cfg, key, parts)
            if not counts and data is None:
                self.observed.pop(identity, None)
                return None, 'COLLECTING', 'Создайте папку READY <ключ лекции> <число частей>'
            count = next(iter(counts)) if counts else data['expected_parts']
            p.check_numbers(parts, count)
            if data and data['expected_parts'] != count and not owned:
                raise ValueError('число частей в сигнале не совпадает с READY.json')
            entries, signatures = fingerprint(parts)
            if data and entries != data['files'] and not owned:
                raise ValueError('SHA-256 не совпадает с READY.json; нужна проверка исходного комплекта')
            if owned and (entries != data['files'] or data['expected_parts'] != count):
                data = None  # Re-seal only our own manifest after a new full stability interval.
            stamp = {'entries': entries, 'signatures': signatures, 'count': count,
                     'remote': bool(counts), 'ready': data}
            old = self.observed.get(identity)
            if old is None or old[0] != stamp:
                self.observed[identity] = (stamp, self.monotonic())
                return None, 'WAITING', f'Полный комплект найден; проверяю стабильность {self.stable_seconds} с'
            if self.monotonic() - old[1] < self.stable_seconds:
                return None, 'WAITING', f'Ожидаю неизменности всех файлов не менее {self.stable_seconds} с'
            # A supplied v1.1 READY is immutable. Only absent manifests are created.
            if data is None:
                data = {'version': 1, 'lecture': key, 'expected_parts': count, 'files': entries}
                self.journal.setdefault('generated_ready', {})[identity] = data
                self.save()
                atomic_json(ready_file, data)
            return data, 'READY', 'Части 1…N и повторные SHA-256 совпали'
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
            self.observed.pop(identity, None)
            return None, 'WAITING', str(exc)

    def fail_job(self, identity, job, exc):
        failures = job.get('failures', 0) + 1
        job.update(failures=failures, error=str(exc), retry_at=self.clock() + min(3600, 300 * 2 ** min(failures - 1, 4)))
        if job['phase'] != 'publishing':
            job['phase'] = 'error'
        self.save()
        self.report(identity, 'ERROR', f'{exc}; автоматическая повторная попытка после {time.ctime(job["retry_at"])}')
        logging.exception('Job failed: %s', identity)

    def spool(self, job):
        return self.home / 'worker_spool' / job['token']

    def publish_job(self, identity, job, cfg, key, state_file, state):
        """Replay a durable result bundle after an interrupted Drive write, without Whisper."""
        spool = self.spool(job)
        bundle = spool / 'raw' / key
        plan = json.loads((spool / 'publish.json').read_text(encoding='utf-8'))
        for entry in plan['files']:
            source = bundle / entry['name']
            if source.name != entry['name'] or source.stat().st_size != entry['size'] or p.digest(source) != entry['sha256']:
                raise ValueError('повреждён локальный комплект результатов; публикация остановлена')
        destination = cfg['raw_dir'] / key
        if not job.get('archive_checked'):
            if destination.exists():
                archive = cfg['raw_dir'] / '.history' / (key + '-worker-' + job['token'])
                # Do not overwrite an earlier successful archive on replay.
                if not archive.exists():
                    pending_archive = archive.with_name(archive.name + '.pending')
                    shutil.copytree(destination, pending_archive, dirs_exist_ok=True)
                    pending_archive.replace(archive)
            job['archive_checked'] = True
            self.save()
        destination.mkdir(parents=True, exist_ok=True)
        for entry in plan['files']:
            target = destination / entry['name']
            if target.exists() and target.stat().st_size == entry['size'] and p.digest(target) == entry['sha256']:
                continue
            tmp = target.with_name(target.name + '.pending')
            shutil.copyfile(bundle / entry['name'], tmp)
            if p.digest(tmp) != entry['sha256']:
                raise OSError('не совпала подпись скопированного результата')
            tmp.replace(target)
        record = plan['record']
        record['output_dir'] = str(destination)
        record['combined_txt'] = str(destination / f'{key}_raw.txt')
        state['lectures'][identity] = record
        state['model'], state['updated_at'] = p.MODEL_NAME, p.now_iso()
        p.save_state(state_file, state)
        job['phase'] = 'done'
        job.pop('error', None)
        self.save()
        self.report(identity, 'DONE', 'Результаты опубликованы в папке черновых расшифровок')

    def transcribe(self, identity, cfg, key, parts, state_file, state):
        job = self.journal['jobs'].get(identity)
        if job is None:
            job = {'token': uuid.uuid4().hex, 'phase': 'transcribing', 'failures': 0}
            self.journal['jobs'][identity] = job
        else:
            job['phase'] = 'transcribing'
        self.save()
        try:
            self.report(identity, 'VERIFYING', 'Проверка файлов и подготовка локальной копии')
            with p.verified_inputs(cfg, key, parts) as copies:
                # Recheck the authoritative DONE ledger before expensive work.
                current = p.load_state(state_file)
                if not p.needs_processing(current, identity.split('/')[0], key, parts, cfg['raw_dir']):
                    self.report(identity, 'DONE', 'Защищено существующим state/результатом')
                    return
                self.report(identity, 'TRANSCRIBING', 'Whisper обрабатывает проверенные локальные копии')
                if self.model is None:
                    self.model = p.WhisperModel(p.MODEL_NAME, device=p.DEVICE,
                                               compute_type=p.COMPUTE_TYPE, local_files_only=True)
                if hasattr(self.model,'progress_callback'):
                    self.model.progress_callback=lambda value:atomic_json(self.home/'asr_progress.json',dict(value,identity=identity))
                spool = self.spool(job)
                spool.mkdir(parents=True, exist_ok=True)
                local_state = {'version': 1, 'lectures': {}}
                local_cfg = dict(cfg, raw_dir=spool / 'raw')
                p.process_lecture(self.model, identity.split('/')[0], local_cfg, key, copies,
                                  local_state, spool / 'state.json', spool / 'pipeline.log')
                bundle = spool / 'raw' / key
                outputs = sorted(bundle.iterdir(), key=lambda f: (f.name.endswith('_manifest.json'), f.name))
                plan = {'files': [{'name': f.name, 'size': f.stat().st_size, 'sha256': p.digest(f)} for f in outputs],
                        'record': local_state['lectures'][identity]}
                atomic_json(spool / 'publish.json', plan)
                self.report(identity, 'PUBLISHING', 'Публикация TXT/SRT')
                job['phase'] = 'publishing'
                self.save()
                self.publish_job(identity, job, cfg, key, state_file, current)
        except Exception as exc:
            if job['phase'] != 'publishing':
                self.model = None
            self.fail_job(identity, job, exc)

    def cycle(self):
        state_file, log_file, subjects = p.discover_layout()
        self.status_path = state_file.parent / 'WORKER_STATUS.txt'
        state = p.load_state(state_file)
        self.worker_state, self.worker_message = 'RUNNING', 'Проверка каждые 30 с; незавершённые комплекты ожидают'
        for code, cfg in subjects.items():
            groups = p.collect_lectures(cfg['audio_dir'])
            signals, invalid = remote_signals(cfg['audio_dir'])
            for name in invalid:
                self.report(code + '/signal:' + name, 'ERROR', 'Неверное имя: пример READY 05_2026-09-25 5')
            legacy_ready = {f.name[:-11] for f in cfg['audio_dir'].glob('*.READY.json')}
            recorded = {k.split('/', 1)[1] for k in state['lectures'] if k.startswith(code + '/')}
            jobs = {k.split('/', 1)[1] for k in self.journal['jobs'] if k.startswith(code + '/')}
            for key in sorted(set(groups) | set(signals) | legacy_ready | recorded | jobs):
                identity = code + '/' + key
                parts = groups.get(key, [])
                record = state['lectures'].get(identity, {})
                if record.get('status', '').lower() in {'completed', 'done'}:
                    self.report(identity, 'DONE', 'Завершённая лекция защищена; повторный READY игнорируется')
                    continue
                job = self.journal['jobs'].get(identity)
                if job and job.get('retry_at', 0) > self.clock():
                    self.report(identity, 'ERROR', f'{job.get("error", "сбой")}; ожидаю повторной попытки')
                    continue
                if job and job['phase'] == 'publishing':
                    try:
                        self.report(identity, 'READY', 'Восстанавливаю публикацию готовых результатов без Whisper')
                        self.publish_job(identity, job, cfg, key, state_file, state)
                    except Exception as exc:
                        self.fail_job(identity, job, exc)
                    continue
                if not p.needs_processing(state, code, key, parts, cfg['raw_dir']):
                    self.report(identity, 'ERROR', 'Есть прежние результаты без completed; автоматическая перезапись запрещена')
                    continue
                ready, status, detail = self.stable_ready(cfg, key, parts, signals.get(key, set()))
                self.report(identity, status, detail)
                if ready:
                    self.transcribe(identity, cfg, key, parts, state_file, state)
                    state = p.load_state(state_file)
        self.publish_status()
        # AI indexing is a separate, idempotent projection; ASR/DONE are unchanged.
        if self.home.resolve() == p.CONFIG.worker_home.resolve():
            try:
                from ai_queue import refresh
                refresh(p.CONFIG)
            except Exception:
                logging.exception('AI queue update failed; lecture completion is retained')

    def safe_cycle(self):
        try:
            self.cycle()
        except Exception as exc:
            self.worker_state, self.worker_message = 'ERROR', str(exc)
            logging.exception('Worker cycle failed; retrying without resetting state')
            try:
                self.publish_status()
            except Exception:
                logging.exception('Drive status unavailable; consult local worker_status.json')


class LogStream:
    def write(self, text):
        if text.strip():
            logging.info(text.rstrip())
    def flush(self):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--poll-seconds', type=int, default=30)
    parser.add_argument('--stable-seconds', type=int, default=120)
    args = parser.parse_args(argv)
    if args.poll_seconds < 5 or args.stable_seconds < 120:
        parser.error('poll >= 5; stable >= 120')
    from pipeline_config import require_preflight
    require_preflight(p.CONFIG)
    BASE.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(BASE / 'worker.log', maxBytes=5_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    sys.stdout = sys.stderr = LogStream()
    try:
        with p.pipeline_lock(BASE / 'lecture_pipeline.lock'):
            worker = Worker(stable_seconds=args.stable_seconds)
            stop = threading.Event()
            def heartbeat():
                while not stop.wait(60):
                    try:
                        worker.publish_status()
                    except Exception:
                        logging.exception('Heartbeat publication failed')
            hb = threading.Thread(target=heartbeat, daemon=True)
            hb.start()
            try:
                while not (BASE / 'worker.stop').exists():
                    worker.safe_cycle()
                    if args.once:
                        break
                    # Short waits make administrative graceful stop responsive.
                    for _ in range(args.poll_seconds):
                        if (BASE / 'worker.stop').exists():
                            break
                        stop.wait(1)
            finally:
                stop.set()
                hb.join(timeout=2)
                worker.worker_state, worker.worker_message = 'STOPPED', 'Worker остановлен'
                worker.publish_status()
        return 0
    except Exception:
        logging.exception('Worker stopped; scheduler may restart it')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
