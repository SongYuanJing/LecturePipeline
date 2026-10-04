"""JSON-lines bridge for the pre-Python shell. Existing modules own all policies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

from launch import ROOT, app_root
import download_components
import component_status
import setup


class Cancelled(Exception):
    pass


def emit(stage, message, **fields):
    print(json.dumps(dict(stage=stage, message=message, **fields), ensure_ascii=False), flush=True)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    temporary.replace(path)


def configure_resumable(root, data, mode):
    """Initialize only a new data root; preserve a completed config on retry.

    Data is built in an owned sibling then published. The journal lets a retry
    finish a crash between data publication and configuration publication.
    """
    cfg = root / 'config/config.json'
    journal = root / 'bootstrap-data.json'
    stage = data.parent / ('.lp-data-' + hashlib.sha256(str(root).encode()).hexdigest()[:12])
    if cfg.exists() and not journal.exists():
        value = json.loads(cfg.read_text(encoding='utf8'))
        if Path(value['data_root']).resolve() != data:
            raise ValueError('Эта установка использует другую папку данных; она не изменена.')
        return cfg
    if journal.exists():
        expected = dict(data=str(data), stage=str(stage))
        if json.loads(journal.read_text(encoding='utf8')) != expected:
            raise ValueError('Пути не совпадают с незавершённой установкой.')
        if not cfg.exists() and stage.exists():
            # Only our journal-owned, unpublished, freshly created directory.
            if stage.is_symlink() or stage.resolve() != stage:
                raise ValueError('Небезопасный временный каталог данных')
            shutil.rmtree(stage)
        if not cfg.exists():
            initial_state = root / 'run/dialogue/dialogue_state.json'
            if initial_state.exists():
                if json.loads(initial_state.read_text(encoding='utf8')) != dict(schema_version=1, mode='dialogue', jobs={}):
                    raise ValueError('Непустое состояние сохранено; автоматический сброс запрещён.')
                initial_state.unlink()
    else:
        if stage.exists() or (data.exists() and any(data.iterdir())):
            raise ValueError('Выберите новую пустую папку данных. Существующие данные сохранены.')
        write(journal, dict(data=str(data), stage=str(stage)))
    if not cfg.exists():
        setup.configure(root, stage, 'semester-1', 'SUBJECT', device_mode=mode)
    value = json.loads(cfg.read_text(encoding='utf8'))
    if Path(value['data_root']).resolve() not in (stage, data):
        raise ValueError('Конфигурация не принадлежит текущей операции установки.')
    if stage.exists():
        if data.exists():
            data.rmdir()  # Only an empty destination; never replace user files.
        stage.rename(data)
    if not data.is_dir():
        raise ValueError('Не найдены подготовленные данные; установка не завершена.')
    value['data_root'] = str(data)
    write(cfg, value)
    journal.unlink()
    return cfg


def run(root, data, mode, cancel, smoke_audio=None):
    root, data = root.resolve(), data.resolve()
    if root == data or root in data.parents or data in root.parents:
        raise ValueError('Папки установки и данных должны быть отдельными.')
    def checkpoint():
        if cancel.exists():
            raise Cancelled('Установка отменена. Проверенные файлы сохранены; можно повторить.')
    last = [0.0]
    def transfer(name, done, total):
        if time.monotonic() - last[0] > 0.25 or done == total:
            last[0] = time.monotonic()
            emit('download', name, downloaded=done, total=total)
    def install(kind):
        emit('components', 'Проверка / установка: ' + kind)
        result = download_components.install(kind, root,
            progress=lambda text: emit('components', text), checkpoint=checkpoint, transfer=transfer)
        emit('components', result)
        checkpoint()
    app = app_root(root)
    sys.path.insert(0, str(app))
    from asr_device import hardware, configured_mode
    existing = root / 'config/config.json'
    if existing.exists():
        mode = configured_mode(json.loads(existing.read_text(encoding='utf8'))['asr'])
    inventory = hardware()
    emit('hardware', ', '.join(inventory['adapters']) or inventory['reason'], hardware=inventory)
    install('required')
    # Inventory is only a download hint. Readiness always comes from full probe.
    if mode == 'gpu' or (mode == 'auto' and any('nvidia' in n.lower() for n in inventory['adapters'])):
        install('cuda')
    checkpoint()
    emit('probe', 'Проверка private runtime и выбранного режима…')
    cfg = configure_resumable(root, data, mode)
    checkpoint()
    from pipeline_config import Config
    selected = Config(cfg).asr_selection()
    statuses = component_status.status(root)
    if statuses['CPU ASR capability']['status'] != 'Available':
        raise RuntimeError('Проверка компонентов не прошла: ' + str(statuses))
    result = dict(selection=selected, components=statuses, hardware=inventory)
    write(root / 'logs/bootstrap-health.json', result)
    emit('health', 'Компоненты проверены. Режим: ' + selected['device'], **result)
    checkpoint()
    if smoke_audio is not None:
        emit('smoke', 'Короткая проверка настоящего ASR…')
        model = Config(cfg).new_model()
        rows, info = model.transcribe(smoke_audio, language='en')
        text = ' '.join(row.text for row in rows)
        if not text.strip() or model.last_run['actual_device'] != selected['device']:
            raise RuntimeError('ASR smoke не подтвердил выбранный backend.')
        write(root / 'logs/bootstrap-smoke.json', dict(last_run=model.last_run, transcript_nonempty=True))
        emit('smoke', 'ASR smoke пройден: ' + model.last_run['actual_device'])
        checkpoint()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--mode', choices=('auto', 'cpu', 'gpu'), required=True)
    p.add_argument('--cancel', type=Path, required=True)
    p.add_argument('--smoke-audio', type=Path)
    a = p.parse_args()
    try:
        run(ROOT, a.data, a.mode, a.cancel, a.smoke_audio)
    except Cancelled as exc:
        emit('cancelled', str(exc));raise SystemExit(130)
    except Exception as exc:
        emit('error', str(exc));raise SystemExit(1)
