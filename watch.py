#!/usr/bin/env python3
"""
Dev watcher — rebuilds on file changes and triggers live reload in the browser.
Run: python3 watch.py
Open the site at http://192.168.6.110:8080 — the browser reloads automatically on save.
"""
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

RELOAD_PORT = 35729
WATCH_EXTS  = {'.html', '.css', '.js', '.py'}
IGNORE      = {'watch.py', 'build.py'}
WATCH_DIRS  = ['.', '_partials']
POLL_MS     = 300

RELOAD_SCRIPT = f"""<script>
(function(){{
  var es = new EventSource('http://localhost:{RELOAD_PORT}/__reload');
  es.addEventListener('reload', function(){{ location.reload(); }});
  es.onerror = function(){{ setTimeout(function(){{ location.reload(); }}, 1000); }};
}})();
</script>"""

# ── SSE server ────────────────────────────────────────────────────────────────

clients: set = set()
clients_lock = threading.Lock()


class ReloadHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # suppress access log

    def do_GET(self):
        if self.path != '/__reload':
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(b'data: connected\n\n')
        self.wfile.flush()
        with clients_lock:
            clients.add(self.wfile)
        try:
            while True:
                time.sleep(1)
                self.wfile.write(b': heartbeat\n\n')
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with clients_lock:
                clients.discard(self.wfile)


def notify_clients():
    with clients_lock:
        dead = set()
        for w in clients:
            try:
                w.write(b'event: reload\ndata: ok\n\n')
                w.flush()
            except Exception:
                dead.add(w)
        clients.difference_update(dead)


def start_sse_server():
    server = HTTPServer(('', RELOAD_PORT), ReloadHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f'Live reload on :{RELOAD_PORT}')


# ── Build + notify ────────────────────────────────────────────────────────────

def inject_reload_script():
    if not os.path.isdir('dist'):
        return
    for f in os.listdir('dist'):
        if not f.endswith('.html'):
            continue
        p = os.path.join('dist', f)
        html = open(p, encoding='utf-8').read()
        if '/__reload' not in html:
            open(p, 'w', encoding='utf-8').write(
                html.replace('</body>', RELOAD_SCRIPT + '\n</body>')
            )


def rebuild():
    result = subprocess.run([sys.executable, 'build.py'])
    if result.returncode != 0:
        return
    inject_reload_script()
    notify_clients()
    print(f'[{datetime.now().strftime("%H:%M:%S")}] rebuilt')


# ── File watcher (polling) ────────────────────────────────────────────────────

def snapshot():
    mtimes = {}
    for watch_dir in WATCH_DIRS:
        if not os.path.isdir(watch_dir):
            continue
        for entry in os.scandir(watch_dir):
            if not entry.is_file():
                continue
            _, ext = os.path.splitext(entry.name)
            if ext not in WATCH_EXTS:
                continue
            if entry.name in IGNORE:
                continue
            mtimes[entry.path] = entry.stat().st_mtime
    return mtimes


_debounce_timer: threading.Timer | None = None
_debounce_lock = threading.Lock()


def on_change(path):
    global _debounce_timer
    print(f'changed: {path}')
    with _debounce_lock:
        if _debounce_timer:
            _debounce_timer.cancel()
        _debounce_timer = threading.Timer(0.1, rebuild)
        _debounce_timer.start()


def watch_loop():
    prev = snapshot()
    while True:
        time.sleep(POLL_MS / 1000)
        curr = snapshot()
        for path, mtime in curr.items():
            if mtime != prev.get(path):
                on_change(path)
                break
        prev = curr


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    start_sse_server()
    rebuild()
    print('Watching _partials/, *.html, *.css, *.py … Ctrl+C to stop.')
    try:
        watch_loop()
    except KeyboardInterrupt:
        print('\nStopped.')
