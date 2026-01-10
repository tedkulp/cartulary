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
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
    vector_search_service: VectorSearchService = Depends(get_vector_search_service),
) -> List[SearchResult]:
    """
    Advanced search with multiple modes: fulltext, semantic, or hybrid.

    - **q**: Search query string
    - **mode**: Search mode (fulltext, semantic, or hybrid)
    - **limit**: Maximum number of results

    Modes:
    - **fulltext**: Traditional keyword search (fast, exact matching)
    - **semantic**: Vector similarity search (understands meaning)
    - **hybrid**: Combines both methods using Reciprocal Rank Fusion (best quality)
    """
    if mode == SearchMode.SEMANTIC:
        # Pure semantic search
        results = vector_search_service.vector_search(q, current_user.id, limit=limit)
    elif mode == SearchMode.HYBRID:
        # Hybrid search with RRF
        results = vector_search_service.hybrid_search(q, current_user.id, limit=limit)
    else:
        # Full-text search (default)
        docs = search_service.search_documents(q, current_user.id, skip=0, limit=limit)
        results = [(doc, 1.0) for doc in docs]  # Assign score of 1.0 to all FTS results

    # Convert to SearchResult objects
    return [
        SearchResult(document=DocumentResponse.model_validate(doc), score=score)
        for doc, score in results
    ]
