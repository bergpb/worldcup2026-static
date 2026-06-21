# worldcup2026-static — CLAUDE.md

Static HTML/CSS/JS site showing all 104 FIFA World Cup 2026 matches with live scores, group standings, knockout bracket, and top scorers. Has a partial-based build step (`python3 build.py`) that assembles pages into `dist/`.

**Live at:** `worldcup.bergpb.dev` (Cloudflare-proxied) — `worldcup2026.bergpb.dev` 308-redirects here
**Local dev:** `192.168.6.110:8080`
**Prod server:** `swarm` (192.168.6.101), app lives at `~/worldcup-2026-static/`

---

## Pages

| Source file | Description |
|---|---|
| `index.html` | All 104 matches, live card, group filter, score toggle |
| `groups.html` | Group stage standings with live provisional standings |
| `bracket.html` | Knockout bracket from R32 to Final |
| `scorers.html` | Top scorers / Golden Boot race |
| `scorers.json` | Scorer data fetched from API (baked fallback + live from volume) |
| `data.json` | Match data fetched from API (baked fallback + live from volume) |
| `match-details.json` | Per-match goals, OG, penalties, cards — served from volume only (no baked fallback); used by event card popup and live card details |
| `group-winners.json` | `{letter: {first, second}}` for fully completed groups — served from volume only; used by `applyGroupWinners()` in knockout section |
| `styles.css` | Consolidated CSS for all pages (cache-busted per deploy via `?vBUILD`) |
| `sw.js` | Service worker kill switch — unregisters old SW and clears caches |
| `manifest.json` | PWA manifest |

Source files contain only empty `<!-- partial:name --><!-- /partial:name -->` markers — never edit `dist/` directly.

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

## Build system

### `build.py`

Reads source files (with empty markers), injects partials, writes fully-assembled HTML to `dist/`. Run before deploying or testing locally.

```bash
python3 build.py           # build → dist/
python3 build.py --check   # exit 1 if dist/ is stale (CI safety)
python3 build.py --strip   # empty all markers in source files (run before committing if needed)
```

`dist/` is gitignored and self-contained (HTML + CSS + icons + static assets).

### `_partials/`

| File | Injected into |
|---|---|
| `head.html` | All pages — `<!DOCTYPE html>` through shared `<head>` tags; uses `{{PAGE_TITLE}}`, `{{PAGE_DESCRIPTION}}`, `{{PAGE_CANONICAL}}` |
| `nav.html` | All pages — nav buttons; build.py adds `active` class for the current page |
| `langs.html` | All pages — `<script>` block defining `LANGS_COMMON` (shared nav/timezone/teams translations) |
| `tz-options.html` | index, groups, bracket — `<option>` list for timezone selector |
| `common.js` | All pages — `cycleLang()`, `applyLang()`, `langBtnHTML()`, `shareApp()`, localStorage lang persistence |
| `footer.html` | All pages — `<div class="footer">` with `#footer-line1` and `#footer-line2`; includes credits |
| `jsonld.html` | index only — JSON-LD structured data (all 104 match events), injected before `</body>` |

**Adding a new HTML page:** add it to the `PAGES` array in `build.py` with `title`, `description`, `canonical`, and `nav` key; add `<!-- partial:X --><!-- /partial:X -->` markers; update the Dockerfile if needed.

---

## Makefile commands

