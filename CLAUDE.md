# Claude Code Assistant - Cartulary Project Guide

This document contains context, conventions, and best practices for working on the Cartulary digital archive system with Claude Code.

## Project Overview

**Cartulary** is a digital archive system similar to paperless-ngx with advanced features:
- Vision-based OCR using Ollama (minicpm-v, llava, gemma3)
- Semantic search using RAG (Retrieval Augmented Generation)
- LLM-based metadata extraction (Ollama, OpenAI, Gemini)
- Multi-user support with RBAC
- Automated import from directories and IMAP mailboxes
- Cross-platform: Web app + native iOS/Android mobile app

## Technology Stack

### Backend (`apps/backend`)
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with pgvector extension
- **ORM**: SQLAlchemy 2.0+ (async where possible)
- **Migrations**: Alembic
- **Task Queue**: Celery with Redis broker
- **OCR**: Ollama vision models (minicpm-v, llava, gemma3)
- **Embeddings**: Ollama (nomic-embed-text), sentence-transformers (local), or OpenAI API
- **Storage**: Local filesystem with optional S3/MinIO support

### Web Frontend (`apps/web`)
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **State Management**: Zustand
- **Styling**: Tailwind CSS
- **UI Components**: Radix UI + shadcn/ui
- **PDF Viewer**: react-pdf (PDF.js wrapper)

### Mobile App (`apps/mobile`)
- **Framework**: Expo SDK 54 + React Native 0.81
- **Language**: TypeScript 5.9+ (strict mode)
- **UI Library**: React Native Paper (Material Design 3)
- **Navigation**: React Navigation 7.x
- **State Management**: Zustand
- **Camera**: Expo Camera

### Shared Package (`packages/shared`)
- **Purpose**: Shared TypeScript code between web and mobile
- **Contents**: API services, types, hooks, Zustand stores
- **Build**: tsup for bundling

### Infrastructure
- **Monorepo**: pnpm workspaces + Turborepo
- **Deployment**: Docker Compose
- **Caching**: Redis
- **Authentication**: JWT + optional OIDC

## Project Structure

```
cartulary/
├── apps/
│   ├── backend/              # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/       # API endpoints (versioned)
│   │   │   ├── core/         # Security, permissions, exceptions
│   │   │   ├── models/       # SQLAlchemy ORM models
│   │   │   ├── schemas/      # Pydantic request/response schemas
│   │   │   ├── services/     # Business logic layer
│   │   │   ├── tasks/        # Celery tasks
│   │   │   ├── workers/      # Long-running background workers
│   │   │   └── utils/        # Helper utilities
│   │   ├── alembic/          # Database migrations
│   │   └── tests/            # Pytest tests
│   │
│   ├── web/                  # React web frontend
│   │   ├── src/
│   │   │   ├── components/   # React components
│   │   │   │   └── ui/       # shadcn/ui components
│   │   │   ├── pages/        # Page components
│   │   │   ├── services/     # API client
│   │   │   └── lib/          # Utilities
│   │   └── public/
│   │
│   └── mobile/               # React Native mobile app
│       ├── src/
│       │   ├── screens/      # Screen components
│       │   ├── components/   # Reusable components
│       │   ├── navigation/   # React Navigation setup
│       │   ├── stores/       # Zustand stores
│       │   ├── services/     # API client
│       │   ├── types/        # TypeScript types
│       │   ├── config/       # App configuration
│       │   └── utils/        # Utilities
│       └── assets/
│
├── packages/
│   └── shared/               # Shared TypeScript code
│       └── src/
│           ├── services/     # API services (auth, documents, etc.)
│           ├── types/        # Shared type definitions
│           ├── hooks/        # React hooks
│           ├── stores/       # Zustand store definitions
│           └── utils/        # Shared utilities
│
├── docker-compose.yml        # Development environment
├── docker-compose.prod.yml   # Production environment
├── pnpm-workspace.yaml       # pnpm workspace config
├── turbo.json                # Turborepo config
└── package.json              # Root package.json
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

### Frontend (TypeScript/React)

#### General Style
- Use TypeScript strict mode
- Use functional components with hooks
- Follow React best practices

#### Component Structure (Web - React)
```tsx
import { useState, useEffect } from 'react'
import { Document } from '@cartulary/shared'

interface DocumentCardProps {
  document: Document
  onUpdate?: (doc: Document) => void
  onDelete?: (id: string) => void
}

