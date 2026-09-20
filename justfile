# Cartulary — common developer tasks.
#
#   just              list every recipe
#   just install      first-time setup (pnpm workspace + backend venv)
#   just test         backend tests + type checks, as CI runs them
#
# Docker recipes drive docker compose; everything else runs on the host.
# Host-side backend recipes talk to the Postgres and Redis that compose
# publishes on localhost, so `just up` first (or point DATABASE_URL elsewhere).

set shell := ["bash", "-uc"]
set positional-arguments := true

root     := justfile_directory()
backend  := root / "apps/backend"
web      := root / "apps/web"
mobile   := root / "apps/mobile"
shared   := root / "packages/shared"
venv     := env_var_or_default("CARTULARY_VENV", backend / ".venv")
py       := venv / "bin/python"
compose  := "docker compose"
compose_prod := "docker compose -f docker-compose.prod.yml"

# Prelude for host-side backend recipes: read the repo-root .env (the backend's own
# lookup is cwd-relative, and apps/backend has no .env), then default the connection
# URLs to what compose publishes on localhost. Anything already exported wins.
#
# The test recipes deliberately skip this — they run on the ambient environment, the
# way CI does, so a local .env cannot change what the suite does.
load_env := 'set -a; [ -f "' + justfile_directory() + '/.env" ] && . "' + justfile_directory() + '/.env"; set +a; ' + \
    ': "${DATABASE_URL:=postgresql://cartulary:${DB_PASSWORD:-changeme}@localhost:5432/cartulary}"; ' + \
    ': "${REDIS_URL:=redis://localhost:6379/0}"; ' + \
    ': "${CELERY_BROKER_URL:=$REDIS_URL}"; ' + \
    ': "${CELERY_RESULT_BACKEND:=$REDIS_URL}"; ' + \
    'export DATABASE_URL REDIS_URL CELERY_BROKER_URL CELERY_RESULT_BACKEND'

[private]
default:
    @just --list --unsorted

# Fail early with a useful message when the backend venv is missing.
[private]
venv-check:
    @test -x "{{ py }}" || { echo "No backend virtualenv at {{ venv }}. Run: just install-py" >&2; exit 1; }

# ─── Setup ────────────────────────────────────────────────────────────────────

# Install everything: JS workspace, shared build, backend venv
[group('setup')]
install: install-js build-shared install-py
    @echo "✅ Ready. Next: just up (Docker) or just dev (host)"

# Install the pnpm workspace
[group('setup')]
install-js:
    pnpm install

# Create apps/backend/.venv and install Python dependencies
[group('setup')]
install-py:
    test -d "{{ venv }}" || python3 -m venv "{{ venv }}"
    "{{ py }}" -m pip install --upgrade pip
    "{{ py }}" -m pip install -r "{{ backend }}/requirements.txt"

# Copy .env.example to .env if you don't have one yet
[group('setup')]
env:
    @test -f "{{ root }}/.env" && echo ".env already exists — leaving it alone" || cp "{{ root }}/.env.example" "{{ root }}/.env"

# ─── Dev servers ──────────────────────────────────────────────────────────────

# Run every dev server via Turborepo
[group('dev')]
dev:
    pnpm dev

# Vite dev server for the web app (http://localhost:8080)
[group('dev')]
dev-web:
    pnpm --filter @cartulary/web dev

# Rebuild the shared package on every change
[group('dev')]
dev-shared:
    pnpm --filter @cartulary/shared dev

# uvicorn with reload on http://localhost:8000
[group('dev')]
dev-backend: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000

# Celery worker (host-side)
[group('dev')]
worker *args: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/celery" -A app.tasks.celery_app worker --loglevel=info "$@"

# Celery beat scheduler (host-side)
[group('dev')]
beat *args: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/celery" -A app.tasks.celery_app beat --loglevel=info "$@"

# Import-directory watcher worker
[group('dev')]
watch-directory: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ py }}" run_directory_watcher.py

# IMAP mailbox watcher worker
[group('dev')]
watch-imap: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ py }}" run_imap_watcher.py

# Expo dev server; extra args pass through, e.g. just mobile --dev-client
[group('mobile')]
mobile *args:
    pnpm --filter @cartulary/mobile start "$@"

# Run the mobile app on the iOS simulator
[group('mobile')]
ios:
    pnpm --filter @cartulary/mobile ios

# Run the mobile app on an Android emulator
[group('mobile')]
android:
    pnpm --filter @cartulary/mobile android

# Run the mobile app in a browser (limited functionality)
[group('mobile')]
mobile-web:
    pnpm --filter @cartulary/mobile web

# Restart Expo with a cleared cache
[group('mobile')]
mobile-clean:
    pnpm --filter @cartulary/mobile clean

# ─── Build ────────────────────────────────────────────────────────────────────

# Build every workspace package
[group('build')]
build:
    pnpm build

# Build @cartulary/shared (web and mobile both depend on it)
[group('build')]
build-shared:
    pnpm --filter @cartulary/shared build

# Type-check and build the web app
[group('build')]
build-web: build-shared
    pnpm --filter @cartulary/web build

# Serve the built web app
[group('build')]
preview:
    pnpm --filter @cartulary/web preview

# ─── Test & check ─────────────────────────────────────────────────────────────

# What CI gates on: backend tests plus the web type-check
[group('test')]
test: test-backend type-check-web
    @echo "✅ All checks passed"

# pytest; extra args pass through, e.g. just test-backend -k ocr
[group('test')]
test-backend *args: venv-check
    cd "{{ backend }}" && "{{ venv }}/bin/pytest" -v "$@"

