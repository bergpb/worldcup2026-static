# worldcup2026-static — CLAUDE.md

Static HTML/CSS/JS site showing all 104 FIFA World Cup 2026 matches with live scores, group standings, knockout bracket, and top scorers. No build step. Pure static files served via nginx.

**Live at:** `worldcup2026.bergpb.dev` (Cloudflare-proxied)
**Local dev:** `192.168.6.110:8080`
**Prod server:** `swarm` (192.168.6.101), app lives at `~/worldcup-2026-static/`

---

## Pages

| File | Description |
|---|---|
| `index.html` | All 104 matches, live card, group filter, score toggle |
| `groups.html` | Group stage standings with live provisional standings |
| `bracket.html` | Knockout bracket from R32 to Final |
| `scorers.html` | Top scorers / Golden Boot race |
| `scorers.json` | Scorer data fetched from API (baked fallback + live from volume) |
| `data.json` | Match data fetched from API (baked fallback + live from volume) |
| `styles.css` | Consolidated CSS for all pages (cache-busted per deploy via `?vBUILD`) |
| `sw.js` | Service worker kill switch — unregisters old SW and clears caches |
| `manifest.json` | PWA manifest |

---

## Branch structure

| Branch | Purpose |
|---|---|
| `main` | Stable base — score updates only |
| `feature/live-match-card` | PR: live card, HT indicator, teamName fallback, CARD_LABELS |
| `feature/i18n` | PR: full i18n system (LANGS, applyLang, cycleLang, data-i18n) |
| `personal` | Personal deployment — merges both PRs + personal customizations |

**Merge order when rebasing:** `feature/live-match-card` first, then `feature/i18n` on top.
**Always deploy from `personal` branch.** Never push `personal` as a PR.

---

## Makefile commands

```bash
make deploy        # rsync to swarm + rebuild prod container + start all prod services
make sync          # rsync only, no rebuild
make dev-up        # start local dev server + fetcher
make dev-down      # stop local dev server
make fetcher-stop  # freeze live data (for testing)
make fetcher-start # unfreeze live data
make patch-ht      # set Netherlands vs Japan → PAUSED 2-1 (half-time test)
make patch-live    # set Netherlands vs Japan → IN_PLAY 1-0 (live test)
make patch-goal    # set Netherlands vs Japan → IN_PLAY 2-0 (simulate goal flash)
make restore       # restart fetcher, live data back within 60s
```

**Always ask before running `make deploy`.** Show what changed first, then wait for go-ahead.

---

## Infrastructure

### Docker Compose (`docker-compose.yml`)

Three services sharing the named volume `wc-data`:

- **`dev`** (profile: `dev`): `nginx:alpine`, mounts local dir + `nginx.conf` + `wc-data:/data:ro`; port `8080`
- **`fetcher`** (profile: `dev` + `prod`): `alpine`, polls API every 60s, writes `data.json` + `scorers.json` to `wc-data:/data`
- **`prod`** (profile: `prod`): built from `Dockerfile`, mounts `wc-data:/data:ro`; port `8081`

The fetcher writes to the volume; nginx containers mount it read-only and serve live files from `/data`, falling back to the baked copies in the image.

### Dockerfile

```dockerfile
FROM nginx:alpine
ARG BUILD_VERSION=dev
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY index.html groups.html bracket.html scorers.html sitemap.xml styles.css /usr/share/nginx/html/
COPY manifest.json sw.js favicon.ico /usr/share/nginx/html/
COPY icons/ /usr/share/nginx/html/icons/
COPY data.json scorers.json /usr/share/nginx/html/
RUN find /usr/share/nginx/html -name "*.html" -exec sed -i "s/vBUILD/v${BUILD_VERSION}/g" {} +
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
```

**`127.0.0.1` not `localhost`** in healthcheck — busybox wget resolves `localhost` as IPv6 and fails.

**Build version injection:** all `*.html` files have `vBUILD` replaced with the git short hash at build time (e.g. `v99e382b`). Used for cache-busting `styles.css?vBUILD`.

### nginx (both `nginx/default.conf` prod and `nginx.conf` dev)

