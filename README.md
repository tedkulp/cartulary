# Trapper

A modern document management system with OCR processing, semantic search, and AI-powered metadata extraction.

## Features

- **Document Management**: Upload, organize, and manage PDF files and images
- **OCR Processing**: Automatic text extraction using PaddleOCR
- **Semantic Search**: RAG-powered search with vector embeddings
- **AI Metadata Extraction**: Automatic tagging, categorization, and metadata extraction using LLMs (OpenAI, Gemini, Ollama)
- **Multi-User Support**: Role-based access control and document sharing
- **Multiple Import Methods**:
  - Manual upload via web interface
  - Directory watching for automatic import
  - IMAP mailbox monitoring
- **Optional OIDC Authentication**: Enterprise SSO support

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with pgvector extension
- **Task Queue**: Celery + Redis
- **OCR**: PaddleOCR
- **Embeddings**: sentence-transformers (local) or OpenAI API
- **Storage**: Local filesystem or S3-compatible (MinIO)

### Frontend
- **Framework**: Vue 3 (Composition API) + TypeScript
- **Build Tool**: Vite
- **UI**: Tailwind CSS + PrimeVue
- **PDF Viewer**: PDF.js (vue-pdf-embed)

### Infrastructure
- **Deployment**: Docker Compose
- **Caching**: Redis

## Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 4GB RAM available for Docker

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd trapper
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
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/v1/docs

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
trapper/
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   ├── api/v1/      # API endpoints
│   │   ├── core/        # Security, permissions
│   │   ├── models/      # Database models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic
│   │   ├── tasks/       # Celery tasks
│   │   └── workers/     # Background workers
│   ├── alembic/         # Database migrations
│   └── tests/           # Tests
├── frontend/            # Vue 3 frontend
│   └── src/
│       ├── components/  # Vue components
│       ├── views/       # Page components
│       ├── stores/      # Pinia stores
│       └── services/    # API services
├── docker-compose.yml   # Development environment
└── CLAUDE.md           # Development guide for Claude Code
```

## Configuration

See [.env.example](.env.example) and [backend/.env.example](backend/.env.example) for all available configuration options.

### Key Configuration Options

- `STORAGE_TYPE`: `local` or `s3` for file storage
- `OCR_ENABLED`: Enable/disable OCR processing
- `EMBEDDING_PROVIDER`: `local` (sentence-transformers) or `openai`
- `LLM_ENABLED`: Enable optional LLM features
- `LLM_PROVIDER`: `openai`, `gemini`, or `ollama`
- `OIDC_ENABLED`: Enable OIDC authentication

## Implementation Status

### ✅ Phase 1: Foundation (Current)
- [x] Project scaffolding
- [x] Docker Compose setup
- [x] Database schema
- [ ] Authentication system
- [ ] Basic document upload

### 🔲 Phase 2: OCR & Full-Text Search
- [ ] OCR integration
- [ ] Full-text search
- [ ] Tag management

### 🔲 Phase 3: Semantic Search
- [ ] Embedding generation
- [ ] Vector search
- [ ] Hybrid search

### 🔲 Phase 4: LLM Integration
- [ ] Metadata extraction
- [ ] Auto-tagging

### 🔲 Phase 5: Multi-User & Permissions
- [ ] RBAC
- [ ] Document sharing

### 🔲 Phase 6: Import Sources
- [ ] Directory watching
- [ ] IMAP integration

### 🔲 Phase 7: OIDC & Polish
- [ ] OIDC authentication
- [ ] UI polish

### 🔲 Phase 8: Production Ready
- [ ] Testing
- [ ] Performance optimization
- [ ] Documentation

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
- OCR by [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- Vector search with [pgvector](https://github.com/pgvector/pgvector)

---

**Version**: 0.1.0 (Phase 1 - Scaffolding)
**Status**: In Development
