"""Supplier downloads into a verified cache; existing importers own installation.

No pip, global runtime, driver, configuration or user-data changes.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SUPPLIERS = {'files.pythonhosted.org', 'huggingface.co'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def filename(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value)
            or value.endswith('.') or value.split('.')[0].upper() in
            {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
        raise ValueError('Unsafe component filename')
    return value


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Non-HTTPS download redirect rejected')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url):
    return urllib.request.build_opener(HTTPSRedirect()).open(
        urllib.request.Request(url, headers={'User-Agent': 'LecturePipeline-bootstrap'}), timeout=60)


def fetch(url, sha256, name, cache, *, limit, progress=lambda message: None):
    """Only complete verified bytes become cache hits. Interrupted bytes are removed."""
    filename(name)
    if not isinstance(sha256, str) or not re.fullmatch('[0-9a-f]{64}', sha256):
        raise ValueError('Invalid pinned SHA256')
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in SUPPLIERS or parts.username or parts.password:
        raise ValueError('Expected an official HTTPS supplier URL')
    target = Path(cache) / sha256 / name
    if target.is_file() and digest(target) == sha256:
        progress('Verified cache: ' + name)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    # Unique temporary file: parallel downloads cannot expose partial bytes.
    # The hash directory identifies the artifact. Repeating a long wheel name
    # plus a random suffix can exceed MAX_PATH although the final cache file fits.
    fd, pending = tempfile.mkstemp(prefix='.download-', suffix='.part', dir=target.parent)
    pending = Path(pending)
    try:
        with os.fdopen(fd, 'wb') as output, open_url(url) as response:
            if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                raise ValueError('Non-HTTPS response rejected')
            total = 0
            h = hashlib.sha256()
            progress('Downloading: ' + name)
            for block in iter(lambda: response.read(1024 * 1024), b''):
                total += len(block)
                if total > limit:
                    raise ValueError('Component exceeds pinned size limit: ' + name)
                output.write(block)
                h.update(block)
            if h.hexdigest() != sha256:
                raise ValueError('SHA256 mismatch: ' + name)
            output.flush()
            os.fsync(output.fileno())
        os.replace(pending, target)
        progress('Verified download: ' + name)
        return target
    finally:
        pending.unlink(missing_ok=True)


def read_spec(root, kind):
    return json.loads((root / 'launcher' / (kind + '-manifest.json')).read_text(encoding='utf8'))


def extract_cuda(wheels, spec, target):
    """Extract only pinned DLL basenames, never supplier-controlled paths."""
    expected = {filename(n): h for n, h in spec['files'].items()}
    found = set()
    total = 0
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            for info in archive.infolist():
                name = PurePosixPath(info.filename).name
                if name not in expected:
                    continue
                if name in found:
                    raise ValueError('Duplicate CUDA DLL: ' + name)
                total += info.file_size
                if total > spec['bytes']:
                    raise ValueError('CUDA DLLs exceed pinned size')
                with archive.open(info) as source, (target / name).open('xb') as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                if digest(target / name) != expected[name]:
                    raise ValueError('CUDA DLL hash mismatch: ' + name)
                found.add(name)
    if found != set(expected):
        raise ValueError('Missing pinned CUDA DLLs: ' + ', '.join(sorted(set(expected) - found)))


def install(kind, root=ROOT, progress=lambda message: None):
    """Download one component or the CPU prerequisites. CUDA is explicit opt-in."""
    root = Path(root)
    if kind == 'required':
        return '\n'.join(install(k, root, progress) for k in ('pyav', 'ctranslate2', 'model'))
    if kind not in ('pyav', 'ctranslate2', 'model', 'cuda'):
        raise ValueError('Unknown component')
    import component_status
    import import_pyav
    import import_ctranslate2
    import import_model
    import import_cuda
    modules = {'pyav': import_pyav, 'ctranslate2': import_ctranslate2,
               'model': import_model, 'cuda': import_cuda}
    module = modules[kind]
    state = (component_status.wheel_state(module, root) if kind in ('pyav', 'ctranslate2')
             else component_status.asset_state(root, kind))
    if state['status'] == 'Valid':
        return kind + ': already verified'
    if state['status'] != 'Missing':
        raise ValueError(kind + ': existing component invalid; preserved, not overwritten')
    spec = read_spec(root, kind)
    cache = root / 'cache/downloads'
    if kind in ('pyav', 'ctranslate2'):
        source = fetch(spec['official_source'], spec['sha256'], spec['filename'], cache,
                       limit=100_000_000, progress=progress)
        return module.install(source, root)
    # Private temporary source directory. Existing staged import owns publication.
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=kind + '-', dir=cache) as temporary:
        source = Path(temporary)
        if kind == 'model':
            if spec['model'] != 'Systran/faster-whisper-large-v3' or not re.fullmatch('[0-9a-f]{40}', spec['revision']):
                raise ValueError('Expected pinned large-v3 revision')
            for name, sha256 in spec['files'].items():
                filename(name)
                url = 'https://huggingface.co/' + spec['model'] + '/resolve/' + spec['revision'] + '/' + name
                cached = fetch(url, sha256, name, cache, limit=spec['bytes'], progress=progress)
                # Same volume; fall back to copy on filesystems without hard links.
                try:
                    os.link(cached, source / name)
                except OSError:
                    shutil.copy2(cached, source / name)
        else:
            wheels = [fetch(item['official_source'], item['sha256'], name, cache,
                            limit=item['bytes'], progress=progress)
                      for name, item in spec['wheels'].items()]
            extract_cuda(wheels, spec, source)
        return module.install(source, root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=('required', 'pyav', 'ctranslate2', 'model', 'cuda'))
    args = parser.parse_args()
    try:
        print(install(args.component, progress=lambda message: print(message, flush=True)))
    except Exception as exc:
        raise SystemExit('Component download/import failed: ' + str(exc))
