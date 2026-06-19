#!/usr/bin/env node
// Dev watcher — rebuilds on file changes and triggers live reload in the browser.
// Run: node watch.js (or: make watch)
// Open the site at http://192.168.6.110:8080 — the browser reloads automatically on save.

const fs   = require('fs');
const path = require('path');
const http = require('http');
const { spawnSync } = require('child_process');

// ── SSE server for live reload ─────────────────────────────────────────────
const clients = new Set();
const RELOAD_PORT = 35729;

http.createServer((req, res) => {
  if (req.url !== '/__reload') { res.writeHead(404); res.end(); return; }
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
  });
  res.write('data: connected\n\n');
  clients.add(res);
  req.on('close', () => clients.delete(res));
}).listen(RELOAD_PORT, () => console.log(`Live reload on :${RELOAD_PORT}`));

// ── Reload script injected into dist/ HTML (watch mode only) ──────────────
const RELOAD_SCRIPT = `<script>
(function(){
  var es = new EventSource('http://localhost:${RELOAD_PORT}/__reload');
  es.addEventListener('reload', function(){ location.reload(); });
  es.onerror = function(){ setTimeout(function(){ location.reload(); }, 1000); };
})();
</script>`;

function injectReloadScript() {
  fs.readdirSync('dist').filter(f => f.endsWith('.html')).forEach(f => {
    const p = path.join('dist', f);
    let html = fs.readFileSync(p, 'utf8');
    if (!html.includes('35729/__reload'))
      fs.writeFileSync(p, html.replace('</body>', RELOAD_SCRIPT + '\n</body>'));
  });
}

// ── Build + notify ─────────────────────────────────────────────────────────
function rebuild() {
  const res = spawnSync('python3', ['build.py'], { stdio: 'inherit' });
  if (res.status !== 0) return;
  injectReloadScript();
  clients.forEach(c => c.write('event: reload\ndata: ok\n\n'));
  console.log(`[${new Date().toLocaleTimeString()}] rebuilt`);
}

// ── File watcher ──────────────────────────────────────────────────────────
const WATCH_EXTS = new Set(['.html', '.css', '.js']);
const IGNORE = new Set(['watch.js', 'build.py']);
let timer = null;

function onChange(filename) {
  if (!filename) return;
  const ext = path.extname(filename);
  if (!WATCH_EXTS.has(ext)) return;
  if (filename.startsWith('dist') || IGNORE.has(path.basename(filename))) return;
  clearTimeout(timer);
  timer = setTimeout(() => { console.log(`changed: ${filename}`); rebuild(); }, 80);
}

fs.watch('_partials', (_, f) => onChange(path.join('_partials', f)));
fs.watch('.', (_, f) => { if (f && !f.startsWith('dist') && !f.startsWith('.')) onChange(f); });

// Initial build
rebuild();
console.log('Watching _partials/, *.html, styles.css … Ctrl+C to stop.');
