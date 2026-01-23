"""Search service for document full-text search."""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import DocumentResponse

logger = logging.getLogger(__name__)


class SearchService:
    """Service for document search operations."""

    def __init__(self, db: Session):
        """
        Initialize search service.

        Args:
            db: Database session
        """
        self.db = db

    def extract_snippet(
        self, text: str, query: str, context_chars: int = 150, max_snippets: int = 2
    ) -> List[str]:
        """
        Extract snippets from text around keyword matches with highlighted terms.

        Args:
            text: Text to search in
            query: Search query
            context_chars: Number of characters to include before/after match
            max_snippets: Maximum number of snippets to return

        Returns:
            List of text snippets with matched terms wrapped in <mark> tags
        """
        if not text or not query:
            return []

        # Split query into terms
        terms = [term.strip() for term in query.split() if term.strip()]
        if not terms:
            return []

        snippets = []
        text_lower = text.lower()

        # Find matches for each term
        for term in terms[:max_snippets]:  # Limit to first few terms
            term_lower = term.lower()
            # Find first occurrence of this term
            match_pos = text_lower.find(term_lower)

            if match_pos != -1:
                # Extract context around the match
                # Use len(term_lower) to match the search position calculation
                start = max(0, match_pos - context_chars)
                end = min(len(text), match_pos + len(term_lower) + context_chars)

                snippet = text[start:end].strip()

                # Highlight all occurrences of search terms in the snippet
                snippet = self._highlight_terms(snippet, terms)

                # Add ellipsis if we're not at the start/end
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."

                snippets.append(snippet)

                # Break after finding first match to avoid duplicates
                if len(snippets) >= max_snippets:
                    break

        return snippets

    def _highlight_terms(self, text: str, terms: List[str]) -> str:
        """
        Wrap matched terms in <mark> tags for highlighting.

        Args:
            text: Text to highlight
            terms: List of terms to highlight

        Returns:
            Text with matched terms wrapped in <mark> tags
        """
        import re
        
        result = text
        for term in terms:
            if not term:
                continue
            # Case-insensitive replacement, preserving original case
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            result = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", result)
        
        return result

    def search_documents(
        self,
        query: str,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DocumentResponse]:
        """
        Search documents using full-text search on title and OCR text.

        Args:
            query: Search query string
            user_id: User ID (for permission filtering)
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of matching documents
        """
        if not query or not query.strip():
            # Return all documents if no query
            documents = (
                self.db.query(Document)
                .filter(Document.owner_id == user_id)
                .order_by(Document.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            return [DocumentResponse.model_validate(doc) for doc in documents]

        # Use PostgreSQL ILIKE for case-insensitive search
        # In production, you'd want to use ts_vector for better performance
        search_term = f"%{query}%"

        documents = (
            self.db.query(Document)
            .filter(
                Document.owner_id == user_id,
                or_(
                    Document.title.ilike(search_term),
                    Document.original_filename.ilike(search_term),
                    Document.ocr_text.ilike(search_term),
                    Document.extracted_title.ilike(search_term),
                    Document.extracted_correspondent.ilike(search_term),
                ),
            )
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return [DocumentResponse.model_validate(doc) for doc in documents]

    def count_search_results(self, query: str, user_id: UUID) -> int:
        """
        Count total number of search results.

        Args:
            query: Search query string
            user_id: User ID (for permission filtering)

        Returns:
            Total count of matching documents
        """
        if not query or not query.strip():
            return self.db.query(Document).filter(Document.owner_id == user_id).count()

        search_term = f"%{query}%"

        return (
            self.db.query(func.count(Document.id))
            .filter(
                Document.owner_id == user_id,
                or_(
                    Document.title.ilike(search_term),
                    Document.original_filename.ilike(search_term),
                    Document.ocr_text.ilike(search_term),
                    Document.extracted_title.ilike(search_term),
                    Document.extracted_correspondent.ilike(search_term),
                ),
            )
            .scalar()
        )