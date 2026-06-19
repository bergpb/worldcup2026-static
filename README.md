# World Cup 2026 — Live Schedule & Scores

A lightweight static site tracking all 104 matches of the 2026 FIFA World Cup with live scores, group standings, knockout bracket, and top scorers — all in your local timezone. No framework, no ads.

**Live at:** https://worldcup.bergpb.dev  
**Redirects:** `worldcup2026.bergpb.dev` → 308 → `worldcup.bergpb.dev`

---

## Pages

| Page | Description |
|---|---|
| `index.html` | Full match schedule with live scores, timezone picker, and team highlight filter |
| `groups.html` | Live group standings for all 12 groups with FIFA tiebreaker logic |
| `bracket.html` | Knockout bracket from Round of 32 through the Final |
| `scorers.html` | Top scorers / Golden Boot race |

---

## How it works

Data is fetched from the ESPN public API (no auth required) by a Docker container running `fetcher.py`. It writes `data.json` and `scorers.json` to a shared Docker volume every 120 seconds. nginx serves the live files from the volume, falling back to the baked copy in the image.

```
ESPN public API
      ↓
fetcher.py (Docker, every 120s) → /data/data.json + scorers.json
      ↓
nginx (volume-first, baked fallback)
      ↓
Browser fetches data.json on load + re-polls every 60s
```

---

## Features

- Live scores updated every 2 minutes via ESPN API
- Automatic timezone detection with manual override (saved to `localStorage`)
- Team highlight filter to follow your nation across all matches
- i18n: English, Portuguese, Spanish (cycle with the language button)
- Group standings computed client-side with correct FIFA tiebreaker rules
- Full knockout bracket rendered from live data
- Top scorers / Golden Boot table
- Mobile-friendly, no JS framework

---

## Project structure

```
worldcup2026-static/
├── index.html          # Schedule + live scores (source, markers only)
├── groups.html         # Group standings (source)
├── bracket.html        # Knockout bracket (source)
├── scorers.html        # Top scorers (source)
├── styles.css          # Consolidated CSS for all pages
├── _partials/          # Shared HTML/JS fragments injected by build.py
├── build.py            # Assembles partials → dist/
├── watch.py            # Dev watcher — rebuilds on change + SSE live reload
├── fetcher.py          # Polls ESPN API, writes data.json + scorers.json
├── dist/               # Built output (gitignored) — served by nginx
├── nginx.conf          # Dev nginx config
├── nginx/default.conf  # Prod nginx config
├── Dockerfile          # Production image (nginx:alpine)
├── docker-compose.yml  # Dev and prod service definitions
├── Makefile            # Common commands
└── sitemap.xml
```

---

## Build system

Source HTML files contain only empty `<!-- partial:name --><!-- /partial:name -->` markers. `build.py` injects shared partials (head, nav, footer, langs, etc.) and writes assembled pages to `dist/`.

```bash
python3 build.py           # build → dist/
python3 build.py --check   # exit 1 if dist/ is stale
python3 build.py --strip   # empty all markers in source files (before committing)
```

Or via Make:

```bash
make build   # python3 build.py
make check   # python3 build.py --check
```

---

## Running locally

```bash
make up     # start nginx + builder (live reload) + fetcher
make down   # stop everything
make logs   # follow dev logs
```

- Site: `http://localhost:8080`
- Live reload on file save via SSE at `:35729`
- Works from any machine on the network — live reload uses `location.hostname`

### Docker services (dev profile)

| Service | Image | Role |
|---|---|---|
| `dev` | `nginx:alpine` | Serves `dist/` on port 8080 |
| `builder` | `python:3.12-alpine` | Runs `watch.py` — rebuilds on change, SSE reload on `:35729` |
| `fetcher` | `python:3.12-alpine` | Polls ESPN every 120s, writes to `wc-data` volume |

---

## Running in production

```bash
make deploy   # build + rsync to swarm + rebuild prod container
```

The prod image (`Dockerfile`) copies `dist/` into `nginx:alpine`. At build time, all `vBUILD` placeholders in HTML are replaced with the git short hash for CSS cache-busting.

The `fetcher` service also runs in the prod profile, keeping `data.json` and `scorers.json` live on the `wc-data` volume.

---

## License

MIT
