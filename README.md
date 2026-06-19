# World Cup 2026 — Live Schedule & Scores

A lightweight static site tracking all 104 matches of the 2026 FIFA World Cup with live scores, group standings, and the knockout bracket — all in your local timezone. No framework, no build step, no ads.

**Live at:** https://kingdoggydog.github.io/worldcup2026/

## Pages

| Page | Description |
|---|---|
| `index.html` | Full match schedule with live scores, timezone picker, and team highlight filter |
| `groups.html` | Live group standings for all 12 groups with FIFA tiebreaker logic |
| `bracket.html` | Knockout bracket from Round of 32 through the Final |
| `feedback.html` | Feedback form |

## How it works

Data flows from [football-data.org](https://www.football-data.org/) through a Cloudflare Worker proxy into `data.json`, which is committed directly to the repo by a GitHub Actions cron job every 5 minutes. Each page fetches `data.json` at load time and re-polls every 60 seconds for live updates — no server required.

```
football-data.org API
       ↓
Cloudflare Worker (proxy / auth)
       ↓
GitHub Actions (every 5 min) → commits data.json
       ↓
GitHub Pages (static hosting)
       ↓
Browser fetches data.json on load + every 60s
```

## Features

- Live scores updated every 5 minutes via CI
- Automatic timezone detection with manual override (preference saved to `localStorage`)
- Team highlight filter to track your favourite nation across all matches
- Dark/light (print) mode toggle
- Group standings computed client-side with correct FIFA tiebreaker rules
- Full knockout bracket rendered from live data
- Mobile-friendly, no dependencies beyond Google Fonts

## Project structure

```
worldcup2026-static/
├── index.html          # Schedule + live scores
├── groups.html         # Group standings
├── bracket.html        # Knockout bracket
├── feedback.html       # Feedback form
├── data.json           # Match data (auto-updated by CI)
├── sitemap.xml
├── Dockerfile          # Production image (nginx + copied files)
├── docker-compose.yml  # Dev and prod service definitions
├── nginx.conf          # nginx config (caching, gzip, routing)
└── .github/
    └── workflows/
        └── fetch-scores.yml   # Cron job: fetches & commits data.json
```

## Running locally

**Without Docker** — no build step needed:

```bash
# Python
python3 -m http.server 8080

# Node
npx serve .
```

**With Docker** — files are mounted as a volume so any edit is reflected immediately without rebuilding:

```bash
docker compose --profile dev up
```

Open http://localhost:8080.

## Running in production

The production image copies the static files into an nginx:alpine image (~25 MB). Build and run:

```bash
# Build
docker build -t worldcup2026 .

# Run
docker compose --profile prod up -d
```

Or using plain Docker:

```bash
docker build -t worldcup2026 .
docker run -d -p 80:80 --restart unless-stopped worldcup2026
```

`data.json` is baked into the image at build time. To refresh scores, rebuild the image (or in production just let GitHub Pages serve it directly — the Docker setup is mainly for self-hosting).

## Data pipeline

The GitHub Actions workflow (`.github/workflows/fetch-scores.yml`) runs on a `*/5 * * * *` cron schedule. It:

1. Calls the Cloudflare Worker proxy to fetch all 104 matches
2. Saves the response to `data.json`
3. Commits and pushes only if the file changed

The `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` env var ensures the runner uses a current Node version.

## License

MIT
