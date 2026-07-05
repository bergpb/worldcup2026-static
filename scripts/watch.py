#!/usr/bin/env python3
"""
Dev watcher — rebuilds on file changes and triggers live reload in the browser.
Run: python3 scripts/watch.py
Open the site at http://192.168.6.110:8080 — the browser reloads automatically on save.
"""
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime

RELOAD_PORT = 35729
WATCH_EXTS  = {'.html', '.css', '.js', '.py'}
WATCH_DIRS  = ['.', '_partials']
POLL_MS     = 300

RELOAD_SCRIPT = f"""<script>
(function(){{
  var es = new EventSource('http://' + location.hostname + ':{RELOAD_PORT}/__reload');
  es.addEventListener('reload', function(){{ location.reload(); }});
  es.onerror = function(){{ setTimeout(function(){{ location.reload(); }}, 1000); }};
}})();
</script>"""

# ── SSE server (raw socket) ───────────────────────────────────────────────────
# Raw socket avoids BaseHTTPRequestHandler quirks (implicit timeouts, HTTP/1.0
# close-connection behaviour) that caused the SSE stream to drop immediately.

clients: set = set()
clients_lock = threading.Lock()


def _handle_sse_client(conn: socket.socket):
    try:
        # Read request headers
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = conn.recv(1024)
            if not chunk:
                return
            data += chunk

        first_line = data.split(b'\r\n')[0].decode(errors='replace')
        if '/__reload' not in first_line:
            conn.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n')
            return

        conn.sendall(
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/event-stream\r\n'
            b'Cache-Control: no-cache\r\n'
            b'Connection: keep-alive\r\n'
            b'Access-Control-Allow-Origin: *\r\n'
            b'\r\n'
            b'data: connected\n\n'
        )

        q: queue.Queue = queue.Queue()
        with clients_lock:
            clients.add(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    conn.sendall(msg)
                except queue.Empty:
                    conn.sendall(b': heartbeat\n\n')
        except Exception:
            pass
        finally:
            with clients_lock:
                clients.discard(q)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def notify_clients():
    with clients_lock:
        for q in clients:
            q.put(b'event: reload\ndata: ok\n\n')


def start_sse_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', RELOAD_PORT))
    sock.listen(5)

    def _serve():
        while True:
            try:
                conn, _ = sock.accept()
                threading.Thread(target=_handle_sse_client, args=(conn,), daemon=True).start()
            except Exception:
                break

    threading.Thread(target=_serve, daemon=True).start()
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
    result = subprocess.run([sys.executable, 'scripts/build.py'])
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
