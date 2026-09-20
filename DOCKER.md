# Docker Development Guide

Every command below is a [`just`](https://just.systems) recipe wrapping `docker compose`.
`just --list` shows them all, and the raw `docker compose` form still works if you prefer it.

## Quick Start

### Start all services
```bash
just up
```

### Start without frontend (recommended for development)
```bash
just up-backend
```

Then run frontend locally:
```bash
just dev
```

### Rebuild after changes
```bash
just up-build
```

## Services

- **postgres** - PostgreSQL 16 with pgvector (port 5432)
- **redis** - Redis cache and Celery broker (port 6379)
- **backend** - FastAPI backend (port 8000, not exposed by default)
- **celery_worker** - Background task processor (OCR, embeddings)
- **web** - React web app (port 8080, proxies to backend)

### External Dependencies

- **Ollama** - Required for OCR and embeddings, runs separately
  - Install from: https://ollama.ai
  - Pull models: `ollama pull minicpm-v && ollama pull nomic-embed-text`
  - Configure via `LLM_BASE_URL` environment variable

## Architecture

The web frontend acts as a reverse proxy to the backend:

- **Development (local)**: Vite dev server on port 8080 proxies `/api` requests to `localhost:8000`
- **Development (Docker)**: Vite dev server on port 8080 proxies `/api` requests to `backend:8000`
- **Production**: nginx on port 80 proxies `/api` requests to `backend:8000`

The frontend code **only uses relative URLs** (`/api/v1/...`). The backend is never directly exposed to clients - all traffic goes through the frontend.

## Development Workflow

### Recommended: Local Frontend Development

For the best development experience with hot-reload:

1. Start backend services only:
   ```bash
   just up-backend
   ```

2. Run frontend locally:
   ```bash
   just install-js
   just dev
   ```

This gives you:
- ✅ Instant hot-reload on code changes
- ✅ Full access to dev tools
- ✅ Faster iteration cycle

### Docker-Only Development

If you prefer to run everything in Docker:

```bash
just up
```

**Note**: The frontend container does NOT have hot-reload enabled. To see code changes:
1. Make your changes
2. Rebuild: `just up-build frontend`

## Environment Variables

Create a `.env` file in the root directory:

```bash
# Database
DB_PASSWORD=changeme

# Security
SECRET_KEY=your-secret-key-change-in-production

# Ollama (required for OCR and embeddings)
LLM_BASE_URL=http://host.docker.internal:11434  # For Docker on Mac/Windows
# LLM_BASE_URL=http://172.17.0.1:11434          # For Docker on Linux

# Features
EMBEDDING_ENABLED=true
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768

OCR_ENABLED=true
VISION_OCR_MODEL=minicpm-v

# Metadata extraction and chat both need this; false makes the chat API return 503
LLM_ENABLED=false

# OIDC (optional)
OIDC_ENABLED=false
```

See `.env.example` for all available options.

## Useful Commands

### View logs
```bash
just logs backend
just logs celery_worker
```

### Restart a service
```bash
just restart backend
```

### Stop all services
```bash
just down
```

### Clean everything (including data)
```bash
just down-volumes
```

### Run backend migrations
Migrations run automatically when the backend starts. To run manually:
```bash
just exec backend alembic upgrade head
```

### Access database
```bash
just psql
```

### Access Redis
```bash
just redis
```

## Troubleshooting

### Frontend won't start
Make sure you've built the container:
```bash
just docker-build frontend
```

### Need direct backend access for debugging
The backend port is not exposed by default. To access it directly:

1. Uncomment the backend ports in `docker-compose.yml`:
   ```yaml
   ports:
     - "8000:8000"
   ```

2. Restart the backend:
   ```bash
   just up backend
   ```

3. Access backend docs at `http://localhost:8000/docs`

### Database connection errors
Ensure postgres is healthy:
```bash
just ps
```

### Port conflicts
If ports are already in use, you can change them in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Use 5433 instead of 5432
```

### Clear build cache
```bash
just docker-build --no-cache
```

### Ollama connection issues

**On Mac/Windows:**
```bash
LLM_BASE_URL=http://host.docker.internal:11434
```

**On Linux:**
```bash
LLM_BASE_URL=http://172.17.0.1:11434
```

Or run Ollama in Docker:
```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

## Production Deployment

For production, use the production docker-compose file with pre-built images from GHCR:

```bash
# Pull and start all services with GHCR images
just prod-up

# View logs
just prod-logs

# Stop services
just prod-down
```

Or build locally:

```bash
docker build -f apps/web/Dockerfile --target production -t cartulary-web .
docker run -p 80:80 cartulary-web
```

The production build uses nginx to serve the static files.

## Continuous Integration

GitHub Actions automatically builds and publishes multi-architecture Docker images on:

- **Push to main branch** → `latest` tag
- **Git tags `v*.*.*`** → semver tags (e.g., `0.7.0`, `0.7`, `0`)
- **Pull requests** → build validation only (no push to registry)

### View Builds

- Actions: https://github.com/tedkulp/cartulary/actions
- Container Registry: https://github.com/tedkulp/cartulary/pkgs/container/cartulary-backend

### Available Images

All images support both **linux/amd64** and **linux/arm64** architectures:

- `ghcr.io/tedkulp/cartulary-backend:latest` - FastAPI backend
- `ghcr.io/tedkulp/cartulary-celery-worker:latest` - Celery worker (connects to external Ollama)
- `ghcr.io/tedkulp/cartulary-web:latest` - Production nginx frontend

**Note:** Ollama must be running separately and accessible to the containers. Configure via `LLM_BASE_URL` environment variable.

### Trigger Manual Builds

1. Go to: https://github.com/tedkulp/cartulary/actions/workflows/docker-build.yml
2. Click "Run workflow"
3. Select branch and whether to push to registry

### Build Features

- **Multi-arch builds** - AMD64 + ARM64 (Apple Silicon compatible)
- **BuildKit caching** - 3-5x faster incremental builds
- **Security scanning** - Trivy vulnerability detection with GitHub Security integration
- **Automated testing** - pytest + type-checking runs before building
- **Smoke tests** - Verifies images work after build

### Image Tags

Each build creates multiple tags for flexibility:

```bash
# Latest from main branch
ghcr.io/tedkulp/cartulary-backend:latest

# Specific version (from git tags)
ghcr.io/tedkulp/cartulary-backend:0.7.0
ghcr.io/tedkulp/cartulary-backend:0.7
ghcr.io/tedkulp/cartulary-backend:0

# Commit-specific (for debugging)
ghcr.io/tedkulp/cartulary-backend:sha-136e1e8
```

### Local Multi-Arch Build

To test multi-architecture builds locally:

```bash
# Setup buildx
docker buildx create --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f apps/backend/Dockerfile \
  -t cartulary-backend:test \
  apps/backend
```

### Build Time Estimates

**First build** (no cache):
- Backend: ~3 minutes
- Celery worker: ~3 minutes (same as backend, uses standard Dockerfile)
- Web frontend: ~4 minutes
- **Total**: ~10 minutes (builds run in parallel)

**Incremental builds** (with cache):
- Backend: ~30 seconds
- Celery worker: ~30 seconds
- Web frontend: ~1 minute
- **Total**: ~2 minutes

## Mobile App

The mobile app (`apps/mobile`) is **not containerized** - it runs via Expo:

```bash
just install-js
just mobile
```

See [apps/mobile/README.md](apps/mobile/README.md) for mobile development instructions.

---

Last Updated: 2026-01-26
