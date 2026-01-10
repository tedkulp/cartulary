# Cartulary

A modern digital archive system with OCR processing, semantic search, and AI-powered metadata extraction.

## Features

- **Document Management**: Upload, organize, and manage PDF files and images
- **Real-Time Updates**: WebSocket-based live updates for document status, uploads, and changes
- **OCR Processing**: Automatic text extraction using EasyOCR with automatic image resizing
- **Semantic Search**: RAG-powered search with vector embeddings
- **AI Metadata Extraction**: Automatic tagging, categorization, and metadata extraction using LLMs (OpenAI, Gemini, Ollama)
- **Advanced Sorting**: Server-side sorting by title, date, file size, and processing status
- **Document Statistics**: Real-time word count, file size metrics, and document counts
- **Multi-User Support**: Role-based access control and document sharing
- **Multiple Import Methods**:
  - Manual upload via web interface with drag-and-drop
  - Directory watching for automatic import
  - IMAP mailbox monitoring
- **Optional OIDC Authentication**: Enterprise SSO support

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with pgvector extension
- **Task Queue**: Celery + Redis
- **OCR**: EasyOCR (with automatic image resizing for memory optimization)
- **Embeddings**: sentence-transformers (local) or OpenAI API
- **Storage**: Local filesystem or S3-compatible (MinIO)
- **Real-Time**: WebSocket with Redis pub/sub for live updates

### Frontend
- **Framework**: Vue 3 (Composition API) + TypeScript
- **Build Tool**: Vite
- **UI**: Tailwind CSS + PrimeVue
- **PDF Viewer**: PDF.js (vue-pdf-embed)
- **Real-Time**: WebSocket client with automatic reconnection

### Infrastructure
- **Deployment**: Docker Compose
- **Caching**: Redis
- **Message Broker**: Redis pub/sub for WebSocket broadcasting

## Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 6GB RAM available for Docker (4GB for Celery workers + 2GB for services)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cartulary
   ```

2. **Copy environment files**:
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

3. **Generate a secret key**:
   ```bash
   # Update the SECRET_KEY in .env
   openssl rand -hex 32
   ```

4. **Start the services**:
   ```bash
   docker-compose up -d
   ```

5. **Run database migrations**:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

6. **Access the application**:
   - Frontend: http://localhost:8080
   - API Documentation: http://localhost:8080/api/v1/docs

## Docker Images

Pre-built multi-architecture Docker images are available from GitHub Container Registry:

### Pull Images

```bash
# Latest (main branch)
docker pull ghcr.io/tedkulp/cartulary-backend:latest
docker pull ghcr.io/tedkulp/cartulary-celery-worker:latest
docker pull ghcr.io/tedkulp/cartulary-web:latest

# Specific version
docker pull ghcr.io/tedkulp/cartulary-backend:0.7.0

# Specific commit (for debugging)
docker pull ghcr.io/tedkulp/cartulary-backend:main-136e1e8
```

### Supported Architectures

- **linux/amd64** (x86_64)
- **linux/arm64** (ARM64/aarch64, including Apple Silicon)

### Production Deployment

Use the production docker-compose file with pre-built images:

```bash
# Pull latest images and start
docker-compose -f docker-compose.prod.yml up -d