Key rules:
- `data.json` and `scorers.json` — served from `/data` volume first, baked image copy as fallback; `no-cache`
- `sw.js` and `styles.css` — exact-match `location =` blocks with `no-cache` (override the regex block below)
- `*.css|js|png...` — `public, max-age=31536000, immutable`
- `*.html` and `/` — `private, no-store, no-cache, must-revalidate, no-transform` (prevents Cloudflare caching, returns `DYNAMIC`)

**Key nginx rule:** exact `location =` blocks always take priority over regex `location ~*` blocks.

### Data pipeline

1. **Fetcher container**: polls `https://fancy-block-fde3.aking116.workers.dev/competitions/WC/matches?season=2026` and `/scorers?season=2026&limit=200` every 60s, writes to `wc-data` volume
2. nginx serves from volume (live), falls back to baked copy in image
3. **GitHub Actions** (`.github/workflows/fetch-scores.yml`): runs every 5 min, commits `data.json` to repo if changed (used as baked fallback)

**API has no `minute` field** — only `status` is reliable for live state (`IN_PLAY`, `PAUSED`, `FINISHED`, `TIMED`).

### Traefik routing

`worldcup2026.bergpb.dev` is Cloudflare-proxied → uses `web` entrypoint (HTTP port 80), NOT `websecure`. Cloudflare handles SSL termination.

---

## i18n system

Three languages: `en`, `pt`, `es`. Stored in `LANGS` object in each page. Saved to `localStorage('wc2026_lang')`.

- `data-i18n="key"` attributes on elements; `applyLang()` sets `innerHTML` from `LANGS[_lang][key]`
- `cycleLang()` rotates `en → pt → es`
- `teamName(n)` translates country names: `LANGS[_lang]?.teams?.[n] ?? n`
- Nav buttons translated via `['schedule','groups','knockout','scorers','feedback'].forEach(k => ...)` in `applyLang()`

**Team name translations** (`teams:{}` key) live in the `pt` and `es` LANGS blocks in every page that renders team names. When adding a new country, add it to both `pt` and `es` in all relevant pages.

**FLAGS lookup** uses country name as key (e.g. `'Brazil':'br'`). The API returns `Curaçao` (with accent) — the FLAGS map must have the accented version as a key.

---

## JS architecture (index.html)

### Scope structure

- **Global scope**: `LANGS`, `_lang`, `teamName()`, `FLAGS`, `flagImg()`, `flagUrl()`, `normalise()`, `scoreMap`, `lastMatches`, `loadScores()`, `showToast()`, `updateLiveCard()`
- **`render()` function**: inner `FLAGS` (duplicate), inner `flagUrl()` (do NOT remove — used internally by render)
- **IIFE**: page init, `applyLang()`, `restoreAndRender()`

**`flagUrl()` must exist at global scope** — the copy inside `render()` is not accessible to `updateLiveCard()`. Silent TypeError otherwise (caught by loadScores try/catch — always check console when debugging).

### Live scores flow

```javascript
let lastMatches = [];  // cached so live card re-renders on language switch

async function loadScores() {
  const prevScoreMap = { ...scoreMap };
  // fetch data.json, build scoreMap
  // detect score changes → showToast(...)
  lastMatches = data.matches || [];
  updateLiveCard(lastMatches);
}
```

`cycleLang()` calls `updateLiveCard(lastMatches)` so translations update without a refetch.

### `updateLiveCard(matches)`

