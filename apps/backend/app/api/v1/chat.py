"""Chat API endpoints for RAG-based document Q&A."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.vector_search_service import VectorSearchService
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.api.v1.auth import get_current_user
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    """Get chat service with dependencies."""
    # Create embedding service
    embedding_service = EmbeddingService(
        provider=settings.EMBEDDING_PROVIDER,
        model_name=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY if settings.EMBEDDING_PROVIDER == "openai" else None,
        dimension=settings.EMBEDDING_DIMENSION,
    )

    # Create vector search service
    vector_search_service = VectorSearchService(
        db=db,
        embedding_service=embedding_service,
    )

    # Create LLM service
    llm_service = LLMService(
        provider=settings.LLM_PROVIDER,
        model_name=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY if settings.LLM_PROVIDER == "openai" else None,
        base_url=settings.LLM_BASE_URL,
    )

    # Create and return chat service
    return ChatService(
        db=db,
        vector_search_service=vector_search_service,
        llm_service=llm_service,
    )


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Chat with your documents using RAG.

    Ask questions about your documents and get answers based on their content.
    The system will search for relevant document chunks and use them to generate
    an accurate answer.

    Args:
        request: Chat request with question and optional conversation history
        current_user: Authenticated user
        chat_service: Chat service dependency

    Returns:
        ChatResponse with answer, source documents, and chunks used
    """
    try:
        logger.info(f"Chat request from user {current_user.id}: {request.question[:100]}")

        response = chat_service.chat(
            question=request.question,
            user_id=current_user.id,
            conversation_history=request.conversation_history,
            num_chunks=request.num_chunks,
        )

        logger.info(f"Chat response generated with {len(response.sources)} sources")
        return response

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your question. Please try again.",
        )
