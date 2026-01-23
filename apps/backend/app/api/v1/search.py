"""Search API endpoints."""
from typing import List
from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.search_service import SearchService
from app.services.vector_search_service import VectorSearchService

router = APIRouter(prefix="/search", tags=["search"])


class SearchMode(str, Enum):
    """Search mode enum."""

    FULLTEXT = "fulltext"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchResult(BaseModel):
    """Search result with document and score."""

    document: DocumentResponse
    score: float
    highlights: List[str] = []
    matched_chunk: str | None = None


def get_search_service(db: Session = Depends(get_db)) -> SearchService:
    """Dependency to get search service."""
    return SearchService(db)


def get_vector_search_service(db: Session = Depends(get_db)) -> VectorSearchService:
    """Dependency to get vector search service."""
    return VectorSearchService(db)


@router.get("", response_model=List[DocumentResponse])
async def search_documents(
    q: str = Query(..., description="Search query"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records"),
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> List[DocumentResponse]:
    """
    Search documents by title, filename, or content.

    - **q**: Search query string
    - **skip**: Pagination offset
    - **limit**: Maximum number of results
    """
    return search_service.search_documents(
        query=q, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get("/count", response_model=dict)
async def count_search_results(
    q: str = Query(..., description="Search query"),
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> dict:
    """
    Get count of search results.

    - **q**: Search query string
    """
    count = search_service.count_search_results(query=q, user_id=current_user.id)
    return {"query": q, "count": count}


@router.get("/advanced", response_model=List[SearchResult])
async def advanced_search(
    q: str = Query(..., description="Search query"),
    mode: SearchMode = Query(SearchMode.HYBRID, description="Search mode"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    similarity_threshold: float = Query(
        0.3, 
        ge=0.0, 
        le=1.0, 
        description="Minimum similarity score (0-1) for semantic/hybrid search. 0.3=default, 0.5=stricter, 0.0=no filter"
    ),
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
) -> List[SearchResult]:
    """
    Advanced search with multiple modes: fulltext, semantic, or hybrid.

    - **q**: Search query string
    - **mode**: Search mode (fulltext, semantic, or hybrid)
    - **limit**: Maximum number of results
    - **similarity_threshold**: Minimum relevance score (0-1). Higher = stricter filtering.
      - 0.0: No filtering (return all results)
      - 0.3: Default (filters out irrelevant results)
      - 0.5: Strict (only fairly relevant results)
      - 0.7: Very strict (only highly relevant results)

    Modes:
    - **fulltext**: Traditional keyword search (fast, exact matching)
    - **semantic**: Vector similarity search (understands meaning)
    - **hybrid**: Combines both methods using Reciprocal Rank Fusion (best quality)
    """
    search_results = []

    if mode == SearchMode.SEMANTIC:
        # Pure semantic search
        results = vector_search_service.vector_search(
            q, current_user.id, limit=limit, similarity_threshold=similarity_threshold
        )
        # results is List[Tuple[Document, float, str]]
        for doc, score, chunk_text in results:
            highlights = []
            if chunk_text:
                # Truncate chunk if too long for display and highlight terms
                display_chunk = chunk_text[:300] + "..." if len(chunk_text) > 300 else chunk_text
                display_chunk = search_service._highlight_terms(display_chunk, q.split())
                highlights.append(display_chunk)
            
            search_results.append(
                SearchResult(
                    document=DocumentResponse.model_validate(doc),
                    score=score,
                    highlights=highlights,
                    matched_chunk=chunk_text
                )
            )

    elif mode == SearchMode.HYBRID:
        # Hybrid search with RRF
        results = vector_search_service.hybrid_search(
            q, current_user.id, limit=limit, similarity_threshold=similarity_threshold
        )
        # results is List[Tuple[Document, float, Optional[str]]]
        for doc, score, chunk_text in results:
            highlights = []
            
            # Add semantic chunk if available (with highlighting)
            if chunk_text:
                display_chunk = chunk_text[:300] + "..." if len(chunk_text) > 300 else chunk_text
                display_chunk = search_service._highlight_terms(display_chunk, q.split())
                highlights.append(display_chunk)
            
            # Add keyword snippet from OCR text (already highlighted by extract_snippet)
            if doc.ocr_text:
                snippets = search_service.extract_snippet(doc.ocr_text, q, context_chars=150, max_snippets=1)
                highlights.extend(snippets)
            
            search_results.append(
                SearchResult(
                    document=DocumentResponse.model_validate(doc),
                    score=score,
                    highlights=highlights,
                    matched_chunk=chunk_text
                )
            )

    else:
        # Full-text search (default)
        docs = search_service.search_documents(q, current_user.id, skip=0, limit=limit)
        for doc in docs:
            highlights = []
            # Extract snippets from OCR text
            if doc.ocr_text:
                snippets = search_service.extract_snippet(doc.ocr_text, q, context_chars=150, max_snippets=2)
                highlights.extend(snippets)
            
            search_results.append(
                SearchResult(
                    document=doc,
                    score=1.0,
                    highlights=highlights,
                    matched_chunk=None
                )
            )

    return search_results