```bash
make build         # assemble partials → dist/
make check         # verify dist/ is up-to-date (exits non-zero if stale)
make deploy        # build + rsync to swarm + rebuild prod container
make sync          # rsync only, no rebuild
make up            # start local dev (nginx + builder + fetcher)
make down          # stop local dev
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

Four services sharing the named volume `wc-data`:

- **`dev`** (profile: `dev`): `nginx:alpine`, mounts `dist/` + `nginx.conf` + `wc-data:/data:ro`; port `8080`
- **`builder`** (profile: `dev`): `python:3.12-alpine`, runs `watch.py` — watches source files, rebuilds to `dist/`, serves live-reload SSE on port `35729`
- **`fetcher`** (profile: `dev` + `prod`): `alpine`, polls API every 60s, writes `data.json` + `scorers.json` to `wc-data:/data`
- **`prod`** (profile: `prod`): built from `Dockerfile`, mounts `wc-data:/data:ro`; port `8081`

`make up` starts all three dev services. The browser auto-reloads on any source file change via the builder's SSE server at `:35729`.

### Dockerfile

```dockerfile
FROM nginx:alpine
ARG BUILD_VERSION=dev
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY dist/ /usr/share/nginx/html/
RUN find /usr/share/nginx/html -name "*.html" -exec sed -i "s/vBUILD/v${BUILD_VERSION}/g" {} +
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
```

**`127.0.0.1` not `localhost`** in healthcheck — busybox wget resolves `localhost` as IPv6 and fails.

**Build version injection:** all `*.html` files in `dist/` have `vBUILD` replaced with the git short hash at build time. Used for cache-busting `styles.css?vBUILD`.

### nginx (both `nginx/default.conf` prod and `nginx.conf` dev)

Key rules:
- `data.json` and `scorers.json` — served from `/data` volume first, baked image copy as fallback; `no-cache`
- `sw.js` and `styles.css` — exact-match `location =` blocks with `no-cache`
- `*.css|js|png...` — `public, max-age=31536000, immutable`
- `*.html` and `/` — `private, no-store, no-cache, must-revalidate, no-transform` (prevents Cloudflare caching, returns `DYNAMIC`)

**Key nginx rule:** exact `location =` blocks always take priority over regex `location ~*` blocks.

### Data pipeline

1. **Fetcher container** (`fetcher.py`): polls ESPN public API (`site.api.espn.com/apis/site/v2/sports/soccer/fifa.world`) every 60s, writes four files to `wc-data` volume:
   - `data.json` — all matches with scores, status, minute, period
   - `scorers.json` — top scorers / Golden Boot
   - `match-details.json` — keyed by match ID → `{status, score{fullTime}, goals[], bookings[]}` (own goals, penalties, cards; bookings include `YELLOW`, `RED`, `YELLOW_RED`)
   - `group-winners.json` — keyed by group letter → `{first, second}` (only populated once all 6 group games FINISHED)
2. nginx serves from volume (live), falls back to baked copy for `data.json`/`scorers.json`; `match-details.json` and `group-winners.json` return 404 if not yet generated (frontend handles gracefully)

**`make deploy` uses `--force-recreate`** — all containers including the fetcher are restarted on every deploy, so `fetcher.py` changes take effect automatically.

**ESPN API notes:**
- No auth required
- `score` field is a string (`'2'`, not `2`) — `int()` conversion needed
- Scheduled matches return `score='0'` — fetcher guards with `is_started` check
- No `minute` field — only `status` is reliable (`IN_PLAY`, `PAUSED`, `FINISHED`, `TIMED`)
- `shortDisplayName` for Türkiye = `'Türkiye'`, Bosnia = `'Bosnia-Herz'` — both mapped in `API_NAME_MAP`
- `keyEvents` on summary endpoint: `type.type` = `"goal"` / `"own-goal"` / `"penalty"` / `"yellow-card"` / `"red-card"` / `"yellow-red-card"`
- Own goal `team` field = the scorer's own team (not the benefiting team) — side must be flipped in display
- `yellow-red-card` maps to `"YELLOW_RED"` in `match-details.json` (distinct from `"RED"`) — displayed as 🟧 in event card and live card
- `score.duration` in `data.json`: `"REGULAR"` / `"EXTRA_TIME"` / `"PENALTY_SHOOTOUT"` — used for AET/PSO badge on finished match rows
- `score.halfTime` in `data.json`: stored in `scoreMap` and used by `buildEventCard` to render HT separator with score at the break

### Traefik routing

- `worldcup.bergpb.dev` — Cloudflare-proxied → `web` entrypoint (HTTP port 80); serves the site via `worldcup@file`
- `worldcup2026.bergpb.dev` — 308 permanent redirect to `worldcup.bergpb.dev` via Traefik `redirectregex` middleware
- Cloudflare handles SSL termination; Traefik uses `web` (not `websecure`) for Cloudflare-proxied domains

---

## i18n system

Three languages: `en`, `pt`, `es`. Stored in `LANGS` object in each page. Saved to `localStorage('wc2026_lang')`.

- `data-i18n="key"` attributes on elements; `applyLang()` sets `innerHTML` from `LANGS[_lang][key]`
- `cycleLang()` rotates `en → pt → es`
- `teamName(n)` translates country names: `LANGS[_lang]?.teams?.[n] ?? n`
- Nav buttons translated via `['schedule','groups','knockout','scorers','feedback'].forEach(k => ...)` in `applyLang()`

### `LANGS_COMMON` (shared partial)

Injected by build.py from `_partials/langs.html` before each page's own `<script>`. Defines:
- `nav_*` keys (nav button labels in all 3 languages)
- `lbl_timezone` (timezone label)
- `teams` map in `pt` and `es` (country name translations)

Each page's `LANGS` uses spread to inherit: `en: { ...LANGS_COMMON.en, sub_page: '...', ... }`. Only page-specific keys live in the page source.

**When adding a new country:** add to `teams` map in `_partials/langs.html` for both `pt` and `es`.

**FLAGS lookup** uses country name as key (e.g. `'Brazil':'br'`). The API returns `Curaçao` (with accent) — the FLAGS map must have the accented version as a key.

---

## Footer

All pages use a standardized footer from `_partials/footer.html`:

```html
<div class="footer">
  <p id="footer-line1"></p>
  <p id="footer-line2"></p>
  <p class="footer-credits">
    <a href="https://buymeacoffee.com/coolcato">👋 Made by coolcato</a>
    / <a href="https://github.com/bergpb">✏️ Edited by bergpb</a>
  </p>