# pytest with a coverage report over app/
[group('test')]
test-cov *args: venv-check
    cd "{{ backend }}" && "{{ venv }}/bin/pytest" --cov=app --cov-report=term-missing "$@"

# Contract tests against real model providers (needs Ollama/API keys)
[group('test')]
test-live *args: venv-check
    cd "{{ backend }}" && "{{ venv }}/bin/pytest" -v --live -m live "$@"

# Playwright end-to-end tests against the web app
[group('test')]
e2e *args:
    pnpm --filter @cartulary/web exec playwright test "$@"

# Install Playwright's browsers (once, before the first `just e2e`)
[group('test')]
e2e-install:
    pnpm --filter @cartulary/web exec playwright install --with-deps chromium

# TypeScript type checks across the whole workspace, mobile included
[group('test')]
type-check: build-shared
    pnpm type-check

# Type-check the web app only — the check CI gates on
[group('test')]
type-check-web: build-shared
    pnpm --filter @cartulary/web type-check

# Type-check the mobile app only
[group('test')]
type-check-mobile: build-shared
    pnpm --filter @cartulary/mobile type-check

# ESLint across the workspace
[group('test')]
lint:
    pnpm lint

# The GitHub Actions test job, from a clean install (.github/workflows/docker-build.yml)
[group('test')]
ci: venv-check
    "{{ py }}" -m pip install -q -r "{{ backend }}/requirements.txt"
    cd "{{ backend }}" && "{{ venv }}/bin/pytest" -v --maxfail=3 --cov=app --cov-report=term
    pnpm install --frozen-lockfile
    just build-shared
    pnpm --filter @cartulary/web type-check

# ─── Database ─────────────────────────────────────────────────────────────────

# Apply all pending migrations
[group('db')]
migrate: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/alembic" upgrade head

# Autogenerate a migration: just migration "add foo table"
[group('db')]
migration message: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/alembic" revision --autogenerate -m "$1"
    @echo "⚠️  Review the generated file in {{ backend }}/alembic/versions before applying it"

# Roll back one migration
[group('db')]
migrate-down: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/alembic" downgrade -1

# The revision the database is currently on
[group('db')]
db-current: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/alembic" current

# Migration history
[group('db')]
db-history: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/alembic" history --indicate-current

# psql shell in the Postgres container
[group('db')]
psql *args:
    {{ compose }} exec postgres psql -U cartulary -d cartulary "$@"

# redis-cli in the Redis container
[group('db')]
redis *args:
    {{ compose }} exec redis redis-cli "$@"

# Drop every table and re-migrate — destroys all data
[group('db')]
[confirm("This drops every table in the database. Continue? (y/N)")]
db-reset: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ venv }}/bin/alembic" downgrade base && "{{ venv }}/bin/alembic" upgrade head

# Change the vector dimension and drop existing embeddings, e.g. just embedding-dimension 768
[group('db')]
[confirm("This deletes every stored embedding. Continue? (y/N)")]
embedding-dimension dimension: venv-check
    {{ load_env }} && cd "{{ backend }}" && "{{ py }}" scripts/update_embedding_dimension.py "$1"

# ─── Docker ───────────────────────────────────────────────────────────────────

# Start the dev stack in the background
[group('docker')]
up *args:
    {{ compose }} up -d "$@"

# Rebuild images and start the dev stack
[group('docker')]
up-build *args:
    {{ compose }} up -d --build "$@"

# Start only Postgres, Redis, backend and worker — run the frontend with `just dev-web`
[group('docker')]
up-backend:
    {{ compose }} up -d postgres redis backend celery_worker

# Stop the dev stack
[group('docker')]
down *args:
    {{ compose }} down "$@"

# Restart one service, or all of them: just restart backend
[group('docker')]
restart *args:
    {{ compose }} restart "$@"

# Follow logs, optionally for one service: just logs celery_worker
[group('docker')]
logs *args:
    {{ compose }} logs -f --tail=100 "$@"

# Show container status
[group('docker')]
ps:
    {{ compose }} ps

# Build images without starting anything
[group('docker')]
docker-build *args:
    {{ compose }} build "$@"

# Shell into a running service: just shell backend
[group('docker')]
shell service="backend":
    {{ compose }} exec {{ service }} /bin/sh

# Run a command in a service: just exec backend pytest -v
[group('docker')]
exec service +cmd:
    {{ compose }} exec "$1" "${@:2}"

# Stop the stack and delete its volumes — destroys database and document storage
[group('docker')]
[confirm("This deletes the Postgres, Redis and document volumes. Continue? (y/N)")]
down-volumes:
    {{ compose }} down -v

# Start the production stack
[group('docker')]
prod-up *args:
    {{ compose_prod }} up -d "$@"

# Stop the production stack
[group('docker')]
prod-down *args:
    {{ compose_prod }} down "$@"

# Follow production logs
[group('docker')]
prod-logs *args:
    {{ compose_prod }} logs -f --tail=100 "$@"

# ─── Housekeeping ─────────────────────────────────────────────────────────────

# Remove build output and node_modules
[group('clean')]
clean:
    pnpm clean

# Remove Python caches and the backend venv
[group('clean')]
clean-py:
    find "{{ backend }}" -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf "{{ backend }}/.pytest_cache" "{{ venv }}"

# Reinstall the JS workspace from scratch
[group('clean')]
reinstall:
    rm -rf "{{ root }}/node_modules" "{{ root }}/apps/*/node_modules" "{{ root }}/packages/*/node_modules"
    pnpm install
