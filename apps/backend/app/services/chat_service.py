"""Chat service for RAG-based document Q&A."""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.chat import ChatMessage, ChatResponse, DocumentSource
from app.services.vector_search_service import VectorSearchService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ChatService:
    """Service for RAG-based chat with documents."""

    def __init__(
        self,
        db: Session,
        vector_search_service: VectorSearchService,
        llm_service: LLMService,
    ):
        """
        Initialize chat service.

        Args:
            db: Database session
            vector_search_service: Service for vector similarity search
            llm_service: Service for LLM-based answer generation
        """
        self.db = db
        self.vector_search_service = vector_search_service
        self.llm_service = llm_service

    def chat(
        self,
        question: str,
        user_id: UUID,
        conversation_history: Optional[List[ChatMessage]] = None,
        num_chunks: int = 5,
        similarity_threshold: float = 0.3,
    ) -> ChatResponse:
        """
        Answer a question about documents using RAG.

        Args:
            question: User's question
            user_id: User ID for filtering documents
            conversation_history: Optional previous conversation messages
            num_chunks: Number of document chunks to retrieve
            similarity_threshold: Minimum similarity score for retrieval

        Returns:
            ChatResponse with answer, sources, and chunks used
        """
        logger.info(f"Processing chat question for user {user_id}: {question[:100]}...")

        # Step 1: Retrieve relevant document chunks using vector search
        try:
            search_results = self.vector_search_service.vector_search(
                query=question,
                user_id=user_id,
                limit=num_chunks,
                similarity_threshold=similarity_threshold,
            )
            logger.info(f"Retrieved {len(search_results)} relevant chunks")
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return ChatResponse(
                answer="I encountered an error while searching your documents. Please try again.",
                sources=[],
                chunks_used=[],
            )

        # If no relevant documents found
        if not search_results:
            logger.info("No relevant documents found")
            return ChatResponse(
                answer="I couldn't find any relevant information in your documents to answer that question. "
                "Try rephrasing your question or make sure you have uploaded relevant documents.",
                sources=[],
                chunks_used=[],
            )

        # Step 2: Extract chunks and build sources list
        chunks = []
        sources = []
        seen_doc_ids = set()

        for doc, score, chunk_text in search_results:
            # Add chunk text
            if chunk_text:
                chunks.append(chunk_text)

            # Add document to sources (avoid duplicates)
            if doc.id not in seen_doc_ids:
                sources.append(
                    DocumentSource(
                        id=str(doc.id),
                        title=doc.title or doc.original_filename,
                        score=score,
                    )
                )
                seen_doc_ids.add(doc.id)

        logger.info(f"Using {len(chunks)} chunks from {len(sources)} documents")

        # Step 3: Convert conversation history to dict format for LLM
        history_dicts = None
        if conversation_history:
            history_dicts = [
                {"role": msg.role, "content": msg.content}
                for msg in conversation_history
            ]

        # Step 4: Generate answer using LLM
        try:
            answer = self.llm_service.generate_answer(
                question=question,
                context_chunks=chunks,
                conversation_history=history_dicts,
            )
            logger.info(f"Generated answer (length: {len(answer)} chars)")
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return ChatResponse(
                answer="I encountered an error while generating an answer. Please try again.",
                sources=sources,
                chunks_used=chunks,
            )

        # Step 5: Return response
        return ChatResponse(
            answer=answer,
            sources=sources,
            chunks_used=chunks,
        )
