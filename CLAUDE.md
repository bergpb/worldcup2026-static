# worldcup2026-static — CLAUDE.md

Static HTML/CSS/JS site showing all 104 FIFA World Cup 2026 matches with live scores, group standings, knockout bracket, and top scorers. Has a partial-based build step (`python3 scripts/build.py`) that assembles pages into `dist/`.

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

### `scripts/build.py`

Reads source files (with empty markers), injects partials, writes fully-assembled HTML to `dist/`. Run before deploying or testing locally. Lives in `scripts/` alongside `fetcher.py`, `watch.py`, and `check_empty_markers.py`; all path handling inside these scripts is relative to the **current working directory** (repo root), not the script's own location — always invoke them from the repo root (every Makefile target, Docker Compose service, and CI/pre-commit step already does this).

```bash
python3 scripts/build.py           # build → dist/
python3 scripts/build.py --check   # exit 1 if dist/ is stale (CI safety)
python3 scripts/build.py --strip   # empty all markers in source files (run before committing if needed)
```

`dist/` is gitignored and self-contained (HTML + CSS + icons + static assets).

### `_partials/`

| File | Injected into |
|---|---|
| `head.html` | All pages — `<!DOCTYPE html>` through shared `<head>` tags; uses `{{PAGE_TITLE}}`, `{{PAGE_DESCRIPTION}}`, `{{PAGE_CANONICAL}}` |
| `nav.html` | All pages — nav buttons; `scripts/build.py` adds `active` class for the current page |
| `langs.html` | All pages — `<script>` block defining `LANGS_COMMON` (shared nav/timezone/teams translations) |
| `tz-options.html` | index, groups, bracket — `<option>` list for timezone selector |
| `common.js` | All pages — `cycleLang()`, `applyLang()`, `langBtnHTML()`, `shareApp()`, localStorage lang persistence |
| `footer.html` | All pages — `<div class="footer">` with `#footer-line1` and `#footer-line2`; includes credits |
| `jsonld.html` | index only — JSON-LD structured data (all 104 match events), injected before `</body>` |

**Adding a new HTML page:** add it to the `PAGES` array in `scripts/build.py` with `title`, `description`, `canonical`, and `nav` key; add `<!-- partial:X --><!-- /partial:X -->` markers; update the Dockerfile if needed.

---

## Makefile commands