</div>
```

Each page's `applyLang()` populates `footer-line1` and `footer-line2` with page-specific content (timezone, source attribution, version span, etc.). The `<span id="version">vBUILD</span>` inside footer JS strings gets replaced by the Dockerfile `sed` at build time.

---

## JS architecture (index.html)

### Scope structure

- **Global scope**: `LANGS_COMMON`, `LANGS`, `_lang`, `teamName()`, `FLAGS`, `flagImg()`, `flagUrl()`, `normalise()`, `scoreMap`, `matchDetails`, `groupWinners`, `lastMatches`, `loadScores()`, `showToast()`, `updateLiveCard()`, `buildLiveCardEvents()`, `getMatchId()`, `buildEventCard()`, `positionEventCard()`, `applyGroupWinners()`
- **`render()` function**: inner `FLAGS` (duplicate), inner `flagUrl()` (do NOT remove — used internally by render)
- **IIFE**: page init, `applyLang()`, `restoreAndRender()`, event card listeners, changelog popup

**`flagUrl()` must exist at global scope** — the copy inside `render()` is not accessible to `updateLiveCard()`. Silent TypeError otherwise (caught by loadScores try/catch — always check console when debugging).

### Live scores flow

`loadScores()` fetches three files sequentially: `data.json` → `match-details.json` → `group-winners.json`. **`updateLiveCard(lastMatches)` is called after ALL three fetches** — if moved inside the `data.json` try block, `matchDetails` won't be populated yet and live card events won't show.

`scoreMap` includes ALL stages (not just GROUP_STAGE). Each entry has `id: m.id` — required by `getMatchId()` to look up match details. Also stores `duration` (`REGULAR`/`EXTRA_TIME`/`PENALTY_SHOOTOUT`) and `halfTime: {home, away}` from `data.json`, used by `getScore()` (AET/PSO badge) and `buildEventCard` (HT separator).

`cycleLang()` calls `updateLiveCard(lastMatches)` so translations update without a refetch.

### Match event card

`buildEventCard(teamsStr)` shows goals + cards on hover (desktop) / tap (mobile). Returns `null` when: hide-scores active, match not in scoreMap, no `matchDetails` entry, status TIMED, score null, or no events at all. Event listeners use `isTouchDevice = window.matchMedia('(hover: none)').matches`.

When `scoreMap` has `halfTime` data, events are split into 1st half (≤45') and 2nd half (>45') with an `HT X–Y` separator row between them (`.ev-ht-row`). Falls back to flat list if no halfTime. Card icons: ⚽ goal, 🟨 yellow (`YELLOW`), 🟧 second yellow (`YELLOW_RED`), 🟥 red (`RED`).

### Live card events

`buildLiveCardEvents(live)` appends goals (⚽ with OG/pen tags) and cards to each match row in the live card, split home/away. Shows 🟨 yellow (`YELLOW`), 🟧 second yellow (`YELLOW_RED`), and 🟥 red (`RED`) cards.

### Knockout group-winner replacement

`applyGroupWinners(teamsStr)` replaces `Win A`→winner, `2nd A`→runner-up using `groupWinners` dict (A–L letters only, not `Win M73` style). Called before `xlateTeams()` in the knockout render loop.

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
- Translates country names via `teamName()` with `teams:{}` map from `LANGS_COMMON`
- FLAGS lookup uses `s.team.shortName` — must match key in FLAGS exactly (including accents)
- CSS for scorers table lives in `styles.css` (not inline)

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

## groups.html

### Qualification badge engine

`calcGroupBadges(grp, teamNames, finishedResultsMap)` simulates all 3^N remaining fixture outcomes to determine if a team's finish position is mathematically guaranteed. Returns badge per team: `1` (gold, winner), `Q` (green, top-2), `2` (blue, runner-up), `E` (red, eliminated). Only triggers once all 4 teams have played ≥2 games. Capped at 100 scenarios.

**`GROUP_FIXTURES`** — array of all 72 group fixtures used by `getGroupFixtureStatus()`. Required; missing it crashes `render()`.

`calcStandings()` returns `{ groups, results, finishedResults, liveGroups }`:
- `results` — includes IN_PLAY/PAUSED provisional scores (for H2H tiebreaking in standings)
- `finishedResults` — FINISHED-only (passed to badge engine to avoid premature badges from provisional scores)

Badge legend (`#badge-legend`) below the standings note explains the four colours. Translated via `data-i18n` in all 3 languages.

