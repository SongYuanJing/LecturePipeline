"""One version pointer, crash journal, and launch/update exclusion. No user-data writes."""
import base64
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import uuid


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    data = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf8')
    with pending.open('wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


@contextmanager
def locked(path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('Закройте GUI / остановите workers или дождитесь другого обновления.') from exc
        yield


def journal(root):
    return Path(root)/'run/update-transaction.json'


def recover(root):
    """Caller holds update gate; an unfinished first launch is rolled back."""
    path = journal(root)
    if path.exists():
        state = json.loads(path.read_text(encoding='utf8'))
        with idle_sessions(root):
            atomic(Path(root)/'current.json', base64.b64decode(state['previous'], validate=True))
            path.unlink()
        return True
    return False


@contextmanager
def idle_sessions(root):
    with ExitStack() as stack:
        for path in sorted((Path(root)/'run/sessions').glob('*.lock')):
            stack.enter_context(locked(path))
        yield


@contextmanager
def launch_session(root):
    root = Path(root)
    token = os.environ.get('LP_UPDATE_TOKEN')
    session = root/'run/sessions'/(uuid.uuid4().hex+'.lock')
    with ExitStack() as stack:
        if token:
            state = json.loads(journal(root).read_text(encoding='utf8'))
            if state['token'] != token or json.loads((root/'current.json').read_text()) != state['next']:
                raise RuntimeError('Invalid update trial')
            stack.enter_context(locked(session))
        else:
            with locked(root/'run/update.lock'):
                recover(root)
                stack.enter_context(locked(session))
        try:
            yield
        finally:
            stack.close()
            session.unlink(missing_ok=True)


def gui_ready(root):
    token = os.environ.get('LP_UPDATE_TOKEN')
    if token:
        state = json.loads(journal(root).read_text(encoding='utf8'))
        if state['token'] != token:
            raise RuntimeError('Invalid update trial')
        atomic(Path(root)/'run'/('update-ready-'+token+'.json'),
               dict(token=token, version=os.environ['LP_APP_VERSION'], pid=os.getpid()))
