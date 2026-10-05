"""Supplier downloads into a verified cache; existing importers own installation.

No pip, global runtime, driver, configuration or user-data changes.
"""
import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import tempfile
import time
import urllib.error
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


def open_url(url, headers=None):
    return urllib.request.build_opener(HTTPSRedirect()).open(
        urllib.request.Request(url, headers={'User-Agent': 'LecturePipeline-bootstrap', **(headers or {})}), timeout=60)


RESUME_THRESHOLD = 128 * 1024 * 1024
RESUME_ATTEMPTS = 3
RESUME_CHECKPOINT = 8 * 1024 * 1024


def resumable_fetch(url, sha256, name, target, size, progress, checkpoint, transfer):
    """Persist locally checksummed prefixes; only the pinned whole hash authenticates bytes.

    HTTP rules: RFC 9110 sections 13.1.5, 14 and 15.3.7. A partial is never a
    cache hit. Short fixed names also avoid extending the Windows wheel path.
    """
    partial = target.parent / '.partial'
    metadata = target.parent / '.partial.json'
    temporary = target.parent / '.partial.tmp'
    identity = dict(schema=1, url=url, sha256=sha256, name=name, size=size)

    def discard():
        for path in (partial, metadata, temporary):
            path.unlink(missing_ok=True)

    def save(output, h, etag):
        output.flush()
        os.fsync(output.fileno())
        temporary.write_text(json.dumps(dict(identity, offset=output.tell(),
            prefix_sha256=h.hexdigest(), etag=etag)), encoding='utf8')
        os.replace(temporary, metadata)

    # A persistent advisory lock prevents two GUI/CLI requests appending to one prefix.
    with (target.parent / '.resume.lock').open('a+b') as lock:
        lock.seek(0, 2)
        if not lock.tell():
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if target.is_file() and target.stat().st_size == size and digest(target) == sha256:
            progress('Verified cache: ' + name)
            return target
        offset, etag, h = 0, None, hashlib.sha256()
        if partial.exists() or metadata.exists():
            try:
                state = json.loads(metadata.read_text(encoding='utf8'))
                offset = state['offset']
                if (any(state.get(k) != v for k, v in identity.items())
                        or type(offset) is not int or not 0 <= offset <= partial.stat().st_size <= size):
                    raise ValueError('Partial identity/size mismatch')
                etag = state.get('etag')
                with partial.open('rb') as source:
                    remaining = offset
                    while remaining:
                        checkpoint()
                        block = source.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ValueError('Partial truncated during verification')
                        h.update(block); remaining -= len(block)
                if h.hexdigest() != state['prefix_sha256']:
                    raise ValueError('Partial prefix hash mismatch')
                # A crash can leave an uncheckpointed tail; never resume beyond proof.
                with partial.open('r+b') as output:
                    output.truncate(offset)
            except (OSError, ValueError, KeyError, TypeError):
                discard(); offset, etag, h = 0, None, hashlib.sha256()
                progress('Discarded invalid partial: ' + name)
        for attempt in range(RESUME_ATTEMPTS):
            checkpoint()
            if offset == size:
                break
            headers = {'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = 'bytes=' + str(offset) + '-'
                if etag:
                    headers['If-Range'] = etag
            try:
                with open_url(url, headers) as response:
                    if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                        raise ValueError('Non-HTTPS response rejected')
                    status = response.status
                    length = response.headers.get('Content-Length')
                    response_etag = response.headers.get('ETag')
                    if response_etag and (response_etag.startswith('W/') or not response_etag.startswith('"')):
                        response_etag = None
                    if response.headers.get('Content-Encoding', 'identity') != 'identity':
                        raise ValueError('Encoded artifact response rejected')
                    if status == 200:
                        # Range ignored / If-Range changed: this is a fresh whole body.
                        if offset:
                            progress('Range ignored; restarting: ' + name)
                        discard(); offset, h, etag = 0, hashlib.sha256(), response_etag
                        end = size - 1
                        if length is None or not length.isdigit() or int(length) != size:
                            raise ValueError('Pinned size mismatch: ' + name)
                    elif status == 206:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                        valid = (match and int(match[1]) == offset and offset <= int(match[2]) < size
                            and int(match[3]) == size and (length is None or
                                (length.isdigit() and int(length) == int(match[2]) - offset + 1))
                            and (not etag or response_etag == etag))
                        if not valid:
                            discard(); offset, etag, h = 0, None, hashlib.sha256()
                            progress('Incompatible Content-Range/identity; restarting: ' + name)
                            if attempt == RESUME_ATTEMPTS - 1:
                                raise ValueError('Incompatible Content-Range/identity: ' + name)
                            continue
                        end = int(match[2]); etag = response_etag
                    else:
                        raise ValueError('Unexpected HTTP status: ' + str(status))
                    progress(('Resuming at ' + str(offset) + ': ' if offset else 'Downloading: ') + name)
                    with partial.open('r+b' if partial.exists() else 'w+b') as output:
                        output.seek(offset)
                        saved = offset
                        try:
                            while True:
                                checkpoint()
                                block = response.read(1024 * 1024)
                                if not block:
                                    break
                                if offset + len(block) > end + 1:
                                    raise ValueError('Artifact exceeds expected size: ' + name)
                                output.write(block); h.update(block); offset += len(block)
                                transfer(name, offset, size)
                                if offset - saved >= RESUME_CHECKPOINT:
                                    save(output, h, etag); saved = offset
                        finally:
                            # Includes cooperative Cancel and network read errors.
                            save(output, h, etag)
                    if offset != end + 1:
                        raise ConnectionError('Incomplete artifact response: ' + name)
                    if offset == size:
                        break
            except urllib.error.HTTPError as exc:
                if exc.code == 416:
                    discard(); offset, etag, h = 0, None, hashlib.sha256()
                elif exc.code not in (408, 429, 500, 502, 503, 504):
                    raise
                if attempt == RESUME_ATTEMPTS - 1:
                    raise
            except (TimeoutError, ConnectionError, urllib.error.URLError, ssl.SSLError, http.client.IncompleteRead):
                if attempt == RESUME_ATTEMPTS - 1:
                    raise
            except ValueError:
                discard()
                raise
            if attempt < RESUME_ATTEMPTS - 1:
                delay = 2 ** attempt
                progress('Retry in ' + str(delay) + 's: ' + name)
                for _ in range(delay * 10):
                    checkpoint(); time.sleep(0.1)
        checkpoint()
        if offset != size:
            raise ConnectionError('Download incomplete after bounded retries: ' + name)
        if h.hexdigest() != sha256 or partial.stat().st_size != size or digest(partial) != sha256:
            discard()
            raise ValueError('SHA256/size mismatch: ' + name)
        os.replace(partial, target)
        metadata.unlink(missing_ok=True)
        progress('Verified download: ' + name)
        return target


def fetch(url, sha256, name, cache, *, limit, progress=lambda message: None,
          checkpoint=lambda: None, transfer=lambda name, done, total: None, expected_size=None, resume=False):
    """Only verified whole files are cache hits; large pinned files retain safe prefixes."""
    checkpoint()
    filename(name)
    if not isinstance(sha256, str) or not re.fullmatch('[0-9a-f]{64}', sha256):
        raise ValueError('Invalid pinned SHA256')
    parts = urllib.parse.urlsplit(url)
    release = (parts.hostname == 'github.com' and re.fullmatch(
        r'/SongYuanJing/LecturePipeline/releases/download/v[0-9][A-Za-z0-9.\-]*/[A-Za-z0-9_.\-]+', parts.path))
    if (parts.scheme != 'https' or (parts.hostname not in SUPPLIERS and not release)
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError('Expected an official HTTPS supplier URL')
    target = Path(cache) / sha256 / name
    if expected_size is not None and (type(expected_size) is not int or not 0 < expected_size <= limit):
        raise ValueError('Invalid pinned size')
    if resume and expected_size is None:
        raise ValueError('Resume requires a pinned size')
    if (target.is_file() and (expected_size is None or target.stat().st_size == expected_size)
            and digest(target) == sha256):
        progress('Verified cache: ' + name)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if expected_size is not None and (resume or expected_size >= RESUME_THRESHOLD):
        return resumable_fetch(url, sha256, name, target, expected_size, progress, checkpoint, transfer)
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
            length = response.headers.get('Content-Length') if hasattr(response, 'headers') else None
            expected = int(length) if length and length.isdigit() else None
            for block in iter(lambda: response.read(1024 * 1024), b''):
                checkpoint()
                total += len(block)
                if total > limit:
                    raise ValueError('Component exceeds pinned size limit: ' + name)
                output.write(block)
                h.update(block)
                transfer(name, total, expected)
            if expected_size is not None and total != expected_size:
                raise ValueError('Pinned size mismatch: ' + name)
            if h.hexdigest() != sha256:
                raise ValueError('SHA256 mismatch: ' + name)
            output.flush()
            os.fsync(output.fileno())
        checkpoint()
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


def install(kind, root=ROOT, progress=lambda message: None, *,
            checkpoint=lambda: None, transfer=lambda name, done, total: None):
    """Download one component or the CPU prerequisites. CUDA is explicit opt-in."""
    root = Path(root)
    checkpoint()
    hooks = dict(progress=progress, checkpoint=checkpoint, transfer=transfer)
    if kind == 'required':
        return '\n'.join(install(k, root, **hooks) for k in ('pyav', 'ctranslate2', 'model'))
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
                       limit=100_000_000, **hooks)
        checkpoint()
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
                cached = fetch(url, sha256, name, cache, limit=spec['bytes'],
                               expected_size=spec.get('file_sizes', {}).get(name), **hooks)
                # Same volume; fall back to copy on filesystems without hard links.
                try:
                    os.link(cached, source / name)
                except OSError:
                    shutil.copy2(cached, source / name)
        else:
            wheels = [fetch(item['official_source'], item['sha256'], name, cache,
                            limit=item['bytes'], expected_size=item['bytes'], **hooks)
                      for name, item in spec['wheels'].items()]
            extract_cuda(wheels, spec, source)
        checkpoint()
        return module.install(source, root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=('required', 'pyav', 'ctranslate2', 'model', 'cuda'))
    args = parser.parse_args()
    try:
        print(install(args.component, progress=lambda message: print(message, flush=True)))
    except Exception as exc:
        raise SystemExit('Component download/import failed: ' + str(exc))
