"""Explicit full-package beta.4 upgrade; immutable user data is never rewritten."""
from __future__ import annotations

from contextlib import ExitStack
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import uuid

from update_state import atomic, idle_sessions, idle_workers, locked


BASELINE = '2.0.0-beta.4'
JOURNAL = Path('run/safe-upgrade.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def member(name):
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or path.is_absolute() or any(p in ('', '.', '..') for p in path.parts)
            or any(p.endswith(('.', ' ')) for p in path.parts)):
        raise ValueError('Unsafe upgrade path: ' + str(name))
    return path


def _payload(root, stage, payload):
    root = Path(root).resolve(strict=True)
    stage = Path(stage).resolve(strict=True)
    if (root / '.upgrade-stage').resolve() not in stage.parents:
        raise ValueError('Upgrade stage must be inside this installation')
    if not isinstance(payload, dict) or not isinstance(payload.get('files'), dict):
        raise ValueError('Invalid upgrade payload manifest')
    version = payload.get('app_version')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+-beta\.\d+-dev\.\d+', version):
        raise ValueError('Expected an isolated DEV upgrade version')
    names = set(payload['files'])
    required = {'current.json', 'launcher/launch.py',
                'versions/' + version + '/release.json'}
    if not required <= names:
        raise ValueError('Full upgrade payload is incomplete')
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    if actual != names:
        raise ValueError('Upgrade payload inventory mismatch')
    if len(names) > 10000:
        raise ValueError('Upgrade payload has too many files')
    for name, pin in payload['files'].items():
        member(name)
        path = stage / name
        if path.is_symlink() or path.resolve() != path or not re.fullmatch(r'[0-9a-f]{64}', pin):
            raise ValueError('Unsafe upgrade payload member: ' + name)
        if digest(path) != pin:
            raise ValueError('Upgrade payload SHA-256 mismatch: ' + name)
    pointer = json.loads((stage / 'current.json').read_text(encoding='utf8'))
    release = json.loads((stage / 'versions' / version / 'release.json').read_text(encoding='utf8'))
    if (pointer != {'app_version': version, 'path': 'versions/' + version}
            or release.get('app_version') != version or release.get('config_schema_version') != 1
            or release.get('migration_required') is not False):
        raise ValueError('Upgrade version contract mismatch')
    return root, stage, version


def _baseline(root):
    pointer = json.loads((root / 'current.json').read_text(encoding='utf8'))
    if pointer != {'app_version': BASELINE, 'path': 'versions/' + BASELINE}:
        raise ValueError('Upgrade requires the accepted beta.4 installation')
    release = json.loads((root / pointer['path'] / 'release.json').read_text(encoding='utf8'))
    if release.get('app_version') != BASELINE:
        raise ValueError('Installed beta.4 release mismatch')
    state = json.loads((root / 'bootstrap-state.json').read_text(encoding='utf8'))
    if state.get('status') != 'ready':
        raise ValueError('Existing installation is not ready')
    config = json.loads((root / 'config/config.json').read_text(encoding='utf8'))
    config_dir = root / 'config'
    if (config.get('schema_version') != 1 or
            (config_dir / config.get('application_home', '')).resolve() != root):
        raise ValueError('Existing config does not belong to this installation')
    data = Path(config['data_root']).resolve(strict=True)
    if data == root or root in data.parents or data in root.parents:
        raise ValueError('Data root overlaps application')
    if Path(state['data']).resolve() != data:
        raise ValueError('Setup data root differs from config')
    return state


def _metadata_names(payload):
    return sorted({'current.json', 'package-manifest.json', 'bootstrap-state.json',
                   *(name for name in payload['files'] if '/' not in name and name != 'current.json')})


def _backup(root, token, payload):
    folder = root / 'backups' / ('safe-upgrade-' + token)
    folder.mkdir(parents=True, exist_ok=False)
    names = _metadata_names(payload)
    present = []
    for name in names:
        source = root / name
        if source.is_file():
            dest = folder / 'metadata' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            present.append(name)
    atomic(folder / 'receipt.json', dict(schema_version=1, token=token,
                                        metadata=names, present=present,
                                        next_version=payload['app_version']))
    return folder, names, present


def _manifest(root, payload):
    old = json.loads((root / 'package-manifest.json').read_text(encoding='utf8'))
    files = dict(old['files'])
    top = {name for name in payload['files'] if '/' not in name}
    for name in list(files):
        if name.startswith('launcher/') or name in top:
            files.pop(name)
    files.update(payload['files'])
    return dict(manifest_schema_version=1, app_version=payload['app_version'], files=files)


def _same_version(destination, payload, version):
    prefix = 'versions/' + version + '/'
    expected = {name[len(prefix):]: pin for name, pin in payload['files'].items()
                if name.startswith(prefix)}
    if not destination.is_dir() or destination.is_symlink():
        return False
    actual = {path.relative_to(destination).as_posix() for path in destination.rglob('*')
              if path.is_file() or path.is_symlink()}
    if actual != set(expected):
        return False
    return all(not (destination / name).is_symlink() and digest(destination / name) == pin
               for name, pin in expected.items())