# Or specify a version
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## Development Setup

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm run test
npm run test:e2e
```

## Project Structure

```
cartulary/
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   ├── api/v1/      # API endpoints (including WebSocket)
│   │   ├── core/        # Security, permissions
│   │   ├── models/      # Database models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic (OCR, notifications, WebSocket)
│   │   ├── tasks/       # Celery tasks
│   │   └── workers/     # Background workers
│   ├── alembic/         # Database migrations
│   └── tests/           # Tests
├── frontend/            # Vue 3 frontend
│   └── src/
│       ├── components/  # Vue components
│       ├── composables/ # Vue composables (WebSocket)
│       ├── views/       # Page components
│       ├── stores/      # Pinia stores
│       └── services/    # API services (including WebSocket)
├── docker-compose.yml   # Development environment
└── CLAUDE.md           # Development guide for Claude Code
```

## Configuration

See [.env.example](.env.example) and [backend/.env.example](backend/.env.example) for all available configuration options.

### Key Configuration Options

#### Storage & Processing
- `STORAGE_TYPE`: `local` or `s3` for file storage
- `OCR_ENABLED`: Enable/disable OCR processing
- `OCR_LANGUAGES`: List of languages for OCR (default: `["en"]`)
- `OCR_USE_GPU`: Enable GPU acceleration for OCR (default: `false`)

#### Embeddings & Search
- `EMBEDDING_PROVIDER`: `local` (sentence-transformers) or `openai`
- `EMBEDDING_MODEL`: Model name (default: `all-MiniLM-L6-v2` for local)
- `EMBEDDING_DIMENSION`: Vector dimension (384 for local, 1536 for OpenAI)

#### LLM Integration
- `LLM_ENABLED`: Enable optional LLM features
- `LLM_PROVIDER`: `openai`, `gemini`, or `ollama`
- `LLM_MODEL`: Model name (e.g., `gpt-4`, `gemini-pro`, `llama2`)
- `LLM_BASE_URL`: Base URL for Ollama (default: `http://localhost:11434`)

#### Authentication
- `SECRET_KEY`: JWT secret key (generate with `openssl rand -hex 32`)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT token expiration (default: 30)
- `OIDC_ENABLED`: Enable OIDC authentication
- `OIDC_DISCOVERY_URL`: OIDC provider discovery endpoint
- `OIDC_AUTO_PROVISION_USERS`: Auto-create users on first login

#### Performance Tuning
- `CELERY_CONCURRENCY`: Number of Celery worker processes (default: 2)
- `CELERY_MAX_TASKS_PER_CHILD`: Restart workers after N tasks (default: 10)
- `CELERY_MEMORY_LIMIT`: Max memory per worker (default: 4GB)

#### Real-Time Updates
- `REDIS_URL`: Redis URL for WebSocket pub/sub and Celery (default: `redis://redis:6379/0`)

## Implementation Status

### ✅ Phase 1: Foundation
- [x] Project scaffolding
- [x] Docker Compose setup
- [x] Database schema
- [x] Authentication system (JWT)
- [x] Basic document upload with deduplication

### ✅ Phase 2: OCR & Full-Text Search
- [x] OCR integration (PaddleOCR - optional)
- [x] PDF text extraction (PyMuPDF)
- [x] Background processing (Celery)
- [x] Full-text search (ILIKE-based)
- [x] Tag management (backend API + UI)
- [x] Search UI with results
- [x] Processing status display
- [x] Reprocess endpoint for failed documents

### ✅ Phase 3: Semantic Search
- [x] Embedding generation (OpenAI + local support)
- [x] Vector search (pgvector with cosine similarity)
- [x] Hybrid search (RRF combining FTS + semantic)
- [x] Search mode UI (Fulltext/Semantic/Hybrid)
- [x] Dimension validation on startup
- [x] Provider switching support

### ✅ Phase 4: LLM Integration
- [x] LLM service (OpenAI, Gemini, Ollama support)
- [x] Metadata extraction (title, correspondent, date, type, summary)
- [x] Auto-tagging from LLM suggestions
- [x] Integration with document processing pipeline
- [x] Frontend UI for extracted metadata display
- [x] Manual metadata regeneration button

### ✅ Phase 5: Multi-User & Permissions
- [x] RBAC implementation
- [x] Document access control
- [x] Permission service

### ✅ Phase 6: Import Sources
- [x] Directory watching with background worker
- [x] IMAP mailbox monitoring
- [x] Duplicate detection across all import methods

### ✅ Phase 7: OIDC & Real-Time Updates
- [x] OIDC authentication with auto-provisioning
- [x] WebSocket real-time updates
- [x] Server-side sorting and pagination
- [x] Document statistics dashboard
- [x] OCR reliability improvements
- [x] Memory optimization for large images
- [x] Enhanced error logging

