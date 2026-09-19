"""Vector search service for semantic similarity search."""
import logging
from typing import List, Tuple, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentEmbedding
from app.providers import Embedder

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for performing vector similarity search."""

    def __init__(self, db: Session, embedder: Optional[Embedder]):
        """
        Initialize vector search service.

        Args:
            db: Database session
            embedder: Embedder for query text, or None when embeddings are disabled
        """
        self.db = db
        self.embedder = embedder

    def vector_search(
        self, query: str, user_id: UUID, limit: int = 10, similarity_threshold: float = 0.3
    ) -> List[Tuple[Document, float, str]]:
        """
        Perform vector similarity search.

        Args:
            query: Search query
            user_id: User ID for filtering results
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity score (0-1). Default 0.3 filters out irrelevant results.
                                  0.8-1.0: Very relevant, 0.6-0.8: Moderately relevant, 0.3-0.6: Somewhat relevant

        Returns:
            List of (Document, similarity_score, chunk_text) tuples, ordered by similarity desc
        """
        if self.embedder is None:
            # Embeddings are disabled, so there is nothing to search.
            return []

        if query.strip():
            query_embedding = self.embedder.embed([query])[0]
        else:
            query_embedding = [0.0] * self.embedder.dimension

        # Perform vector search using pgvector's cosine similarity operator (<=>)
        # Note: pgvector uses distance (lower is better), so we calculate 1 - distance to get similarity
        # Format embedding as PostgreSQL array literal
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build the SQL query with direct string formatting for the vector
        # (SQLAlchemy text() doesn't handle vector type well with parameters)
        # Inner query: DISTINCT ON picks the best chunk per document (ORDER BY d.id, similarity DESC)
        # Outer query: sorts those best-per-document rows by similarity and applies LIMIT
        sql = text(f"""
            SELECT * FROM (
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
                    1 - (de.embedding <=> '{embedding_str}'::vector) as similarity
                FROM documents d
                INNER JOIN document_embeddings de ON d.id = de.document_id
                WHERE d.owner_id = :user_id
                AND 1 - (de.embedding <=> '{embedding_str}'::vector) >= :threshold
                ORDER BY d.id, similarity DESC
            ) best_chunks
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        result = self.db.execute(
            sql,
            {
                "user_id": str(user_id),
                "threshold": similarity_threshold,
                "limit": limit,
            },
        )

        # Convert results to Document objects with scores and chunk_text
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
            chunk_text = row.chunk_text or ""
            results.append((doc, similarity, chunk_text))

        return results

    def hybrid_search(
        self,
        query: str,
        user_id: UUID,
        limit: int = 10,
        fts_weight: float = 0.5,
        vector_weight: float = 0.5,
        similarity_threshold: float = 0.3,
        min_rrf_score: float = 0.005,
    ) -> List[Tuple[Document, float, Optional[str]]]:
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
            similarity_threshold: Minimum similarity for vector results (0-1)
            min_rrf_score: Minimum RRF score to include in results

        Returns:
            List of (Document, rrf_score, chunk_text) tuples, ordered by RRF score desc
        """
        from app.services.search_service import SearchService

        # Perform both searches
        search_service = SearchService(self.db)
        fts_results = search_service.search_documents(query, user_id, skip=0, limit=limit * 2)
        vector_results = self.vector_search(query, user_id, limit=limit * 2, similarity_threshold=similarity_threshold)

        # Apply Reciprocal Rank Fusion
        k = 60  # RRF constant
        doc_scores = {}
        doc_chunks = {}  # Store chunk_text from vector results

        # Add FTS scores
        for rank, doc in enumerate(fts_results, start=1):
            doc_id = doc.id
            rrf_score = fts_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score

        # Add vector search scores
        for rank, (doc, similarity, chunk_text) in enumerate(vector_results, start=1):
            doc_id = doc.id
            rrf_score = vector_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            # Store the chunk_text from the best matching chunk
            if doc_id not in doc_chunks:
                doc_chunks[doc_id] = chunk_text

        # Sort by RRF score and fetch full document objects
        sorted_doc_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
        results = []

        for doc_id in sorted_doc_ids:
            # Filter by minimum RRF score to remove irrelevant results
            if doc_scores[doc_id] < min_rrf_score:
                continue
                
            doc = (
                self.db.query(Document)
                .filter(Document.id == doc_id, Document.owner_id == user_id)
                .first()
            )
            if doc:
                chunk_text = doc_chunks.get(doc_id)
                results.append((doc, doc_scores[doc_id], chunk_text))
                
            # Stop once we have enough results
            if len(results) >= limit:
                break

        return results
