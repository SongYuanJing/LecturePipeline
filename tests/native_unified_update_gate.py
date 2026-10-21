"""Opt-in local update/rollback gate for an isolated DEV candidate; no network."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--from-version', default='2.0.0-beta.5-dev.1')
    parser.add_argument('--to-version', default='2.0.0-beta.5-dev.2')
    args = parser.parse_args()
    root = args.install.resolve(strict=True)
    candidate = root.parent
    marker = json.loads((candidate / 'DEV_CANDIDATE.json').read_text(encoding='utf-8'))
    if marker.get('purpose') != 'Lecture Pipeline unified DEV' or Path(marker['install_root']).resolve() != root:
        raise ValueError('Only the isolated unified DEV installation is permitted')
    sys.path.insert(0, str(root / 'launcher'))
    import updater
    archive = args.archive.resolve(strict=True)
    name = args.to_version
    current = (root / 'current.json').read_bytes()
    if json.loads(current)['app_version'] != args.from_version:
        raise ValueError('Unexpected isolated DEV baseline')
    data = {p.relative_to(candidate).as_posix(): digest(p)
            for folder in ('data', 'app/config') for p in (candidate / folder).rglob('*') if p.is_file()}
    release = {'tag_name': 'v' + name}
    with patch.object(updater, 'manifest', return_value=({'app_version': name}, {})), \
            patch.object(updater, 'obtain', return_value=archive):
        with patch.object(updater, 'first_launch', side_effect=RuntimeError('deliberate DEV first-launch fault')):
            try:
                updater.apply(root, release, lambda _: None)
            except RuntimeError as exc:
                if 'deliberate DEV' not in str(exc):
                    raise
            else:
                raise AssertionError('Fault did not trigger rollback')
        if (root / 'current.json').read_bytes() != current:
            raise AssertionError('Version pointer changed after rollback')
        if (root / 'run/update-transaction.json').exists():
            raise AssertionError('Update journal remained after rollback')
        result = updater.apply(root, release, lambda _: None)
    after = {p.relative_to(candidate).as_posix(): digest(p)
             for folder in ('data', 'app/config') for p in (candidate / folder).rglob('*') if p.is_file()}
    if data != after or result['status'] != 'updated':
        raise AssertionError('Data changed or update failed')
    print(json.dumps(dict(rollback_pointer_exact=True, data_unchanged=True,
                          current=result['current'], first_launch_pid=result['application_pid']), indent=2))


if __name__ == '__main__':
    main()
