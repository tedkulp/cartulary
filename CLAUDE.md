# Claude Code Assistant - Trapper Project Guide

This document contains context, conventions, and best practices for working on the Trapper document management system with Claude Code.

## Project Overview

**Trapper** is a document management system similar to paperless-ngx with advanced features:
- OCR processing with PaddleOCR
- Semantic search using RAG (Retrieval Augmented Generation)
- Optional LLM-based metadata extraction (OpenAI, Gemini, Ollama)
- Multi-user support with RBAC
- Automated import from directories and IMAP mailboxes

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with pgvector extension
- **ORM**: SQLAlchemy 2.0+ (async where possible)
- **Migrations**: Alembic
- **Task Queue**: Celery with Redis broker
- **OCR**: PaddleOCR
- **Embeddings**: sentence-transformers (local) + OpenAI API (optional)
- **Storage**: Local filesystem with optional S3/MinIO support

### Frontend
- **Framework**: Vue 3 (Composition API) with TypeScript
- **Build Tool**: Vite
- **State Management**: Pinia
- **Styling**: Tailwind CSS
- **UI Library**: PrimeVue
- **PDF Viewer**: vue-pdf-embed (PDF.js wrapper)

### Infrastructure
- **Deployment**: Docker Compose
- **Caching**: Redis
- **Authentication**: JWT + optional OIDC

## Project Structure

```
trapper/
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   ├── api/v1/      # API endpoints (versioned)
│   │   ├── core/        # Security, permissions, exceptions
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── schemas/     # Pydantic request/response schemas
│   │   ├── services/    # Business logic layer
│   │   ├── tasks/       # Celery tasks
│   │   ├── workers/     # Long-running background workers
│   │   └── utils/       # Helper utilities
│   ├── alembic/         # Database migrations
│   └── tests/           # Pytest tests
│
├── frontend/            # Vue 3 frontend
│   ├── src/
│   │   ├── components/  # Reusable Vue components
│   │   ├── views/       # Page-level components
│   │   ├── stores/      # Pinia state management
│   │   ├── services/    # API client services
│   │   ├── router/      # Vue Router
│   │   └── types/       # TypeScript type definitions
│   └── public/
│
└── docker-compose.yml   # Development environment
```

## Coding Conventions

### Backend (Python)

#### General Style
- Follow PEP 8 with line length of 100 characters
- Use type hints for all function signatures
- Prefer async/await for I/O operations
- Use Pydantic for all configuration and validation

#### File Organization
```python
# Standard library imports
import os
from typing import Optional

# Third-party imports
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.models.document import Document
from app.schemas.document import DocumentCreate
```