### 🔲 Phase 8: Production Ready
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Production deployment guide

## Key Features in Detail

### Real-Time Updates

Cartulary uses WebSocket connections to provide live updates across all connected clients:

- **Document Uploads**: See new documents appear instantly when uploaded by any user
- **Processing Status**: Watch OCR and LLM processing progress in real-time
- **Metadata Changes**: Tag additions and updates appear immediately
- **Multi-Tab Sync**: Changes sync across all browser tabs automatically
- **Auto Reconnection**: Graceful handling of network interruptions with exponential backoff

**Technical Implementation**:
- Backend: FastAPI WebSocket endpoint with Redis pub/sub
- Frontend: Vue 3 composable with automatic reconnection
- Events: `document.created`, `document.updated`, `document.deleted`, `document.status_changed`

### OCR Optimization

The OCR system automatically optimizes processing for reliability and memory efficiency:

- **Automatic Image Resizing**: Images larger than 2MB are automatically resized to 2048px maximum dimension
- **Memory Management**: Celery workers limited to 4GB with automatic restarts after 10 tasks
- **Enhanced Logging**: Detailed error tracking for failed OCR operations
- **Retry Logic**: Failed tasks automatically retry with exponential backoff

### Server-Side Sorting

All document lists support efficient server-side sorting:

- **Sortable Fields**: Title, creation date, update date, file size, processing status, filename
- **Performance**: Handles 1000+ documents efficiently with database-level sorting
- **Pagination**: Support for skip/limit with configurable maximum (default: 1000 documents)

### Document Statistics

Real-time metrics calculated across all accessible documents:

- **Total Documents**: Count of all documents in the system
- **Total File Size**: Aggregate storage usage with human-readable formatting
- **Total Words**: Word count extracted from OCR text across all documents
- **Average File Size**: Mean document size for capacity planning

## Documentation

- [Development Guide (CLAUDE.md)](CLAUDE.md) - Comprehensive guide for development with Claude Code
- [Implementation Plan](.claude/plans/deep-sprouting-volcano.md) - Detailed implementation roadmap
- [API Documentation](http://localhost:8000/api/v1/docs) - OpenAPI/Swagger docs (when running)

## Contributing

1. Review [CLAUDE.md](CLAUDE.md) for coding conventions and best practices
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

## License

[Add your license here]

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [Vue 3](https://vuejs.org/)
- OCR by [EasyOCR](https://github.com/JaidedAI/EasyOCR)
- Vector search with [pgvector](https://github.com/pgvector/pgvector)
- Real-time updates with [Redis](https://redis.io/)

## Troubleshooting

### WebSocket Connection Issues

If real-time updates aren't working:

1. Check Redis is running: `docker-compose ps redis`
2. Verify WebSocket endpoint is accessible: Check browser console for connection errors
3. Ensure JWT token is valid: WebSocket authentication uses the same token as API calls

### Celery Worker Memory Issues

If workers are being killed (OOM):

1. Check memory limits in [docker-compose.yml](docker-compose.yml:84-89)
2. Reduce `CELERY_CONCURRENCY` if processing very large images
3. Monitor with: `docker stats cartulary-celery-worker-1`

### OCR Processing Failures

If OCR consistently fails on specific files:

1. Check Celery worker logs: `docker-compose logs celery-worker`
2. Verify file is readable and not corrupted
3. Check file size - very large images (>10MB) may need manual resizing
4. Try reprocessing: Click "Reprocess OCR" in document details

### Database Connection Errors

If you see `NotImplementedError` in Celery logs:

1. Restart Celery workers: `docker-compose restart celery-worker celery-beat`
2. This is typically auto-handled by connection pool disposal in tasks

---

**Version**: 0.7.0 (Phase 7 - Real-Time Updates & Optimizations Complete)
**Status**: In Active Development
