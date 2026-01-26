# Cartulary

A modern digital archive system with OCR processing, semantic search, and AI-powered metadata extraction. Available as a web application and native mobile app.

## Features

- **Document Management**: Upload, organize, and manage PDF files and images
- **Real-Time Updates**: WebSocket-based live updates for document status, uploads, and changes
- **Vision-Based OCR**: LLM-powered text extraction using Ollama vision models (minicpm-v, llava, gemma3)
- **Semantic Search**: RAG-powered search with vector embeddings
- **AI Metadata Extraction**: Automatic tagging, categorization, and metadata extraction using LLMs
- **Advanced Sorting**: Server-side sorting by title, date, file size, and processing status
- **Document Statistics**: Real-time word count, file size metrics, and document counts
- **Multi-User Support**: Role-based access control and document sharing
- **Multiple Import Methods**:
  - Manual upload via web interface with drag-and-drop
  - Camera capture via mobile app
  - Directory watching for automatic import
  - IMAP mailbox monitoring
- **Optional OIDC Authentication**: Enterprise SSO support
- **Cross-Platform**: Web app + native iOS/Android mobile app

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with pgvector extension
- **Task Queue**: Celery + Redis
- **OCR**: Ollama vision models (minicpm-v, llava, gemma3) for text extraction
- **Embeddings**: Ollama (nomic-embed-text), sentence-transformers (local), or OpenAI API
- **Storage**: Local filesystem or S3-compatible (MinIO)
- **Real-Time**: WebSocket with Redis pub/sub for live updates

### Web Frontend (`apps/web`)
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **UI**: Tailwind CSS + Radix UI + shadcn/ui components
- **State Management**: Zustand
- **PDF Viewer**: react-pdf (PDF.js wrapper)
- **Real-Time**: WebSocket client with automatic reconnection

### Mobile App (`apps/mobile`)
- **Framework**: Expo SDK 54 + React Native 0.81
- **Language**: TypeScript 5.9+ (strict mode)
- **UI Library**: React Native Paper (Material Design 3)
- **Navigation**: React Navigation 7.x
- **State Management**: Zustand
- **Camera**: Expo Camera with document capture
- **PDF Viewer**: react-native-pdf

### Shared Package (`packages/shared`)
- **Services**: API client services shared between web and mobile
- **Types**: TypeScript type definitions
- **Hooks**: Shared React hooks
- **Stores**: Zustand store definitions

### Infrastructure
- **Deployment**: Docker Compose
- **Caching**: Redis
- **Message Broker**: Redis pub/sub for WebSocket broadcasting
- **Monorepo**: pnpm workspaces + Turborepo

## Quick Start

### Prerequisites

- Docker and Docker Compose
- **Ollama** installed and running (required for OCR and embeddings)
  - Install from: https://ollama.ai
  - Pull required models:
    ```bash
    ollama pull minicpm-v        # For vision OCR (recommended)
    ollama pull nomic-embed-text # For embeddings (recommended)
    ```
