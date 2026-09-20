"""Vector search service for semantic similarity search."""
import logging
from typing import List, Tuple, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import accessible_documents
from app.models.document import Document, DocumentEmbedding
from app.models.user import User
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

    def _load_documents(self, document_ids: List[UUID]) -> dict:
        """
        Load Documents by id, with tags, keyed by id.

        Args:
            document_ids: Ids to load

        Returns:
            Mapping of document id to Document
        """
        if not document_ids:
            return {}

        documents = (
            self.db.query(Document)
            .options(selectinload(Document.tags))
            .filter(Document.id.in_(document_ids))
            .all()
        )

        return {document.id: document for document in documents}

    def vector_search(
        self, query: str, user: User, limit: int = 10, similarity_threshold: float = 0.3
    ) -> List[Tuple[Document, float, str]]:
        """
        Perform vector similarity search.

        Searches every Document accessible to the user, which includes documents
        shared with them and public documents, not only the ones they own.

        Args:
            query: Search query
            user: User the results must be accessible to
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

        # pgvector's <=> is a distance (lower is better), so similarity is 1 - distance.
        similarity = (
            1 - DocumentEmbedding.embedding.cosine_distance(query_embedding)
        ).label("similarity")

        # DISTINCT ON picks the best-scoring chunk per document; the outer select
        # then ranks those best-per-document rows and applies the limit.
        best_chunks = (
            select(
                Document.id.label("document_id"),
                DocumentEmbedding.chunk_text.label("chunk_text"),
                similarity,
            )
            .join(DocumentEmbedding, DocumentEmbedding.document_id == Document.id)
            .where(
                accessible_documents(user),
                similarity >= similarity_threshold,
            )
            .distinct(Document.id)
            .order_by(Document.id, similarity.desc())
            .subquery()
        )

        rows = self.db.execute(
            select(best_chunks).order_by(best_chunks.c.similarity.desc()).limit(limit)
        ).all()

        # Real Document entities, not column copies: a semantic hit carries
        # everything a listed document carries, tags and ownership included.
        documents = self._load_documents([row.document_id for row in rows])

        return [
            (documents[row.document_id], float(row.similarity), row.chunk_text or "")
            for row in rows
            if row.document_id in documents
        ]

    def hybrid_search(
        self,
        query: str,
        user: User,
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

        Both halves already filter to what the user may read, so the fused result
        needs no access check of its own.

        Args:
            query: Search query
            user: User the results must be accessible to
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
        fts_results = search_service.search_documents(query, user, skip=0, limit=limit * 2)
        vector_results = self.vector_search(query, user, limit=limit * 2, similarity_threshold=similarity_threshold)

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

        # Sort by RRF score, dropping anything too weak to be worth showing
        ranked_ids = [
            doc_id
            for doc_id in sorted(doc_scores, key=lambda doc_id: doc_scores[doc_id], reverse=True)
            if doc_scores[doc_id] >= min_rrf_score
        ][:limit]

        documents = self._load_documents(ranked_ids)

        return [
            (documents[doc_id], doc_scores[doc_id], doc_chunks.get(doc_id))
            for doc_id in ranked_ids
            if doc_id in documents
        ]
