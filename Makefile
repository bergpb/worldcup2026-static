PROD_HOST   = swarm
PROD_DIR    = ~/worldcup-2026-static
VOLUME      = worldcup2026-static_wc-data
DEV_NGINX   = worldcup2026-static-dev-1
BUILD_TS    = $(shell date +%Y%m%d%H%M%S)
BUILD_HASH  = $(shell git rev-parse --short HEAD)

.PHONY: build check test install-hooks deploy sync up down logs fetcher-stop fetcher-start patch-ht patch-live restore

## Assemble partials into all pages
build:
	python3 build.py

## Verify pages are up-to-date with partials (exits non-zero if stale)
check:
	python3 build.py --check

## Run JS + Python unit tests
test:
	npm test
	python3 -m unittest discover -s tests

## Point git at the checked-in hooks (run once per clone)
install-hooks:
	git config core.hooksPath .githooks
	@echo "pre-commit hook installed — runs build + tests before every commit"

## Deploy to production (rsync + inject git hash version + bump SW cache + rebuild)
deploy: build
	rsync -av --exclude='data.json' --exclude='scorers.json' --exclude='.git' ./ $(PROD_HOST):$(PROD_DIR)/
	ssh $(PROD_HOST) "cd $(PROD_DIR) && docker compose --profile prod build --build-arg BUILD_VERSION=$(BUILD_HASH) prod && docker compose --profile prod up -d --force-recreate"

## Start local dev server
up:
	docker compose --profile dev up -d

## Stop local dev server
down:
	docker compose --profile dev down

### Logs for dev env
logs:
	docker compose --profile dev logs -f

## Stop fetcher (freeze live data for testing)
fetcher-stop:
	docker compose --profile dev stop fetcher

## Start fetcher (restore live data)
fetcher-start:
	docker compose --profile dev start fetcher

## Restore live data (restart fetcher)
restore:
	docker compose --profile dev start fetcher
	@echo "Fetcher restarted — live data will refresh within 5 min"
