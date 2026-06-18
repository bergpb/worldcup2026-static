PROD_HOST   = swarm
PROD_DIR    = ~/worldcup-2026-static
VOLUME      = worldcup2026-static_wc-data
DEV_NGINX   = worldcup2026-static-dev-1
BUILD_TS    = $(shell date +%Y%m%d%H%M%S)
BUILD_HASH  = $(shell git rev-parse --short HEAD)

.PHONY: build check deploy sync dev-up dev-down fetcher-stop fetcher-start patch-ht patch-live restore

## Assemble partials into all pages
build:
	node build.js

## Verify pages are up-to-date with partials (exits non-zero if stale)
check:
	node build.js --check

## Deploy to production (rsync + inject git hash version + bump SW cache + rebuild)
deploy: build
	rsync -av --exclude='data.json' --exclude='scorers.json' --exclude='.git' ./ $(PROD_HOST):$(PROD_DIR)/
	ssh $(PROD_HOST) "cd $(PROD_DIR) && docker compose --profile prod build --build-arg BUILD_VERSION=$(BUILD_HASH) prod && docker compose --profile prod up -d"

## Sync files to prod without rebuilding
sync:
	rsync -av --exclude='data.json' --exclude='scorers.json' --exclude='.git' ./ $(PROD_HOST):$(PROD_DIR)/

## Start local dev server
up:
	docker compose --profile dev up -d

## Stop local dev server
down:
	docker compose --profile dev down

## Stop fetcher (freeze live data for testing)
fetcher-stop:
	docker compose --profile dev stop fetcher

## Start fetcher (restore live data)
fetcher-start:
	docker compose --profile dev start fetcher

## Patch data: set first upcoming/finished match to PAUSED (half-time) for local testing
patch-ht:
	@docker compose --profile dev stop fetcher
	@docker cp $(DEV_NGINX):/data/data.json /tmp/data_vol.json
	@python3 -c "\
import json; \
d = json.load(open('/tmp/data_vol.json')); \
m = next((m for m in d['matches'] if m['homeTeam']['name'] == 'Netherlands' and m['awayTeam']['name'] == 'Japan'), d['matches'][1]); \
m['status'] = 'PAUSED'; \
m['score']['fullTime'] = {'home': 2, 'away': 1}; \
json.dump(d, open('/tmp/data_vol.json','w')); \
print(f\"Patched: {m['homeTeam']['name']} vs {m['awayTeam']['name']} → PAUSED 2-1\") \
"
	@docker run --rm -v $(VOLUME):/data -v /tmp/data_vol.json:/tmp/data_vol.json alpine cp /tmp/data_vol.json /data/data.json
	@echo "Done — fetcher stopped, check http://192.168.6.110:8080"

## Patch data: set a match to IN_PLAY for local testing
patch-live:
	@docker compose --profile dev stop fetcher
	@docker cp $(DEV_NGINX):/data/data.json /tmp/data_vol.json
	@python3 -c "\
import json; \
d = json.load(open('/tmp/data_vol.json')); \
m = next((m for m in d['matches'] if m['homeTeam']['name'] == 'Netherlands' and m['awayTeam']['name'] == 'Japan'), d['matches'][1]); \
m['status'] = 'IN_PLAY'; \
m['score']['fullTime'] = {'home': 1, 'away': 0}; \
json.dump(d, open('/tmp/data_vol.json','w')); \
print(f\"Patched: {m['homeTeam']['name']} vs {m['awayTeam']['name']} → IN_PLAY 1-0\") \
"
	@docker run --rm -v $(VOLUME):/data -v /tmp/data_vol.json:/tmp/data_vol.json alpine cp /tmp/data_vol.json /data/data.json
	@echo "Done — fetcher stopped, check http://192.168.6.110:8080"

## Patch score change: simulate a goal (IN_PLAY 2-0) to test goal flash animation
patch-goal:
	@docker cp $(DEV_NGINX):/data/data.json /tmp/data_vol.json
	@python3 -c "\
import json; \
d = json.load(open('/tmp/data_vol.json')); \
m = next((m for m in d['matches'] if m['homeTeam']['name'] == 'Netherlands' and m['awayTeam']['name'] == 'Japan'), d['matches'][1]); \
m['status'] = 'IN_PLAY'; \
m['score']['fullTime'] = {'home': 2, 'away': 0}; \
json.dump(d, open('/tmp/data_vol.json','w')); \
print(f\"Patched: {m['homeTeam']['name']} vs {m['awayTeam']['name']} → IN_PLAY 2-0\") \
"
	@docker run --rm -v $(VOLUME):/data -v /tmp/data_vol.json:/tmp/data_vol.json alpine cp /tmp/data_vol.json /data/data.json
	@echo "Done — pull to refresh on the page to see the goal flash"

## Restore live data (restart fetcher)
restore:
	docker compose --profile dev start fetcher
	@echo "Fetcher restarted — live data will refresh within 5 min"
