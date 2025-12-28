# Cartulary Architecture

## Container Architecture

Cartulary uses a **consolidated container architecture** for simplicity and resource efficiency.

### Containers (5 total)

1. **`cartulary-postgres`** - PostgreSQL 16 with pgvector extension
   - Stores all application data
   - Provides vector similarity search capabilities

2. **`cartulary-redis`** - Redis 7
   - Caching layer
   - Celery message broker
   - Celery result backend

3. **`cartulary-backend`** - FastAPI application server
   - HTTP API endpoints
   - Authentication & authorization
   - Background workers (directory watcher, IMAP watcher)
   - Runs on port 8000

4. **`cartulary-celery-worker`** - Celery worker + beat
   - Heavy processing tasks (OCR, embeddings, LLM metadata extraction)
   - Scheduled tasks (periodic cleanup, etc.)
   - Both worker and beat scheduler run in same container

5. **`cartulary-frontend`** - Vue 3 development server
   - Development only (production serves static files from nginx/CDN)
   - Runs on port 5173

### Previous Architecture (8 containers)

The system was previously split into 8 separate containers:
- ❌ `cartulary-celery-beat` - **Merged into celery-worker**
- ❌ `cartulary-directory-watcher` - **Merged into backend**
- ❌ `cartulary-imap-watcher` - **Merged into backend**

## Background Workers

### Integration with FastAPI

The directory and IMAP watchers now run as **background tasks** within the FastAPI backend process using FastAPI's `lifespan` context manager.

**File:** `backend/app/background_workers.py`

```python
from app.background_workers import lifespan

app = FastAPI(lifespan=lifespan)
```

### Configuration

Background workers are controlled via environment variables:

```bash
# Enable/disable directory watcher (default: true)
ENABLE_DIRECTORY_WATCHER=true

# Enable/disable IMAP watcher (default: false)
ENABLE_IMAP_WATCHER=false
```

### How It Works

1. **Startup:** When FastAPI starts, the `lifespan` context manager:
   - Checks which workers are enabled via environment variables
   - Spawns background tasks for each enabled worker
   - Runs them in separate executor threads (non-blocking)

2. **Runtime:** Background workers run continuously:
   - **Directory Watcher:** Monitors `/data/import_watch` for new files
   - **IMAP Watcher:** Checks configured IMAP mailboxes for new emails

3. **Shutdown:** When FastAPI shuts down:
   - Gracefully cancels all background tasks
   - Waits for them to complete

## Task Processing Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP Upload
       ▼
┌─────────────┐       ┌─────────────┐
│   Backend   │──────▶│    Redis    │
│  (FastAPI)  │       │  (Broker)   │
└──────┬──────┘       └──────┬──────┘
       │                     │
       │ Store file          │ Queue task
       │                     │
       ▼                     ▼
┌─────────────┐       ┌─────────────┐
│  Postgres   │       │   Celery    │
│  (Metadata) │◀──────│   Worker    │
└─────────────┘       └─────────────┘
                      (OCR, Embeddings, LLM)
```

## Directory Structure

```
cartulary/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── background_workers.py  # NEW: Background worker manager
│   │   ├── core/            # Security, permissions
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── tasks/           # Celery tasks
│   │   ├── workers/         # Directory & IMAP watchers
│   │   └── main.py          # FastAPI app
│   ├── run_directory_watcher.py  # DEPRECATED: Use ENABLE_DIRECTORY_WATCHER
│   └── run_imap_watcher.py       # DEPRECATED: Use ENABLE_IMAP_WATCHER
├── frontend/
├── docker-compose.yml       # 5 services (consolidated)
└── docker-compose.yml.backup  # 8 services (old)
```

## Benefits of Consolidated Architecture

1. **Fewer Resources:** 5 containers instead of 8 (37% reduction)
2. **Simpler Management:** Fewer processes to monitor and debug
3. **Faster Startup:** Less container orchestration overhead
4. **Easier Development:** Fewer moving parts
5. **Better Logging:** Background workers log to main backend process

## Production Deployment

For production, further consolidation is possible:

```yaml
services:
  postgres:     # Required
  redis:        # Required
  backend:      # FastAPI + background workers
  celery:       # Worker + beat (merged)
  # Frontend served as static files from nginx/CDN
```

Total: **4 containers** in production

## Migration Guide

### From Old to New Architecture

1. **Stop old containers:**
   ```bash
   docker compose down
   ```

2. **The new docker-compose.yml is already in place**
   - Old version backed up to `docker-compose.yml.backup`

3. **Start new architecture:**
   ```bash
   docker compose up -d
   ```

4. **Verify background workers:**
   ```bash
   docker logs cartulary-backend | grep "background"
   # Should show: "Directory watcher enabled and started"
   ```

### Environment Variables

New variables for worker control:

```bash
# In .env or docker-compose.yml
ENABLE_DIRECTORY_WATCHER=true   # Enable filesystem watching
ENABLE_IMAP_WATCHER=false       # Enable IMAP email import
```

## Troubleshooting

### Background Workers Not Starting

Check backend logs:
```bash
docker logs cartulary-backend | grep -i watcher
```

Expected output:
```
Starting background workers...
Directory watcher enabled and started
```

### Disable Background Workers

Set environment variables to `false`:
```bash
ENABLE_DIRECTORY_WATCHER=false
ENABLE_IMAP_WATCHER=false
```

### Celery Worker + Beat Issues

Check if both are running:
```bash
docker exec cartulary-celery-worker ps aux | grep celery
```

Should show:
- `celery beat` process (scheduler)
- `celery worker` process (task executor)

## Future Optimizations

Potential further consolidation:

1. **Merge Celery into Backend** (development only)
   - Run Celery worker as background thread in FastAPI
   - Not recommended for production (resource isolation)

2. **Use Gunicorn with multiple workers** (production)
   - Background workers run in master process
   - API workers handle requests
   - Better resource utilization

3. **Kubernetes Deployment**
   - Backend as Deployment
   - Celery as separate Deployment (for scaling)
   - Background workers as DaemonSet or CronJob

---

Last Updated: 2025-12-26
Architecture Version: 2.0 (Consolidated, Rebranded as Cartulary)
