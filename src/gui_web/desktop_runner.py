"""One-session DEV dashboard: existing catalog reader plus a local WebView2 window."""
from __future__ import annotations

from contextlib import ExitStack
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading

from readonly_host import handler_for
from readonly_snapshot import SnapshotProvider, contained
from pipeline_config import Config
from update_state import locked


def run(install_root, code_root, config_path):
    install_root = Path(install_root).resolve()
    code_root = Path(code_root).resolve()
    config_path = Path(config_path).resolve()
    candidate_root = install_root.parent
    config = Config(config_path)
    marker = candidate_root / 'DEV_CANDIDATE.json'
    if config.install != code_root:
        raise ValueError('Dashboard version/config mismatch')
    if marker.exists():
        identity = json.loads(marker.read_text(encoding='utf-8'))
        if (identity.get('purpose') != 'Lecture Pipeline unified DEV'
                or Path(identity.get('install_root', '')).resolve() != install_root
                or Path(identity.get('data_root', '')).resolve() != config.data_root
                or not contained(config.data_root, candidate_root)):
            raise ValueError('Dashboard DEV requires its own data inside the candidate root')
        for binding in config.courses().values():
            for key in ('source_audio_folder', 'archive_audio_folder',
                        'raw_output_folder', 'final_output_folder'):
                path = binding.get(key)
                if path is not None and not contained(path, candidate_root):
                    raise ValueError('Dashboard DEV course path leaves the isolated candidate')
        snapshot_root, allowed_roots = candidate_root, ()
    else:
        release = json.loads((code_root / 'release.json').read_text(encoding='utf8'))
        if release.get('distribution_status') != 'beta':
            raise ValueError('Dashboard requires a verified DEV marker or installed beta release')
        roots = {config.data_root}
        for binding in config.courses().values():
            roots.update(binding[key] for key in ('source_audio_folder', 'archive_audio_folder',
                         'raw_output_folder', 'final_output_folder') if binding.get(key))
        snapshot_root, allowed_roots = install_root, tuple(sorted(roots))
    executable = code_root / 'gui_web/native/LecturePipelineDesktop.exe'
    if not executable.is_file():
        raise FileNotFoundError('WebView2 desktop shell is missing; use the Tk fallback')

    gate = ExitStack()
    try:
        gate.enter_context(locked(install_root / 'run/gui-dashboard.lock'))
    except RuntimeError:
        return 0  # An existing dashboard keeps its own host, port, and WebView2 profile.
    with gate:
        provider = SnapshotProvider(snapshot_root, config_path, allowed_roots=allowed_roots)
        token = secrets.token_urlsafe(32)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(provider, session_token=token))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/#session={token}'
            profile = install_root / 'run/gui-webview2-profile'
            command = [str(executable), url, str(profile)]
            status = os.environ.get('LECTURE_PIPELINE_FIRST_LAUNCH_STATUS')
            if status:
                status_path = Path(status).resolve()
                if (status_path.parent != (install_root / 'run').resolve()
                        or not status_path.name.startswith('setup-webview2-')
                        or status_path.suffix != '.status'):
                    raise ValueError('Invalid Setup first-launch status path')
                command.append(str(status_path))
            result = subprocess.run(command, cwd=install_root)
            if result.returncode:
                raise RuntimeError('WebView2 window failed; open Lecture Pipeline (Tk)')
            return 0
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
