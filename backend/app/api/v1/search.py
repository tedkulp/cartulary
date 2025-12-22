"""Search API endpoints."""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def get_search_service(db: Session = Depends(get_db)) -> SearchService:
    """Dependency to get search service."""
    return SearchService(db)


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
