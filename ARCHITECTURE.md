# Cartulary Architecture

## Overview

Cartulary is a digital archive system built as a monorepo with three main applications:
- **Backend**: FastAPI Python server
- **Web**: React web application
- **Mobile**: React Native mobile app (Expo)

Plus a shared package for code reuse between web and mobile.

## Monorepo Structure

```
cartulary/
├── apps/
│   ├── backend/          # FastAPI Python backend
│   ├── web/              # React web frontend
│   └── mobile/           # React Native mobile app
├── packages/
│   └── shared/           # Shared TypeScript code
├── pnpm-workspace.yaml   # pnpm workspace config
├── turbo.json            # Turborepo config
└── package.json          # Root package.json
```

### Package Manager & Build System

- **pnpm**: Fast, disk-efficient package manager with workspace support
- **Turborepo**: Build system for monorepos with caching and parallel execution

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
   - WebSocket pub/sub

3. **`cartulary-backend`** - FastAPI application server
   - HTTP API endpoints
   - WebSocket endpoints
   - Authentication & authorization
   - Background workers (directory watcher, IMAP watcher)
   - Runs on port 8000

4. **`cartulary-celery-worker`** - Celery worker + beat
   - Heavy processing tasks (vision OCR via Ollama, embeddings, LLM metadata extraction)
   - Scheduled tasks (periodic cleanup, etc.)
   - Both worker and beat scheduler run in same container
   - Connects to external Ollama service for OCR and embeddings

5. **`cartulary-web`** - React web frontend
   - Development: Vite dev server on port 8080
   - Production: nginx serving static files
   - Proxies API requests to backend

### External Dependencies

- **Ollama** (required): Runs separately, provides vision OCR and embeddings
  - Not containerized in docker-compose (user manages separately)
  - Connected via `LLM_BASE_URL` environment variable

## Application Architecture

### Backend (`apps/backend`)

```
apps/backend/
├── app/
│   ├── api/v1/              # API endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── documents.py     # Document CRUD
│   │   ├── search.py        # Search endpoints
│   │   ├── tags.py          # Tag management
│   │   ├── websocket.py     # WebSocket endpoint
│   │   └── ...
│   ├── core/                # Core utilities
│   │   ├── security.py      # JWT, password hashing
│   │   ├── permissions.py   # RBAC
│   │   └── exceptions.py    # Custom exceptions
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   │   ├── ocr_service.py   # Ollama vision OCR
│   │   ├── embedding_service.py  # Text embeddings
│   │   ├── llm_service.py   # LLM metadata extraction
│   │   ├── search_service.py     # Hybrid search
│   │   └── ...
│   ├── tasks/               # Celery tasks
│   │   ├── celery_app.py    # Celery configuration
│   │   └── document_tasks.py # Document processing
│   ├── workers/             # Background workers
│   │   ├── directory_watcher.py
│   │   └── imap_watcher.py
│   ├── background_workers.py # Worker lifecycle management
│   └── main.py              # FastAPI app
├── alembic/                 # Database migrations
└── requirements.txt
```

### Web Frontend (`apps/web`)

```
apps/web/
├── src/
│   ├── components/          # React components
│   │   ├── ui/              # shadcn/ui components
│   │   ├── AppHeader.tsx
│   │   ├── Layout.tsx
│   │   └── UploadDialog.tsx
│   ├── pages/               # Page components
│   │   ├── DocumentsList.tsx
│   │   ├── DocumentDetail.tsx
│   │   ├── Login.tsx
│   │   └── ...
│   ├── services/            # API client
│   │   ├── api.ts           # Axios instance
│   │   └── index.ts
│   ├── lib/                 # Utilities
│   │   └── utils.ts         # cn() helper
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── vite.config.ts
└── tailwind.config.js
```

### Mobile App (`apps/mobile`)