def _recover_locked(root):
    path = root / JOURNAL
    if not path.exists():
        return False
    state = json.loads(path.read_text(encoding='utf8'))
    token = state.get('token', '')
    if state.get('schema_version') != 1 or not re.fullmatch(r'[0-9a-f]{32}', token):
        raise ValueError('Invalid upgrade recovery journal')
    backup = root / 'backups' / ('safe-upgrade-' + token)
    if not backup.is_dir():
        raise ValueError('Upgrade backup missing; no automatic overwrite')
    original_launcher = backup / 'launcher'
    if original_launcher.exists():
        failed = backup / 'failed-launcher'
        if (root / 'launcher').exists():
            if failed.exists():
                raise ValueError('Failed launcher already preserved; manual recovery required')
            os.replace(root / 'launcher', failed)
        os.replace(original_launcher, root / 'launcher')
    for name in state['metadata']:
        member(name)
        if '/' in name:
            raise ValueError('Invalid recovery metadata path')
        original = backup / 'metadata' / name
        target = root / name
        if target.exists():
            failed = backup / 'failed-metadata' / name
            failed.parent.mkdir(parents=True, exist_ok=True)
            if not failed.exists():
                shutil.copy2(target, failed)
        if name in state['present']:
            if not original.is_file():
                raise ValueError('Upgrade metadata backup missing: ' + name)
            atomic(target, original.read_bytes())
        elif target.exists():
            target.unlink()
    path.unlink()
    return True


def recover(root):
    root = Path(root).resolve(strict=True)
    with locked(root / 'run/update.lock'):
        with idle_sessions(root), idle_workers(root):
            return _recover_locked(root)


def rollback(root, backup):
    """Restore an already committed upgrade when its first native launch fails."""
    root = Path(root).resolve(strict=True)
    backup = Path(backup).resolve(strict=True)
    if backup.parent != (root / 'backups').resolve() or not backup.name.startswith('safe-upgrade-'):
        raise ValueError('Rollback backup is outside this installation')
    receipt = json.loads((backup / 'receipt.json').read_text(encoding='utf8'))
    if receipt.get('token') != backup.name.removeprefix('safe-upgrade-'):
        raise ValueError('Rollback receipt identity mismatch')
    with locked(root / 'run/update.lock'):
        with idle_sessions(root), idle_workers(root):
            if (root / JOURNAL).exists() or not (backup / 'launcher').is_dir():
                raise ValueError('Rollback transaction state is not ready')
            current = json.loads((root / 'current.json').read_text(encoding='utf8'))
            if current.get('app_version') != receipt['next_version']:
                raise ValueError('Rollback version mismatch')
            atomic(root / JOURNAL, {key:receipt[key] for key in
                   ('schema_version','token','metadata','present')})
            return _recover_locked(root)


def _health(root, code):
    result = subprocess.run([str(root / 'runtime/asr/python.exe'), '-B', '-X', 'utf8',
        str(root / 'launcher/update_health.py'), str(code)], capture_output=True,
        text=True, encoding='utf8', errors='replace', timeout=90)
    if result.returncode or json.loads(result.stdout).get('ok') is not True:
        raise RuntimeError('Upgraded application health failed: ' + (result.stderr or result.stdout)[-1000:])


def apply(root, stage, payload, *, health=None, fail_at=None, bundle=None):
    root, stage, version = _payload(root, stage, payload)
    with locked(root / 'run/update.lock'):
        with idle_sessions(root), idle_workers(root):
            if (root / JOURNAL).exists():
                raise ValueError('Unfinished upgrade: run recover first')
            previous = _baseline(root)
            destination = root / 'versions' / version
            reuse_version = destination.exists()
            if reuse_version and not _same_version(destination, payload, version):
                raise ValueError('Existing target version differs from verified payload')
            token = uuid.uuid4().hex
            backup, names, present = _backup(root, token, payload)
            next_manifest = _manifest(root, payload)
            atomic(root / JOURNAL, dict(schema_version=1, token=token,
                                        metadata=names, present=present))
            try:
                atomic(root / 'bootstrap-state.json', dict(previous, status='upgrading'))
                if not reuse_version:
                    os.replace(stage / 'versions' / version, destination)
                os.replace(root / 'launcher', backup / 'launcher')
                os.replace(stage / 'launcher', root / 'launcher')
                if fail_at == 'launcher':
                    raise RuntimeError('injected failure after launcher swap')
                for name in payload['files']:
                    if '/' not in name and name != 'current.json':
                        atomic(root / name, (stage / name).read_bytes())
                atomic(root / 'current.json', (stage / 'current.json').read_bytes())
                if fail_at == 'crash_after_pointer':
                    raise KeyboardInterrupt()
                atomic(root / 'package-manifest.json', next_manifest)
                (health or _health)(root, destination)
                atomic(root / 'bootstrap-state.json', dict(previous, status='ready',
                       bundle=bundle or hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()))
                (root / JOURNAL).unlink()
                return dict(status='updated', previous=BASELINE, current=version,
                            backup=str(backup))
            except Exception:
                _recover_locked(root)
                raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('apply', 'recover', 'rollback'))
    p.add_argument('--install', type=Path, required=True)
    p.add_argument('--stage', type=Path)
    p.add_argument('--manifest', type=Path)
    p.add_argument('--bundle')
    p.add_argument('--backup', type=Path)
    args = p.parse_args()
    if args.command == 'recover':
        value = dict(recovered=recover(args.install))
    elif args.command == 'rollback':
        if not args.backup:
            p.error('rollback requires --backup')
        value = dict(rolled_back=rollback(args.install, args.backup))
    else:
        if not args.stage or not args.manifest:
            p.error('apply requires --stage and --manifest')
        value = apply(args.install, args.stage,
                      json.loads(args.manifest.read_text(encoding='utf8')), bundle=args.bundle)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
