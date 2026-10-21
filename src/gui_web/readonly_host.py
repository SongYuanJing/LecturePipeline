"""Local GET-only host for the VIC-28 dashboard. Uses the existing DEV Python runtime."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import webbrowser

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from readonly_snapshot import SnapshotProvider

WEB = Path(__file__).resolve().parent / 'web'
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/ui.js': ('ui.js', 'text/javascript; charset=utf-8'),
          '/glass-base.css': ('glass-base.css', 'text/css; charset=utf-8'),
          '/dashboard.css': ('dashboard.css', 'text/css; charset=utf-8')}


def handler_for(provider):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never create a log in the installation or data root.

        def send(self, status, content, mime):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/v1/snapshot':
                payload = json.dumps(provider.snapshot(), ensure_ascii=False, allow_nan=False).encode('utf-8')
                self.send(200, payload, 'application/json; charset=utf-8')
            elif path in ASSETS:
                filename, mime = ASSETS[path]
                self.send(200, (WEB / filename).read_bytes(), mime)
            else:
                self.send(404, b'Not found', 'text/plain; charset=utf-8')

        def deny(self):
            self.send(405, b'Read-only dashboard: commands are not implemented.', 'text/plain; charset=utf-8')

        do_POST = do_PUT = do_PATCH = do_DELETE = deny
    return Handler


def main():
    parser = argparse.ArgumentParser(description='VIC-28 local read-only dashboard')
    parser.add_argument('--dev-root', type=Path, default=Path(r'C:\PipLine GPT WORK'))
    parser.add_argument('--config', type=Path)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--open', action='store_true', help='Open the local UI in the default browser')
    parser.add_argument('--visual-fixture', action='store_true', help='Create and freeze an explicitly synthetic UI test set')
    parser.add_argument('--fixture-root', type=Path)
    parser.add_argument('--fixture-scenario', choices=['normal', 'stale', 'unknown', 'preparing'], default='normal')
    args = parser.parse_args()
    root = args.dev_root.resolve(strict=True)
    config = args.config or root / 'app/config/config.json'
    if args.visual_fixture:
        from visual_fixture import create_fixture
        folder = 'vic28-visual-fixture' + (('-' + args.fixture_scenario) if args.fixture_scenario != 'normal' else '')
        root = (args.fixture_root or Path(__file__).resolve().parents[2] / '.local' / folder).resolve()
        config = create_fixture(root, args.fixture_scenario)
    elif args.fixture_scenario != 'normal':
        parser.error('--fixture-scenario requires --visual-fixture')
    provider = SnapshotProvider(root, config, fixture=args.visual_fixture)
    first = provider.snapshot()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(provider))
    url = 'http://127.0.0.1:' + str(server.server_address[1])
    print('VIC-28 · ' + ('SYNTHETIC FROZEN FIXTURE' if args.visual_fixture else 'DEV READ ONLY'), flush=True)
    print('Source: ' + str(config), flush=True)
    print('Snapshot: ' + ('available' if first['available'] else 'unavailable; see UI diagnostics'), flush=True)
    print('Local: ' + url, flush=True)
    print('No workers, ASR, updater, dictionary or system tasks are started. Ctrl+C stops only this viewer.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