- At least 4GB RAM available for Docker
- Node.js 18+ and pnpm 8+ (for frontend development)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cartulary
   ```

2. **Copy environment files**:
   ```bash
   cp .env.example .env
   cp apps/backend/.env.example apps/backend/.env
   ```

3. **Configure Ollama connection**:
   ```bash
   # Edit .env and set LLM_BASE_URL to your Ollama instance
   # Default: http://localhost:11434
   # If Ollama is on a different host: http://your-ollama-host:11434
   ```

4. **Generate a secret key**:
   ```bash
   # Update the SECRET_KEY in .env
   openssl rand -hex 32
   ```

5. **Start the services**:
   ```bash
   docker compose up -d
   ```

6. **Run database migrations**:
   ```bash
   docker compose exec backend alembic upgrade head
   ```

7. **Access the application**:
   - Web Frontend: http://localhost:8080
   - API Documentation: http://localhost:8080/api/v1/docs

## Project Structure

```
cartulary/
├── apps/
│   ├── backend/              # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/       # API endpoints (including WebSocket)
│   │   │   ├── core/         # Security, permissions
│   │   │   ├── models/       # SQLAlchemy ORM models
│   │   │   ├── schemas/      # Pydantic schemas
│   │   │   ├── services/     # Business logic (OCR, embeddings, LLM)
│   │   │   ├── tasks/        # Celery tasks
│   │   │   └── workers/      # Background workers
│   │   ├── alembic/          # Database migrations
│   │   └── tests/            # Backend tests
│   │
│   ├── web/                  # React web frontend
│   │   └── src/
│   │       ├── components/   # React components (shadcn/ui)
│   │       ├── pages/        # Page components
│   │       └── services/     # API client
│   │
│   └── mobile/               # React Native mobile app
│       └── src/
│           ├── screens/      # Screen components
│           ├── navigation/   # React Navigation setup
│           ├── stores/       # Zustand stores
│           └── services/     # API client
│
├── packages/
│   └── shared/               # Shared TypeScript code
│       └── src/
│           ├── services/     # API services
│           ├── types/        # Type definitions
│           ├── hooks/        # React hooks
│           └── stores/       # Zustand stores
│
├── docker-compose.yml        # Development environment
├── docker-compose.prod.yml   # Production environment
├── pnpm-workspace.yaml       # pnpm workspace config
├── turbo.json                # Turborepo config
└── package.json              # Root package.json
```

## Development Setup

### Backend Development

```bash
cd apps/backend

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

### Web Frontend Development

```bash
# From project root
pnpm install

# Start all frontend apps in dev mode
pnpm dev

# Or start just the web app
cd apps/web
pnpm dev
```

### Mobile App Development

```bash
cd apps/mobile

# Install dependencies
pnpm install

# Start Expo development server
pnpm start

# Run on iOS Simulator
pnpm ios

# Run on Android Emulator
pnpm android
```

See [apps/mobile/README.md](apps/mobile/README.md) for detailed mobile setup instructions.

### Running Tests

```bash
# Backend tests
cd apps/backend
pytest

# Frontend type checking
pnpm type-check

# Frontend tests
cd apps/web
pnpm test
```

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
```

### Supported Architectures

- **linux/amd64** (x86_64)
- **linux/arm64** (ARM64/aarch64, including Apple Silicon)

### Production Deployment

Use the production docker-compose file with pre-built images:

```bash
# Pull latest images and start
docker compose -f docker-compose.prod.yml up -d
```

## Configuration

See [.env.example](.env.example) and [apps/backend/.env.example](apps/backend/.env.example) for all available configuration options.

### Key Configuration Options

#### Storage & Processing
- `STORAGE_TYPE`: `local` or `s3` for file storage
- `OCR_ENABLED`: Enable/disable OCR processing
- `VISION_OCR_MODEL`: Ollama vision model for OCR (default: `minicpm-v`)

#### Embeddings & Search
- `EMBEDDING_PROVIDER`: `ollama`, `local` (sentence-transformers), or `openai`
- `EMBEDDING_MODEL`: Model name (default: `nomic-embed-text` for Ollama)
- `EMBEDDING_DIMENSION`: Vector dimension (768 for nomic-embed-text, 384 for local, 1536 for OpenAI)

#### LLM Integration
- `LLM_ENABLED`: Enable optional LLM metadata extraction
- `LLM_PROVIDER`: `ollama`, `openai`, or `gemini`
- `LLM_MODEL`: Model name (e.g., `llama2`, `gpt-4`, `gemini-pro`)
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

#### Real-Time Updates
- `REDIS_URL`: Redis URL for WebSocket pub/sub and Celery (default: `redis://redis:6379/0`)

## Implementation Status