export function DocumentCard({ document, onUpdate, onDelete }: DocumentCardProps) {
  const [isLoading, setIsLoading] = useState(false)

  // Component logic here

  return (
    <div className="document-card">
      {/* Template content */}
    </div>
  )
}
```

#### Component Structure (Mobile - React Native)
```tsx
import React from 'react'
import { View, StyleSheet } from 'react-native'
import { Card, Text } from 'react-native-paper'
import type { Document } from '@/types/api'

interface DocumentCardProps {
  document: Document
  onPress?: () => void
}

export function DocumentCard({ document, onPress }: DocumentCardProps) {
  return (
    <Card onPress={onPress} style={styles.card}>
      <Card.Title title={document.title} />
      <Card.Content>
        <Text>{document.filename}</Text>
      </Card.Content>
    </Card>
  )
}

const styles = StyleSheet.create({
  card: {
    marginVertical: 8,
  },
})
```

#### Naming Conventions
- **Files**: `PascalCase.tsx` for components (e.g., `DocumentCard.tsx`)
- **Hooks**: `camelCase.ts` with `use` prefix (e.g., `useDocuments.ts`)
- **Stores**: `camelCase.ts` (e.g., `authStore.ts`)
- **Types**: `camelCase.ts` (e.g., `document.ts`)
- **Services**: `camelCase.service.ts` (e.g., `document.service.ts`)

#### State Management (Zustand)
```typescript
import { create } from 'zustand'
import { Document } from '@cartulary/shared'

interface DocumentState {
  documents: Document[]
  currentDocument: Document | null
  loading: boolean
  error: string | null
  fetchDocuments: () => Promise<void>
}

export const useDocumentStore = create<DocumentState>((set) => ({
  documents: [],
  currentDocument: null,
  loading: false,
  error: null,
  fetchDocuments: async () => {
    set({ loading: true, error: null })
    try {
      const data = await documentService.list()
      set({ documents: data, loading: false })
    } catch (err) {
      set({ error: 'Failed to fetch documents', loading: false })
    }
  },
}))
```

#### API Services
- Keep API calls in `services/` not in components
- Use axios with proper error handling
- Return typed responses

```typescript
import { api } from './api'
import type { Document, DocumentFilters } from '@cartulary/shared'

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

### 4. Shared Package Pattern (Frontend)
- **Why**: Code reuse between web and mobile apps
- **When**: API services, types, business logic
- **Example**: `@cartulary/shared` package with services and types

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

### Frontend Tests (Web)
```typescript
// tests/components/DocumentCard.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DocumentCard } from '@/components/DocumentCard'

describe('DocumentCard', () => {
  it('renders document title', () => {
    render(
      <DocumentCard
        document={{
          id: '123',
          title: 'Test Document',
          filename: 'test.pdf',
        }}
      />
    )
    expect(screen.getByText('Test Document')).toBeInTheDocument()
  })
})
```

## Environment Configuration

### Required Environment Variables

**Backend (.env)**
```bash
# Database
DATABASE_URL=postgresql://cartulary:password@postgres:5432/cartulary

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Storage
STORAGE_TYPE=local  # or s3
LOCAL_STORAGE_PATH=/data/documents

# Ollama (Required for OCR and embeddings)
LLM_BASE_URL=http://localhost:11434

# Vision OCR (Required - uses Ollama)
OCR_ENABLED=true
VISION_OCR_MODEL=minicpm-v  # or llava, gemma3:4b-it-q4_K_M

# Embeddings (Uses Ollama by default)
EMBEDDING_ENABLED=true
EMBEDDING_PROVIDER=ollama  # ollama, openai, or local
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768

# LLM Metadata Extraction (Optional)
LLM_ENABLED=false
LLM_PROVIDER=ollama  # ollama, openai, gemini
LLM_MODEL=llama2

# Auth
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# OIDC (Optional)
OIDC_ENABLED=false
OIDC_DISCOVERY_URL=https://auth.example.com/.well-known/openid-configuration
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URI=http://localhost:8080/auth/callback
OIDC_SCOPES=["openid","profile","email"]
OIDC_AUTO_PROVISION_USERS=true
OIDC_DEFAULT_ROLE=user
```

**Frontend (.env.local)**
```bash
VITE_API_URL=http://localhost:8000
```

## Database Migrations

### Creating a Migration
```bash
# Auto-generate migration from model changes
cd apps/backend
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
feat(web): add document upload component

- Create UploadDialog with drag-and-drop
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

## Common Tasks

**IMPORTANT: DO NOT run `docker compose up` or `docker compose build` commands. The user will handle Docker operations manually.**

### Run Backend Locally (outside Docker)
```bash
cd apps/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Run Frontend Locally
```bash
# From project root
pnpm install
pnpm dev

# Or just web
cd apps/web
pnpm dev
```

