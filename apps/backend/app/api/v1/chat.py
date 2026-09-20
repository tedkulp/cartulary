"""Chat API endpoints for RAG-based document Q&A."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import (
    CAPABILITY_DISABLED_RESPONSE,
    TURN_ON_ASSISTANT_MODEL,
    capability_disabled_error,
)
from app.database import get_db
from app.models.user import User
from app.providers.factory import get_assistant_model, get_embedder
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.assistant_service import AssistantService
from app.services.chat_service import ChatService
from app.services.vector_search_service import VectorSearchService
from app.api.v1.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    """Get chat service with dependencies."""
    assistant_model = get_assistant_model()
    if assistant_model is None:
        # 503, not 400: the request is fine, the server has the capability turned
        # off. Chat shares LLM_ENABLED with metadata extraction, so an upgrader
        # who ran chat with the flag off needs to be told to set it. See ADR 0003.
        raise capability_disabled_error(
            "Chat needs an assistant model, and none is configured.",
            TURN_ON_ASSISTANT_MODEL,
        )

    return ChatService(
        db=db,
        vector_search_service=VectorSearchService(db=db, embedder=get_embedder()),
        assistant_service=AssistantService(assistant_model),
    )


@router.post(
    "/",
    response_model=ChatResponse,
    responses=CAPABILITY_DISABLED_RESPONSE,
)
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