#### Naming Conventions
- **Files**: `snake_case.py` (e.g., `document_service.py`)
- **Classes**: `PascalCase` (e.g., `DocumentService`)
- **Functions/Variables**: `snake_case` (e.g., `process_document`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`)
- **Private members**: Prefix with `_` (e.g., `_internal_method`)

#### Database Models
```python
# Use declarative base with type hints
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships use lazy="selectin" for async compatibility
    owner: Mapped["User"] = relationship("User", lazy="selectin")
```

#### Service Layer Pattern
- Keep business logic in `services/` not in API routes
- Services should be dependency-injectable
- Services handle transactions and complex operations

```python
class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    async def create_document(
        self,
        file: UploadFile,
        user_id: uuid.UUID
    ) -> Document:
        # Business logic here
        pass
```

#### API Endpoints
- Use versioned API routes (`/api/v1/`)
- Return Pydantic schemas, not ORM models
- Use proper HTTP status codes
- Include OpenAPI documentation

```python
@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document",
    description="Upload and process a PDF or image file"
)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Upload and process a document."""
    return await doc_service.create_document(file, current_user.id)
```

### Frontend (TypeScript/Vue)

#### General Style
- Use TypeScript strict mode
- Prefer Composition API over Options API
- Use `<script setup>` syntax for components
- Follow Vue 3 style guide

#### Component Structure
```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Document } from '@/types/document'

// Props
const props = defineProps<{
  documentId: string
}>()

// Emits
const emit = defineEmits<{
  updated: [document: Document]
  deleted: [id: string]
}>()

// State
const document = ref<Document | null>(null)

// Computed
const isLoaded = computed(() => document.value !== null)

// Methods
const loadDocument = async () => {
  // Implementation
}

// Lifecycle
onMounted(() => {
  loadDocument()
})
</script>

<template>
  <div class="document-viewer">
    <!-- Template content -->
  </div>
</template>

<style scoped>
/* Component-specific styles */
</style>
```

#### Naming Conventions
- **Files**: `PascalCase.vue` for components (e.g., `DocumentCard.vue`)
- **Composables**: `camelCase.ts` with `use` prefix (e.g., `useDocuments.ts`)
- **Stores**: `camelCase.ts` (e.g., `documentStore.ts`)
- **Types**: `camelCase.ts` (e.g., `document.ts`)

#### State Management (Pinia)
```typescript
export const useDocumentStore = defineStore('documents', () => {
  // State
  const documents = ref<Document[]>([])
  const currentDocument = ref<Document | null>(null)

  // Getters (computed)
  const documentCount = computed(() => documents.value.length)

  // Actions
  const fetchDocuments = async () => {
    const data = await documentService.list()
    documents.value = data
  }

  return {
    documents,
    currentDocument,
    documentCount,
    fetchDocuments
  }
})
```

#### API Services
- Keep API calls in `services/` not in components
- Use axios with proper error handling
- Return typed responses

```typescript
export const documentService = {
  async list(filters?: DocumentFilters): Promise<Document[]> {
    const { data } = await api.get<Document[]>('/documents', { params: filters })
    return data
  },

  async upload(file: File, metadata?: DocumentMetadata): Promise<Document> {
    const formData = new FormData()
    formData.append('file', file)
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata))
    }
    const { data } = await api.post<Document>('/documents', formData)
    return data
  }
}
```

## Key Design Patterns

### 1. Service Layer (Backend)
- **Why**: Separates business logic from API routes
- **When**: All complex operations (document processing, search, etc.)
- **Example**: `DocumentService`, `SearchService`, `OCRService`

### 2. Repository Pattern (Backend)
- **Why**: Abstracts data access, makes testing easier
- **When**: Complex queries, reusable data operations
- **Example**: `DocumentRepository` for database queries

### 3. Strategy Pattern (Backend)
- **Why**: Allows swapping implementations (storage, embeddings, LLMs)
- **When**: Multiple provider support (local vs. S3, OpenAI vs. Ollama)
- **Example**: `StorageBackend` abstract class with `LocalStorage` and `S3Storage`

### 4. Composition API + Composables (Frontend)
- **Why**: Reusable logic, better TypeScript support
- **When**: Shared stateful logic across components
- **Example**: `useDocuments()`, `useSearch()`, `useAuth()`

## Testing Strategy

### Backend Tests
```python
# tests/test_services/test_document_service.py
import pytest
from app.services.document_service import DocumentService

@pytest.mark.asyncio
async def test_create_document(db_session, mock_file):
    """Test document creation."""
    service = DocumentService(db_session)
    doc = await service.create_document(mock_file, user_id=UUID)

    assert doc.id is not None
    assert doc.title == "test.pdf"
    assert doc.processing_status == "pending"
```

### Frontend Tests
```typescript
// tests/components/DocumentCard.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentCard from '@/components/documents/DocumentCard.vue'

describe('DocumentCard', () => {
  it('renders document title', () => {
    const wrapper = mount(DocumentCard, {
      props: {
        document: {
          id: '123',
          title: 'Test Document'
        }
      }
    })
    expect(wrapper.text()).toContain('Test Document')
  })
})
```

## Common Patterns

### 1. Document Upload Flow
```python
# 1. API Endpoint receives file
# 2. Calculate checksum
checksum = await calculate_checksum(file)

# 3. Check for duplicates
existing = await document_repo.get_by_checksum(checksum)
if existing:
    raise HTTPException(status_code=409, detail={
        "error": "duplicate",
        "document_id": str(existing.id)
    })

# 4. Store file
file_path = await storage.save(file)

# 5. Create DB record
document = await document_repo.create(...)

# 6. Trigger async processing
process_document.delay(document.id)
```

### 2. Hybrid Search
```python
# Execute both searches in parallel
async with asyncio.TaskGroup() as tg:
    fts_task = tg.create_task(full_text_search(query))
    vec_task = tg.create_task(vector_search(query))

fts_results = await fts_task
vec_results = await vec_task

# Combine with Reciprocal Rank Fusion
combined = reciprocal_rank_fusion(fts_results, vec_results, k=60)
```

### 3. Error Handling (Frontend)
```typescript
const uploadDocument = async (file: File) => {
  try {
    const doc = await documentService.upload(file)
    toast.success('Document uploaded successfully')
    return doc
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 409) {
        // Handle duplicate
        const existingId = error.response.data.document_id
        toast.warning('Document already exists')
        router.push(`/documents/${existingId}`)
      } else {
        toast.error(error.response?.data?.message || 'Upload failed')
      }
    }
  }
}
```

## Environment Configuration

### Required Environment Variables

**Backend (.env)**
```bash
# Database
DATABASE_URL=postgresql://trapper:password@postgres:5432/trapper

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Storage
STORAGE_TYPE=local  # or s3
LOCAL_STORAGE_PATH=/data/documents

# OCR
OCR_ENABLED=true
OCR_LANGUAGES=["en"]
PADDLEOCR_USE_GPU=false

# Embeddings
EMBEDDING_PROVIDER=local  # or openai
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# LLM (Optional)
LLM_ENABLED=false
LLM_PROVIDER=ollama  # openai, gemini, ollama
LLM_MODEL=llama2
LLM_BASE_URL=http://localhost:11434

# Auth
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OIDC (Optional)
OIDC_ENABLED=false
```

**Frontend (.env)**
```bash
VITE_API_URL=http://localhost:8000
```

## Database Migrations

### Creating a Migration
```bash
# Auto-generate migration from model changes
cd backend
alembic revision --autogenerate -m "Add document_embeddings table"

# Review the generated migration in alembic/versions/
# Edit if needed, then apply:
alembic upgrade head
```

### Migration Best Practices
- Always review auto-generated migrations
- Add indexes in separate operations for large tables
- Use `batch_op` for SQLite compatibility (if needed)
- Test migrations on a copy of production data
- Include both `upgrade()` and `downgrade()`

## Git Commit Strategy

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates
- `build`: Build system or external dependencies

**Examples:**
```
feat(backend): implement document upload with deduplication

- Add DocumentService.create_document() method
- Calculate SHA-256 checksum on upload
- Return 409 Conflict for duplicates
- Store files in local storage

Closes #123
```

```
feat(frontend): add document upload component

- Create DocumentUpload.vue with drag-and-drop
- Integrate with upload API endpoint
- Add progress tracking
- Handle duplicate error response
```

### Commit Frequency

**IMPORTANT: Only commit after completing major sections of work. DO NOT commit after every small bug fix or minor change.**

**When to commit:**
- ✅ After completing a full section of the implementation plan (e.g., Phase 1, Phase 2)
- ✅ After implementing a complete feature end-to-end (backend + frontend + tests)
- ✅ After a major refactoring is complete
- ✅ At logical stopping points that represent significant progress

**When NOT to commit:**
- ❌ After fixing individual bugs during development
- ❌ After making small adjustments or corrections
- ❌ After fixing linting or formatting issues
- ❌ In the middle of implementing a feature

**Philosophy:**
Work should be batched into meaningful commits that represent completed units of work. Bug fixes and corrections made during development should be included in the commit for the feature being worked on, not committed separately.

**Example commit sequence for Phase 1:**
```bash
1. chore: initialize project structure and docker-compose
2. build(backend): set up FastAPI with basic configuration
3. build(frontend): initialize Vue 3 project with Vite and Tailwind
4. feat(backend): add database models and initial migration
5. feat(backend): implement JWT authentication
6. feat(frontend): create login page and auth store
7. feat(backend): add document upload endpoint with local storage
8. feat(frontend): create document upload component
9. test: add tests for authentication and upload
10. docs: update README with setup instructions
```

## Common Tasks

**IMPORTANT: DO NOT run `docker compose up` or `docker compose build` commands. The user will handle Docker operations manually.**

### Run Backend Locally (outside Docker)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Run Frontend Locally
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run test
npm run test:e2e
```

### Create Database Migration
```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Restart Celery Worker
Note: User will handle Docker operations manually.

## Troubleshooting

### pgvector Extension Not Found
```sql
-- Connect to database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### OCR Processing Slow
- Consider using GPU version of PaddlePaddle
- Reduce OCR quality settings in config
- Process documents in batches

### Out of Memory (Embeddings)
- Reduce embedding batch size
- Use smaller embedding model (all-MiniLM-L6-v2 instead of all-mpnet-base-v2)
- Process fewer chunks per document

### Frontend Build Errors
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## Performance Optimization

### Database
- Use `selectinload()` for relationships to avoid N+1 queries
- Create indexes on frequently filtered columns
- Use database connection pooling
- Consider read replicas for search-heavy workloads

### Celery Tasks
- Set appropriate concurrency limits
- Use task routing for different queue priorities
- Monitor task execution time
- Implement retry logic with exponential backoff

### Frontend
- Lazy load routes with dynamic imports
- Use virtual scrolling for large lists
- Implement proper pagination
- Cache API responses when appropriate
- Use web workers for heavy computations

## Security Checklist

- [ ] Use environment variables for secrets
- [ ] Validate all user inputs with Pydantic
- [ ] Sanitize file names before storage
- [ ] Implement rate limiting on API endpoints
- [ ] Use HTTPS in production
- [ ] Set secure headers (CORS, CSP, etc.)
- [ ] Hash passwords with bcrypt
- [ ] Use short-lived JWT tokens with refresh
- [ ] Implement CSRF protection
- [ ] Scan uploaded files for malware (optional)
- [ ] Use prepared statements (SQLAlchemy ORM)
- [ ] Implement proper error handling (don't leak info)

## Resources

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- Vue 3: https://vuejs.org/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- Pinia: https://pinia.vuejs.org/
- PrimeVue: https://primevue.org/
- pgvector: https://github.com/pgvector/pgvector

### Key Dependencies
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- sentence-transformers: https://www.sbert.net/
- LangChain: https://python.langchain.com/

## Implementation Plan Reference

For detailed implementation phases, see: [.claude/plans/deep-sprouting-volcano.md](.claude/plans/deep-sprouting-volcano.md)

## Notes for Future Claude Sessions

### Context to Provide
When starting a new session, provide:
1. Current phase of implementation
2. Recent changes made
3. Current blockers or issues
4. Next planned feature/task

### Key Project Decisions
- **OCR Strategy**: Always create OCR'd PDF with embedded text layer
- **Deduplication**: Block duplicate uploads via SHA-256 checksum
- **Search**: Hybrid approach combining FTS and semantic search with RRF
- **Storage**: Support both local filesystem and S3-compatible storage
- **LLM**: All LLM features are optional and configurable

### Areas Requiring Special Attention
- **Vector embeddings**: Dimension must match model (384 for local, 1536 for OpenAI)
- **Async operations**: Use async/await consistently in backend
- **Error handling**: Provide user-friendly messages, log detailed errors
- **Testing**: Maintain test coverage above 80%
- **Performance**: Monitor OCR and embedding generation time

---

Last Updated: 2025-12-21
Project Version: 0.1.0 (Phase 1 - Planning)
