"""Chat schemas for RAG-based document Q&A."""
from typing import List, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a conversation."""
    
    role: Literal["user", "assistant"]
    content: str


class DocumentSource(BaseModel):
    """Reference to a source document used in the answer."""
    
    id: str
    title: str
    score: float = Field(description="Relevance score (0-1)")


class ChatRequest(BaseModel):
    """Request to chat with documents."""
    
    question: str = Field(min_length=1, max_length=2000)
    conversation_history: List[ChatMessage] = Field(default_factory=list)
    num_chunks: int = Field(default=5, ge=1, le=20, description="Number of document chunks to retrieve")


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    
    answer: str
    sources: List[DocumentSource]
    chunks_used: List[str] = Field(description="The actual text chunks used as context")
