"""Vector search service for semantic similarity search."""
import logging
from typing import List, Tuple, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentEmbedding
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for performing vector similarity search."""

    def __init__(self, db: Session, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize vector search service.

        Args:
            db: Database session
            embedding_service: Optional embedding service (will create if not provided)
        """
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    def vector_search(
        self, query: str, user_id: UUID, limit: int = 10, similarity_threshold: float = 0.0
    ) -> List[Tuple[Document, float]]:
        """
        Perform vector similarity search.

        Args:
            query: Search query
            user_id: User ID for filtering results
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity score (0-1)

        Returns:
            List of (Document, similarity_score) tuples, ordered by similarity desc
        """
        # Generate embedding for query
        query_embedding = self.embedding_service.generate_embedding(query)

        # Perform vector search using pgvector's cosine similarity operator (<=>)
        # Note: pgvector uses distance (lower is better), so we calculate 1 - distance to get similarity
        sql = text("""
            SELECT DISTINCT ON (d.id)
                d.id,
                d.title,
                d.description,
                d.original_filename,
                d.file_size,
                d.mime_type,
                d.checksum,
                d.processing_status,
                d.ocr_text,
                d.created_at,
                d.updated_at,
                d.uploaded_by,
                de.chunk_text,
                1 - (de.embedding <=> :query_embedding::vector) as similarity
            FROM documents d
            INNER JOIN document_embeddings de ON d.id = de.document_id
            WHERE d.owner_id = :user_id
            AND 1 - (de.embedding <=> :query_embedding::vector) >= :threshold
            ORDER BY d.id, similarity DESC
            LIMIT :limit
        """)

        result = self.db.execute(
            sql,
            {
                "query_embedding": query_embedding,
                "user_id": str(user_id),
                "threshold": similarity_threshold,
                "limit": limit,
            },
        )

        # Convert results to Document objects with scores
        results = []
        for row in result:
            # Create Document object from row
            doc = Document(
                id=row.id,
                title=row.title,
                description=row.description,
                original_filename=row.original_filename,
                file_size=row.file_size,
                mime_type=row.mime_type,
                checksum=row.checksum,
                processing_status=row.processing_status,
                ocr_text=row.ocr_text,
                created_at=row.created_at,
                updated_at=row.updated_at,
                uploaded_by=row.uploaded_by,
            )
            similarity = float(row.similarity)
            results.append((doc, similarity))

        return results

    def hybrid_search(
        self,
        query: str,
        user_id: UUID,
        limit: int = 10,
        fts_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> List[Tuple[Document, float]]:
        """
        Perform hybrid search combining full-text and vector search using RRF.

        Reciprocal Rank Fusion (RRF) combines rankings from different search methods.
        RRF score for document d = sum(1 / (k + rank_i)) for all methods i
        where k is a constant (typically 60) and rank_i is the rank in method i.

        Args:
            query: Search query
            user_id: User ID for filtering results
            limit: Maximum number of results
            fts_weight: Weight for full-text search results (0-1)
            vector_weight: Weight for vector search results (0-1)

        Returns:
            List of (Document, rrf_score) tuples, ordered by RRF score desc
        """
        from app.services.search_service import SearchService

        # Perform both searches
        search_service = SearchService(self.db)
        fts_results = search_service.search(query, user_id, skip=0, limit=limit * 2)
        vector_results = self.vector_search(query, user_id, limit=limit * 2)

        # Apply Reciprocal Rank Fusion
        k = 60  # RRF constant
        doc_scores = {}

        # Add FTS scores
        for rank, doc in enumerate(fts_results, start=1):
            doc_id = doc.id
            rrf_score = fts_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score

        # Add vector search scores
        for rank, (doc, similarity) in enumerate(vector_results, start=1):
            doc_id = doc.id
            rrf_score = vector_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score

        # Sort by RRF score and fetch full document objects
        sorted_doc_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
        results = []

        for doc_id in sorted_doc_ids[:limit]:
            doc = (
                self.db.query(Document)
                .filter(Document.id == doc_id, Document.owner_id == user_id)
                .first()
            )
            if doc:
                results.append((doc, doc_scores[doc_id]))

        return results