```
apps/mobile/
├── src/
│   ├── screens/             # Screen components
│   │   ├── auth/            # Login, Register
│   │   ├── documents/       # Document list, viewer
│   │   ├── camera/          # Camera capture
│   │   ├── search/          # Search screen
│   │   └── settings/        # Settings
│   ├── components/          # Reusable components
│   │   └── auth/            # Auth-related components
│   ├── navigation/          # React Navigation
│   │   ├── RootNavigator.tsx
│   │   ├── AuthNavigator.tsx
│   │   └── MainNavigator.tsx
│   ├── stores/              # Zustand stores
│   │   ├── authStore.ts
│   │   ├── documentStore.ts
│   │   └── settingsStore.ts
│   ├── services/            # API client
│   │   ├── api.ts
│   │   ├── auth.service.ts
│   │   └── document.service.ts
│   ├── types/               # TypeScript types
│   ├── config/              # App configuration
│   └── utils/               # Utilities
├── App.tsx
├── app.json                 # Expo config
└── package.json
```

### Shared Package (`packages/shared`)

```
packages/shared/
├── src/
│   ├── services/            # API services
│   │   ├── auth.service.ts
│   │   ├── document.service.ts
│   │   ├── search.service.ts
│   │   └── ...
│   ├── types/               # Type definitions
│   │   ├── auth.ts
│   │   ├── document.ts
│   │   └── ...
│   ├── hooks/               # React hooks
│   │   ├── useAuth.ts
│   │   ├── useDocuments.ts
│   │   └── ...
│   ├── stores/              # Zustand stores
│   │   └── authStore.ts
│   └── utils/               # Utilities
├── tsup.config.ts           # Build config
└── package.json
```

## Background Workers

### Integration with FastAPI

The directory and IMAP watchers run as **background tasks** within the FastAPI backend process using FastAPI's `lifespan` context manager.

**File:** `apps/backend/app/background_workers.py`

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
│ (Web/Mobile)│
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
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Postgres   │       │   Celery    │──────▶│   Ollama    │
│  (Metadata) │◀──────│   Worker    │       │ (OCR/Embed) │
└─────────────┘       └─────────────┘       └─────────────┘
```

## Data Flow

### Document Upload Flow

1. Client uploads file via API or mobile camera
2. Backend calculates SHA-256 checksum
3. Check for duplicates in database
4. Store file in local storage or S3
5. Create document record in PostgreSQL
6. Queue Celery task for processing
7. Celery worker:
   - Extracts text via Ollama vision OCR
   - Generates embeddings via Ollama
   - Optionally extracts metadata via LLM
8. Updates document record with extracted data
9. Broadcasts update via WebSocket

### Search Flow

1. Client sends search query
2. Backend performs hybrid search:
   - Full-text search (PostgreSQL ILIKE)
   - Semantic search (pgvector cosine similarity)
3. Results combined via Reciprocal Rank Fusion (RRF)
4. Return ranked results to client

## Production Deployment

For production, the architecture remains the same but uses:

```yaml
services:
  postgres:     # Required
  redis:        # Required
  backend:      # FastAPI + background workers
  celery:       # Worker + beat (merged)
  web:          # nginx serving static files
```

Total: **5 containers** in production (same as development)

Plus external Ollama service managed separately.

## Benefits of This Architecture

1. **Monorepo**: Single repository for all code, easier to maintain
2. **Code Sharing**: Shared package reduces duplication between web and mobile
3. **Consolidated Containers**: 5 containers instead of 8 (37% reduction)
4. **External OCR**: Ollama runs separately, can be shared across services
5. **Simpler Management**: Fewer processes to monitor and debug
6. **Faster Startup**: Less container orchestration overhead
7. **Better Logging**: Background workers log to main backend process

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

### Ollama Connection Issues

Verify Ollama is accessible:
```bash
curl http://localhost:11434/api/tags
```

Check `LLM_BASE_URL` environment variable is set correctly.

---

Last Updated: 2026-01-26
Architecture Version: 3.0 (Monorepo with React Web + React Native Mobile)