---

## Personal branch customizations

### `HIDE_BMC = true`

Adds `hide-bmc` to `<body>`. Hides Buy Me a Coffee widgets, `#lnk-notify`, `#lnk-feedback`, `#lnk-madeby`, `#feedback-nav`.

### Domain

Live at `worldcup.bergpb.dev`. `<meta name="author">` is `bergpb`.

### `styles.css` cache busting

All pages: `<link rel="stylesheet" href="styles.css?vBUILD">`. Dockerfile `sed` replaces `vBUILD` with git hash at build time → forces fresh CSS on every deploy.

---

## Cloudflare caching

**Diagnosing:** `curl -sI https://worldcup.bergpb.dev/sw.js | grep cf-cache-status`
- `HIT` = Cloudflare serving cached copy → purge needed
- `BYPASS` or `DYNAMIC` = passing through to origin → safe

**Purging:** Cloudflare dashboard → zone → Caching → Purge Everything. Do this after any deploy that changes files previously served with long-lived cache headers.

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

Patching writes to the `wc-data` volume via a temp alpine container.

---

## Known quirks / gotchas

- `flagUrl()` must be at global scope — silent TypeError inside loadScores try/catch
- `loadScores()` try/catch swallows all errors from `updateLiveCard` — always check console
- `updateLiveCard` must be called AFTER `match-details.json` fetch, not inside the `data.json` try block — otherwise live card events are always one cycle stale
- API has no `minute` field — only `status`
- `CARD_LABELS` / `_cardLang` only exist on `feature/live-match-card`; `personal` uses `LANGS[_lang]` in `getScore()`
- `GROUP_FIXTURES` array must be defined in `groups.html` — missing it causes a `ReferenceError` in the badge engine that crashes `render()` entirely (blank groups page)
- After prod deploy, fetcher container is NOT restarted automatically — `docker restart worldcup-2026-static-fetcher-1` on `swarm` required for `fetcher.py` changes
- If new `location =` blocks added to `nginx.conf` while local dev containers are running, run `nginx -s reload` inside the dev container (or `make down && make up`) — otherwise the new JSON files return 404 and the frontend silently gets empty data
- Changelog popup re-shows for all users when `VERSION` constant in the changelog IIFE is bumped; update all three `changelog_body` strings in LANGS at the same time; use the short git hash of the feature commit as VERSION (not a date string)
- `score.duration` defaults to `"REGULAR"` for normal-time finishes — AET/PSO badge only shows when it's `"EXTRA_TIME"` or `"PENALTY_SHOOTOUT"`
- `make deploy` uses `--force-recreate` so all containers (including the fetcher) always restart with the latest code — no manual restart needed
- `#feedback-nav` ID on the feedback nav in `index.html` — CSS hide rule depends on this exact ID
- Curaçao in the ESPN API returns as `"Curaçao"` (with accent) — `API_NAME_MAP` maps it to `'Curacao'` for FLAGS lookup
- ESPN returns `"Türkiye"` (with umlaut) and `"Bosnia-Herz"` as shortDisplayName — both must be in `API_NAME_MAP` in all three pages (`index.html`, `groups.html`, `bracket.html`)
- `localhost` in busybox wget resolves as IPv6 → healthcheck must use `127.0.0.1`
- Cloudflare-proxied services use `web` entrypoint; DNS-only use `websecure`
- `Cache-Control: private` prevents CF caching (`DYNAMIC`); `no-store` returns `BYPASS`; `public, max-age=...` returns `HIT`
- Traefik redirectregex replacements in Ansible labels use `${1}` (not `$${1}`) — `$$` is Docker Compose syntax, not needed in Ansible `docker_swarm_service` labels
- When adding a new HTML page: add to `PAGES` array in `build.py`, add markers to source file, update Dockerfile if needed, add nav translation keys to `_partials/langs.html`
- Source HTML files are committed with **empty markers** — `dist/` is gitignored. Never commit populated marker content.