### ✅ Phase 1: Foundation
- [x] Project scaffolding (monorepo with pnpm + Turborepo)
- [x] Docker Compose setup
- [x] Database schema
- [x] Authentication system (JWT)
- [x] Basic document upload with deduplication

### ✅ Phase 2: OCR & Full-Text Search
- [x] Vision OCR integration (Ollama vision models - required)
- [x] PDF text extraction (PyMuPDF + LLM vision)
- [x] Background processing (Celery)
- [x] Full-text search (ILIKE-based)
- [x] Tag management (backend API + UI)
- [x] Search UI with results
- [x] Processing status display
- [x] Reprocess endpoint for failed documents

### ✅ Phase 3: Semantic Search
- [x] Embedding generation (Ollama, OpenAI, or local sentence-transformers)
- [x] Vector search (pgvector with cosine similarity)
- [x] Hybrid search (RRF combining FTS + semantic)
- [x] Search mode UI (Fulltext/Semantic/Hybrid)
- [x] Dimension validation on startup
- [x] Provider switching support (Ollama/OpenAI/local)

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
- [x] React Native mobile app (Expo)
- [x] Camera document capture

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

### Mobile App

The React Native mobile app provides:

- **Camera Capture**: Scan documents directly with your phone camera
- **Photo Library Import**: Import existing photos as documents
- **OIDC/SSO Support**: Enterprise authentication with PKCE flow
- **Offline-Ready Architecture**: Designed for future offline support
- **Native Performance**: Built with Expo and React Native for smooth UX

See [apps/mobile/README.md](apps/mobile/README.md) for mobile-specific documentation.

### OCR Optimization

The OCR system automatically optimizes processing for reliability and memory efficiency:

- **LLM Vision**: Uses Ollama vision models for accurate text extraction
- **Memory Management**: Celery workers limited to 4GB with automatic restarts
- **Enhanced Logging**: Detailed error tracking for failed OCR operations
- **Retry Logic**: Failed tasks automatically retry with exponential backoff

## Documentation

- [Development Guide (CLAUDE.md)](CLAUDE.md) - Comprehensive guide for development
- [Architecture (ARCHITECTURE.md)](ARCHITECTURE.md) - System architecture overview
- [Docker Guide (DOCKER.md)](DOCKER.md) - Docker development and deployment
- [Mobile App (apps/mobile/README.md)](apps/mobile/README.md) - Mobile app documentation
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
- Web frontend powered by [React](https://react.dev/) + [Vite](https://vitejs.dev/)
- Mobile app built with [Expo](https://expo.dev/) + [React Native](https://reactnative.dev/)
- Vision OCR powered by [Ollama](https://ollama.ai)
- Vector search with [pgvector](https://github.com/pgvector/pgvector)
- Real-time updates with [Redis](https://redis.io/)

## Troubleshooting

### WebSocket Connection Issues

If real-time updates aren't working:

1. Check Redis is running: `docker compose ps redis`
2. Verify WebSocket endpoint is accessible: Check browser console for connection errors
3. Ensure JWT token is valid: WebSocket authentication uses the same token as API calls

### Celery Worker Memory Issues

If workers are being killed (OOM):

1. Check memory limits in [docker-compose.yml](docker-compose.yml)
2. Reduce `CELERY_CONCURRENCY` if processing very large images
3. Monitor with: `docker stats cartulary-celery-worker`

### OCR Processing Failures

If OCR consistently fails on specific files:

1. Check Celery worker logs: `docker compose logs celery_worker`
2. Verify Ollama is running and the vision model is pulled
3. Check file size - very large images may need manual resizing
4. Try reprocessing: Click "Reprocess OCR" in document details

### Mobile App Connection Issues

1. Ensure backend is accessible from your device's network
2. For Android emulator, use `http://10.0.2.2:8000` as API URL
3. For physical device, use your computer's local IP address
4. Check Settings screen in the app to verify API URL

---

**Version**: 0.7.0 (Phase 7 Complete)
**Status**: In Active Development