- Filters for `IN_PLAY` or `PAUSED` matches
- `PAUSED` → shows HT label (`HT` / `INT` / `ET` by language)
- `IN_PLAY` → minute div is empty (API doesn't return minute)
- `getScore()` uses `LANGS[_lang]` — NOT `CARD_LABELS` (only exists on `feature/live-match-card`)

### `teamsHtml(teamsStr, score)`

For `FINISHED` non-draw matches, wraps winner in `.team-winner` (bold) and loser in `.team-loser` (muted).

---

## Live Match Card (`#live-match-card`)

Located just above `#next-match-card`.

```
    • LIVE / AO VIVO / EN VIVO    ← pulsing dot
Netherlands 🏴 1–0 🏴 Japan
          HT / INT / ET
     GROUP F · DALLAS
```

LANGS keys: `live_label`, `ht_label`.

---

## Scorers page (`scorers.html`)

- Fetches `scorers.json` (live from volume, falls back to baked copy)
- Translates column headers: `col_player`, `col_goals`, `col_assists`, `col_pens`, `col_mp`
- Translates country names via `teamName()` with `teams:{}` maps in pt/es LANGS
- FLAGS lookup uses `s.team.shortName` — must match key in FLAGS exactly (including accents)
- No Feedback nav button or footer on this page (removed intentionally)

---

## PWA / Service Worker

**`sw.js` is a kill switch only** — no caching, no fetch handler.
- On install: `skipWaiting`
- On activate: clear all caches → navigate all clients → `unregister()`

**`index.html` SW cleanup script** (at bottom of `<body>`):
```javascript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
  caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
}
```
Does not register a new SW. Safe to keep permanently.

**Never delete `sw.js`** — a 404 does not auto-unregister a SW in Chrome. Always serve a kill switch.

---

## Personal branch customizations

### `HIDE_BMC = true`

Adds `hide-bmc` to `<body>`. Hides Buy Me a Coffee widgets, `#lnk-notify`, `#lnk-feedback`, `#lnk-madeby`, `#feedback-nav`.

### Domain

All upstream `kingdoggydog.github.io/worldcup2026` references replaced with `worldcup2026.bergpb.dev`. `<meta name="author">` is `bergpb`.

### `styles.css` cache busting

All pages: `<link rel="stylesheet" href="styles.css?vBUILD">`. Dockerfile `sed` replaces `vBUILD` with git hash at build time → forces fresh CSS on every deploy.

---

## Cloudflare caching

**Diagnosing:** `curl -sI https://worldcup2026.bergpb.dev/sw.js | grep cf-cache-status`
- `HIT` = Cloudflare serving cached copy → purge needed
- `BYPASS` or `DYNAMIC` = passing through to origin → safe

**Purging:** Cloudflare dashboard → zone → Caching → Purge Everything. Do this after any deploy that changes files previously served with long-lived cache headers.

**TODO:** Add `make cf-purge` using Cloudflare API (needs Zone ID + API token with cache purge permission).

**Header behaviour:**
- `Cache-Control: private` → Cloudflare returns `DYNAMIC`
- `no-store` → returns `BYPASS`
- `public, max-age=...` → returns `HIT` after first visit

---

## Testing live match state

```bash
make patch-ht    # Netherlands vs Japan → PAUSED 2-1 (test half-time label)
make patch-live  # Netherlands vs Japan → IN_PLAY 1-0 (test live card)
make patch-goal  # Netherlands vs Japan → IN_PLAY 2-0 (test goal toast)
make restore     # restart fetcher after patching
```

Patching writes to the `wc-data` volume via a temp alpine container — dev nginx is read-only so `docker cp` into it won't work.

---

## Known quirks / gotchas

- `flagUrl()` must be at global scope — silent TypeError inside loadScores try/catch
- `loadScores()` try/catch swallows all errors from `updateLiveCard` — always check console
- API has no `minute` field — only `status`
- `CARD_LABELS` / `_cardLang` only exist on `feature/live-match-card`; `personal` uses `LANGS[_lang]` in `getScore()`
- Dev nginx mounts volume read-only — use a temp alpine container to write to `wc-data`
- `#feedback-nav` ID on the feedback nav in `index.html` — CSS hide rule depends on this exact ID
- Curaçao in the API returns as `"Curaçao"` (with accent) — FLAGS map key must match exactly
- `localhost` in busybox wget resolves as IPv6 → healthcheck must use `127.0.0.1`
- Cloudflare-proxied services use `web` entrypoint; DNS-only use `websecure`
- `Cache-Control: private` prevents CF caching (`DYNAMIC`); `no-store` returns `BYPASS`; `public, max-age=...` returns `HIT`
- When adding a new HTML page: add it to `Dockerfile` COPY, add `scorers.json`-style nginx location if it has dynamic data, add nav translation keys to LANGS in all other pages