```bash
make build         # assemble partials → dist/
make check         # verify dist/ is up-to-date (exits non-zero if stale)
make test          # run JS (npm test) + Python (unittest) test suites
make install-hooks # install the pre-commit git hook (run once per clone)
make deploy        # build + rsync to $(PROD_HOST) + rebuild prod container + force-recreate all (fetcher included)
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

`PROD_HOST` defaults to `swarm` (from `~/.ssh/config`, LAN-only) but is overridable — CI passes `PROD_HOST=bergpb@<tailscale-ip>` since GitHub-hosted runners aren't on the LAN (see CI/CD section below).

**Manual `make deploy` runs still require asking first** — show what changed, then wait for go-ahead. This doesn't apply to the CI pipeline, which auto-deploys on every push to `personal` once tests pass — that's the explicitly agreed-upon automated replacement for this path.

---

## Testing & pre-commit hooks

`tests/` holds two independent suites, both exercising real logic extracted from the page source (not reimplementations):

- **JS** (`tests/*.test.js`, run via `node --test tests/`): uses `tests/helpers/extract.js` to pull named `function`/`const` declarations out of `index.html` / `groups.html` / `bracket.html` / `_partials/common.js` and evaluate them in a `node:vm` sandbox — no DOM, no headless browser. Covers `normalise()`/`FLAGS` coverage, `calcGroupBadges()`/`sortTeams()`, `getScore()` (AET/PSO/live/PAUSED/knockout-by-id/name-alias logic), `scoreSuffix()`, and the own-goal attribution fix in `buildLiveCardEvents`.
  - `vm.runInContext` gotcha: top-level `const`/`function` don't attach to the sandbox object the way `var` does — `extract.js` appends explicit `globalThis.NAME = NAME;` lines to work around it.
  - Use plain `node:assert` (not `node:assert/strict`) — `deepStrictEqual` false-fails comparing vm-sandbox-created objects/arrays against plain literals (cross-realm prototype mismatch).
- **Python** (`tests/test_fetcher.py`, run via `python3 -m unittest discover -s tests`): imports `scripts/fetcher.py` directly (via `sys.path.insert(0, '../scripts')`), covers `STATUS_MAP`/`DURATION_MAP`/`PERIOD_MAP` (including regression tests for real incidents — AET, `STATUS_OVERTIME`, `STATUS_HALFTIME_ET`), `_display()` aliasing, `parse_event_clock()`, `normalize_date()`, `build_detail_entry()`.

### Pre-commit hook

Uses the [pre-commit](https://pre-commit.com/) framework (`.pre-commit-config.yaml`, local hooks — no external repo dependencies). Runs on every `git commit`:

1. `python3 scripts/build.py` — build must succeed
2. `python3 scripts/check_empty_markers.py` — committed source files must keep markers empty (never commit populated `dist/`-style content)
3. `npm test --silent` — JS suite
4. `python3 -m unittest discover -s tests` — Python suite

**Setup per clone:** `pip install pre-commit && make install-hooks` (the target runs `pre-commit install`, writing to `.git/hooks/pre-commit`). Requires Node (`.tool-versions` pins `nodejs 20.11.1` for asdf) and Python 3.12+.

Run manually without committing: `pre-commit run --all-files`.

CI (`build-check` job below) runs the exact same `pre-commit run --all-files` — local and CI checks can't drift out of sync.

---

## Infrastructure

### Docker Compose (`docker-compose.yml`)

Four services sharing the named volume `wc-data`:

- **`dev`** (profile: `dev`): `nginx:alpine`, mounts `dist/` + `nginx/dev.conf` + `wc-data:/data:ro`; port `8080`
- **`builder`** (profile: `dev`): `python:3.12-alpine`, runs `scripts/watch.py` — watches source files, rebuilds to `dist/`, serves live-reload SSE on port `35729`
- **`fetcher`** (profile: `dev` + `prod`): `alpine`, polls API every 60s, writes `data.json` + `scorers.json` to `wc-data:/data`
- **`prod`** (profile: `prod`): built from `Dockerfile`, mounts `wc-data:/data:ro`; port `8081`

`make up` starts all three dev services. The browser auto-reloads on any source file change via the builder's SSE server at `:35729`.

### Dockerfile

```dockerfile
FROM nginx:alpine
ARG BUILD_VERSION=dev
COPY nginx/prod.conf /etc/nginx/conf.d/default.conf
COPY dist/ /usr/share/nginx/html/
RUN find /usr/share/nginx/html -name "*.html" -exec sed -i "s/vBUILD/v${BUILD_VERSION}/g" {} +
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
```

**`127.0.0.1` not `localhost`** in healthcheck — busybox wget resolves `localhost` as IPv6 and fails.

**Build version injection:** all `*.html` files in `dist/` have `vBUILD` replaced with the git short hash at build time. Used for cache-busting `styles.css?vBUILD`.

### nginx (`nginx/prod.conf` and `nginx/dev.conf`)

Key rules:
- `data.json` and `scorers.json` — served from `/data` volume first, baked image copy as fallback; `no-cache`
- `sw.js` and `styles.css` — exact-match `location =` blocks with `no-cache`
- `*.css|js|png...` — `public, max-age=31536000, immutable`
- `*.html` and `/` — `private, no-store, no-cache, must-revalidate, no-transform` (prevents Cloudflare caching, returns `DYNAMIC`)

**Key nginx rule:** exact `location =` blocks always take priority over regex `location ~*` blocks.

### Data pipeline

1. **Fetcher container** (`scripts/fetcher.py`): polls ESPN public API (`site.api.espn.com/apis/site/v2/sports/soccer/fifa.world`) every 60s, writes four files to `wc-data` volume:
   - `data.json` — all matches with scores, status, minute, period
   - `scorers.json` — top scorers / Golden Boot
   - `match-details.json` — keyed by match ID → `{status, score{fullTime}, goals[], bookings[]}` (own goals, penalties, cards; bookings include `YELLOW`, `RED`, `YELLOW_RED`)
   - `group-winners.json` — keyed by group letter → `{first, second}` (only populated once all 6 group games FINISHED)
2. nginx serves from volume (live), falls back to baked copy for `data.json`/`scorers.json`; `match-details.json` and `group-winners.json` return 404 if not yet generated (frontend handles gracefully)

**`make deploy` uses `--force-recreate`** — all containers including the fetcher are restarted on every deploy, so `scripts/fetcher.py` changes take effect automatically.

**ESPN API notes:**
- No auth required
- `score` field is a string (`'2'`, not `2`) — `int()` conversion needed
- Scheduled matches return `score='0'` — fetcher guards with `is_started` check
- No `minute` field — only `status` is reliable (`IN_PLAY`, `PAUSED`, `FINISHED`, `TIMED`)
- `shortDisplayName` for Türkiye = `'Türkiye'`, Bosnia = `'Bosnia-Herz'` — both mapped in `API_NAME_MAP`
- `keyEvents` on summary endpoint: `type.type` = `"goal"` / `"own-goal"` / `"penalty"` / `"yellow-card"` / `"red-card"` / `"yellow-red-card"`
- Own goal `team` field is already the **benefiting** team (verified against real match: Argentina 3-2 Cape Verde, OG scored by a Cape Verde player raised Argentina's tally and `team.name` read `"Argentina"`) — do NOT flip side in display; a previous version of this doc had it backwards, which caused the OG to render under the wrong team's column
- `yellow-red-card` maps to `"YELLOW_RED"` in `match-details.json` (distinct from `"RED"`) — displayed as 🟧 in event card and live card
- `score.duration` in `data.json`: `"REGULAR"` / `"EXTRA_TIME"` / `"PENALTY_SHOOTOUT"` — used for AET/PSO badge on finished match rows
- `score.halfTime` in `data.json`: stored in `scoreMap` and used by `buildEventCard` to render HT separator with score at the break

### Traefik routing

- `worldcup.bergpb.dev` — Cloudflare-proxied → `web` entrypoint (HTTP port 80); serves the site via `worldcup@file`
- `worldcup2026.bergpb.dev` — 308 permanent redirect to `worldcup.bergpb.dev` via Traefik `redirectregex` middleware
- Cloudflare handles SSL termination; Traefik uses `web` (not `websecure`) for Cloudflare-proxied domains

---

## CI/CD (`.github/workflows/build-check.yml`)

Two jobs, triggered on push to `personal` and on pull requests:

### `build-check`

Checks out the repo, sets up Python 3.12 + Node 20, installs `pre-commit`, then runs `pre-commit run --all-files` — the exact same hooks defined in `.pre-commit-config.yaml` (build, empty-marker check, JS tests, Python tests). Local and CI checks share one definition, so they can't drift.

### `deploy`

Runs only `if: github.ref == 'refs/heads/personal' && github.event_name == 'push'` (never on PRs, never on other branches), and only `needs: build-check` (won't run if tests fail).

1. **Connect to tailnet** — `tailscale/github-action@v3` joins the GitHub-hosted runner to the tailnet as an ephemeral, tagged (`tag:ci`) node, authenticated via a Tailscale OAuth client (`secrets.TS_OAUTH_CLIENT_ID` / `TS_OAUTH_CLIENT_SECRET`). This is what lets a runner with no prior relationship to the network reach `swarm-prod` directly — no self-hosted runner or public-facing webhook needed.
2. **Set up deploy SSH key** — decodes `secrets.SWARM_SSH_PRIVATE_KEY_B64` (base64-encoded — see gotcha below) into `~/.ssh/id_ed25519`, then `ssh-keyscan`s `secrets.SWARM_TAILSCALE_IP`.
3. **Deploy to swarm-prod** — `make deploy PROD_HOST=bergpb@${{ secrets.SWARM_TAILSCALE_IP }}`, the same `make deploy` used for manual deploys, just pointed at the tailnet IP instead of the LAN hostname.

**Required GitHub repo secrets** (Settings → Secrets and variables → Actions):
- `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_CLIENT_SECRET` — Tailscale OAuth client scoped to create devices tagged `tag:ci`
- `SWARM_SSH_PRIVATE_KEY_B64` — base64 of a **dedicated** deploy-only SSH keypair (never reuse a personal key) authorized in `swarm-prod`'s `~/.ssh/authorized_keys`
- `SWARM_TAILSCALE_IP` — swarm-prod's tailnet IP; kept as a secret rather than hardcoded in the workflow, by request

**Tailscale OAuth client setup — the non-obvious part:** the client needs scopes across *two separate categories*, both required:
- `Devices → Core → Write`, with `tag:ci` added under that scope's own Tags picker (governs managing devices)
- `Keys → Auth Keys → Write` (governs the `POST /tailnet/-/keys` call the GitHub Action actually uses to provision the ephemeral node) — **this one is easy to miss**; having only Devices scope produces a `403: "calling actor does not have enough permissions to perform this function"` on every `tailscale up` attempt inside the action, silently, because the action's retry loop doesn't propagate that failure as the step's exit code (the step shows green even though the tailnet join never succeeded). If `deploy` fails at "Set up deploy SSH key" (an unrelated-looking step) with no real error, check the "Connect to tailnet" step's raw log for repeated `Attempt N... 403` lines — that's the real failure, one step upstream.
- The tailnet ACL also needs `tag:ci` defined under `tagOwners` (e.g. `"tagOwners": {"tag:ci": ["autogroup:admin"]}`).
- To debug OAuth scope issues directly (bypassing the action's swallowed errors): exchange the client credentials for an access token (`POST https://api.tailscale.com/api/v2/oauth/token`), then attempt the same key-creation call the action makes (`POST https://api.tailscale.com/api/v2/tailnet/-/keys`) — Tailscale's own error message is more specific than what surfaces in the Action log.

**Never paste private key or secret content back into chat/logs** — view it in your own terminal and copy directly into the target secret UI. (This project had a real incident: a private key pasted into a chat transcript required immediate rotation — dedicated deploy keys make this low-blast-radius, but still requires generating a fresh keypair and updating `authorized_keys` + the GitHub secret.)

---

## i18n system

Three languages: `en`, `pt`, `es`. Stored in `LANGS` object in each page. Saved to `localStorage('wc2026_lang')`.

- `data-i18n="key"` attributes on elements; `applyLang()` sets `innerHTML` from `LANGS[_lang][key]`
- `cycleLang()` rotates `en → pt → es`
- `teamName(n)` translates country names: `LANGS[_lang]?.teams?.[n] ?? n`
- Nav buttons translated via `['schedule','groups','knockout','scorers','feedback'].forEach(k => ...)` in `applyLang()`

### `LANGS_COMMON` (shared partial)

Injected by `scripts/build.py` from `_partials/langs.html` before each page's own `<script>`. Defines:
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
- If new `location =` blocks added to `nginx/dev.conf` while local dev containers are running, run `nginx -s reload` inside the dev container (or `make down && make up`) — otherwise the new JSON files return 404 and the frontend silently gets empty data
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
- When adding a new HTML page: add to `PAGES` array in `scripts/build.py`, add markers to source file, update Dockerfile if needed, add nav translation keys to `_partials/langs.html`
- Python scripts (`build.py`, `fetcher.py`, `watch.py`, `check_empty_markers.py`) live in `scripts/` and resolve all paths relative to the **repo root** (cwd), not their own file location — must always be invoked from the repo root (`python3 scripts/build.py`, not `cd scripts && python3 build.py`)
- Source HTML files are committed with **empty markers** — `dist/` is gitignored. Never commit populated marker content.
- Multi-line secrets (e.g. an SSH private key) pasted into a GitHub Actions text-box secret can suffer newline corruption — store as base64 (`base64 -w0 keyfile`) and decode in the workflow step instead
- Tailscale OAuth client for CI needs BOTH `Devices → Core → Write` (with `tag:ci` under its Tags picker) AND `Keys → Auth Keys → Write` — missing the latter causes a silent `403` inside `tailscale/github-action` that doesn't fail the step (see CI/CD section above)
