"""Apply a previously verified local code update to one isolated unified DEV app."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--from-version', required=True)
    args = parser.parse_args()
    root = args.install.resolve(strict=True)
    candidate = root.parent
    marker = json.loads((candidate / 'DEV_CANDIDATE.json').read_text(encoding='utf8'))
    if marker.get('purpose') != 'Lecture Pipeline unified DEV' or Path(marker['install_root']).resolve() != root:
        raise ValueError('Only an isolated unified DEV installation is permitted')
    current = json.loads((root / 'current.json').read_text(encoding='utf8'))
    if current['app_version'] != args.from_version:
        raise ValueError('Unexpected installed DEV baseline')
    source = args.archive.resolve(strict=True)
    manifest = json.loads(args.manifest.resolve(strict=True).read_text(encoding='utf8'))
    if manifest['app_version'] == args.from_version or manifest['tag'] != 'v' + manifest['app_version']:
        raise ValueError('Unexpected DEV update identity')
    if manifest['artifact']['name'] != source.name or hashlib.sha256(source.read_bytes()).hexdigest() != manifest['artifact']['sha256']:
        raise ValueError('DEV archive hash mismatch')
    if (root / 'versions' / manifest['app_version']).exists():
        raise ValueError('Target DEV version already exists')
    data = Path(marker['data_root']).resolve(strict=True)
    if data.parent != candidate:
        raise ValueError('DEV data must stay inside this candidate')
    before = {'data': hashes(data), 'config': hashes(root / 'config'),
              'queue': hashes(root / 'run/ai_queue')}
    sys.path.insert(0, str(root / 'launcher'))
    import updater
    if updater.runtime_contract(root) != manifest['runtime_contract']:
        raise ValueError('Installed private runtime differs from update contract')
    release = {'tag_name': manifest['tag']}
    with patch.object(updater, 'manifest', return_value=(manifest, {})), \
            patch.object(updater, 'obtain', return_value=source):
        result = updater.apply(root, release, lambda _message: None)
    after = {'data': hashes(data), 'config': hashes(root / 'config'),
             'queue': hashes(root / 'run/ai_queue')}
    if before != after or result['status'] != 'updated':
        raise AssertionError('DEV data/config/queue changed during code update')
    print(json.dumps({'result': result, 'data_config_queue_unchanged': True,
                      'data_files': len(before['data'])}, indent=2))


if __name__ == '__main__':
    main()
