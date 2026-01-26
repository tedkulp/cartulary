# Docker Development Guide

## Quick Start

### Start all services
```bash
docker compose up
```

### Start without frontend (recommended for development)
```bash
docker compose up postgres redis backend celery_worker
```

Then run frontend locally:
```bash
pnpm dev
```

### Rebuild after changes
```bash
docker compose up --build
```

## Services

- **postgres** - PostgreSQL 16 with pgvector (port 5432)
- **redis** - Redis cache and Celery broker (port 6379)
- **backend** - FastAPI backend (port 8000, not exposed)
- **celery_worker** - Background task processor
- **frontend** - React web app (port 8080, proxies to backend)

## Architecture

The frontend acts as a reverse proxy to the backend:

- **Development (local)**: Vite dev server on port 8080 proxies `/api` requests to `localhost:8000`
- **Development (Docker)**: Vite dev server on port 8080 proxies `/api` requests to `backend:8000`
- **Production**: nginx on port 80 proxies `/api` requests to `backend:8000`

The frontend code **only uses relative URLs** (`/api/v1/...`). The backend is never directly exposed to clients - all traffic goes through the frontend.

## Development Workflow

### Recommended: Local Frontend Development

For the best development experience with hot-reload:

1. Start backend services only:
   ```bash
   docker compose up postgres redis backend celery_worker
   ```

2. Run frontend locally:
   ```bash
   pnpm dev
   ```

This gives you:
- ✅ Instant hot-reload on code changes
- ✅ Full access to dev tools
- ✅ Faster iteration cycle

### Docker-Only Development

If you prefer to run everything in Docker:

```bash
docker compose up
```

**Note**: The frontend container does NOT have hot-reload enabled. To see code changes:
1. Make your changes
2. Rebuild: `docker compose up --build frontend`

## Environment Variables

Create a `.env` file in the root directory:

```bash
# Database
DB_PASSWORD=changeme

# Security
SECRET_KEY=your-secret-key-change-in-production

# Features (all optional)
EMBEDDING_ENABLED=false
LLM_ENABLED=false
OCR_ENABLED=false

# OIDC (optional)
OIDC_ENABLED=false
```

See `.env.example` for all available options.

## Useful Commands

### View logs
```bash
docker compose logs -f backend
docker compose logs -f celery_worker
```

### Restart a service
```bash
docker compose restart backend
```

### Stop all services
```bash
docker compose down
```

### Clean everything (including data)
```bash
docker compose down -v
```

### Run backend migrations
Migrations run automatically when the backend starts. To run manually:
```bash
docker compose exec backend alembic upgrade head
```

### Access database
```bash
docker compose exec postgres psql -U cartulary -d cartulary
```

### Access Redis
```bash
docker compose exec redis redis-cli
```

## Troubleshooting

### Frontend won't start
Make sure you've built the container:
```bash
docker compose build frontend
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
   docker compose up -d backend
   ```

3. Access backend docs at `http://localhost:8000/docs`

### Database connection errors
Ensure postgres is healthy:
```bash
docker compose ps
```

### Port conflicts
If ports are already in use, you can change them in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Use 5433 instead of 5432
```

### Clear build cache
```bash
docker compose build --no-cache
```

## Production Deployment

For production, use the production docker-compose file with pre-built images from GHCR:

```bash
# Pull and start all services with GHCR images
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop services
docker-compose -f docker-compose.prod.yml down
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
ghcr.io/tedkulp/cartulary-backend:main-136e1e8
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
- Backend: ~3 minutes (reduced, no OCR libraries)
- Celery worker: ~3 minutes (same as backend, uses standard Dockerfile)
- Web frontend: ~4 minutes
- **Total**: ~10 minutes (builds run in parallel)

**Incremental builds** (with cache):
- Backend: ~30 seconds
- Celery worker: ~30 seconds
- Web frontend: ~1 minute
- **Total**: ~2 minutes

**Note:** Build times significantly reduced after removing PaddleOCR/EasyOCR dependencies.