### Run Mobile App
```bash
cd apps/mobile
pnpm install
pnpm start  # Start Expo dev server
pnpm ios    # Run on iOS Simulator
pnpm android # Run on Android Emulator
```

### Run Tests
```bash
# Backend
cd apps/backend
pytest

# Frontend type checking
pnpm type-check
```

### Create Database Migration
```bash
cd apps/backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Build Shared Package
```bash
cd packages/shared
pnpm build
```

## Troubleshooting

### pgvector Extension Not Found
```sql
-- Connect to database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### Vision OCR Processing Slow
- Use a faster Ollama vision model (minicpm-v is faster than llava:13b)
- Ensure Ollama has adequate CPU/GPU resources
- Reduce image resolution in ocr_service.py (lower the Matrix scale factor)
- Increase Celery concurrency if you have multiple CPU cores

### Out of Memory (Embeddings)
- Use Ollama embeddings (offloads to external service)
- If using local embeddings, reduce batch size
- Use smaller embedding model (all-MiniLM-L6-v2: 384 dims instead of nomic-embed-text: 768 dims)
- Process fewer chunks per document

### Frontend Build Errors
```bash
# Clear node_modules and reinstall
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### Mobile App Issues
```bash
# Clear Expo cache
cd apps/mobile
pnpm start --clear

# Reinstall dependencies
rm -rf node_modules
pnpm install
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
- React: https://react.dev/
- React Native: https://reactnative.dev/
- Expo: https://docs.expo.dev/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- Zustand: https://zustand-demo.pmnd.rs/
- Tailwind CSS: https://tailwindcss.com/
- React Native Paper: https://callstack.github.io/react-native-paper/
- pgvector: https://github.com/pgvector/pgvector

### Key Dependencies
- Ollama: https://ollama.ai (Required for OCR and embeddings)
- sentence-transformers: https://www.sbert.net/ (Optional, for local embeddings)
- OpenAI API: https://platform.openai.com/ (Optional, for embeddings/LLM)

## Implementation Plan

**Current Status**: Phase 7 Complete
**Next Phase**: Phase 8 - Testing & Production

The plan outlines 8 phases:
1. **Phase 1: Foundation** - Core infrastructure, auth, basic document upload
2. **Phase 2: OCR & Full-Text Search** - Ollama vision OCR, PostgreSQL FTS
3. **Phase 3: Semantic Search (RAG)** - Vector embeddings (Ollama), pgvector, hybrid search
4. **Phase 4: LLM Integration** - Metadata extraction, auto-tagging (Ollama/OpenAI/Gemini)
5. **Phase 5: Multi-User & Permissions** - RBAC, document sharing
6. **Phase 6: Import Sources** - Directory watching, IMAP integration
7. **Phase 7: OIDC & Polish** - Enterprise auth, mobile app, UI improvements
8. **Phase 8: Testing & Production** - Comprehensive testing, deployment

## Notes for Future Claude Sessions

### Context to Provide
When starting a new session, provide:
1. Current phase of implementation
2. Recent changes made
3. Current blockers or issues
4. Next planned feature/task

### Key Project Decisions
- **OCR Strategy**: LLM vision-based OCR using Ollama (required dependency)
- **Deduplication**: Block duplicate uploads via SHA-256 checksum
- **Search**: Hybrid approach combining FTS and semantic search with RRF
- **Storage**: Support both local filesystem and S3-compatible storage
- **Embeddings**: Ollama by default (nomic-embed-text), with OpenAI/local fallback
- **LLM Metadata**: Optional feature using Ollama/OpenAI/Gemini
- **OIDC**: Enterprise SSO support with auto-provisioning, works alongside JWT auth
- **Mobile**: React Native with Expo for iOS/Android support

### Areas Requiring Special Attention
- **Ollama dependency**: OCR and embeddings require Ollama running and accessible
- **Vector embeddings**: Dimension must match model (768 for nomic-embed-text, 384 for local, 1536 for OpenAI)
- **Vision models**: Ensure Ollama has the vision model pulled (minicpm-v, llava, gemma3)
- **Async operations**: Use async/await consistently in backend
- **Error handling**: Provide user-friendly messages, log detailed errors
- **Testing**: Maintain test coverage above 80%
- **Performance**: Monitor vision OCR and embedding generation time
- **Mobile**: Test on both iOS and Android platforms

---

Last Updated: 2026-01-26
Project Version: 0.7.0 (Phase 7 Complete - Mobile App, Ollama Vision OCR)
