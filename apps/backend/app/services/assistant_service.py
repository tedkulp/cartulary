"""Assistant service: metadata extraction, auto-tagging and RAG answers on the assistant model."""
import json
import logging
from typing import Any, Dict, List, Optional

from app.providers import ChatModel, Message, ModelError

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = (
    "You are a document metadata extraction assistant. "
    "Extract structured information from documents and return it as JSON."
)

ANSWER_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about documents. "
    "You only answer based on the provided document context and clearly state when "
    "information is not available in the documents."
)

ANSWER_ERROR_TEXT = (
    "I encountered an error while trying to answer your question. Please try again."
)

# Deterministic for metadata extraction, tag reconciliation and query rewriting.
EXTRACTION_TEMPERATURE = 0.0
EXTRACTION_MAX_TOKENS = 500

# Slightly creative but mostly factual for answers.
ANSWER_TEMPERATURE = 0.3
ANSWER_MAX_TOKENS = 1000


class AssistantService:
    """Extracts document metadata and answers questions about documents."""

    def __init__(self, model: ChatModel) -> None:
        """
        Initialize the assistant service.

        Args:
            model: The assistant model, already bound to its provider and model
        """
        self.model = model

    def extract_metadata(
        self, text: str, filename: Optional[str] = None, existing_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata from document text using the assistant model.

        Uses a two-step approach for tags:
        1. Extract metadata and generate tags with NO knowledge of existing tags
           (prevents anchoring bias where the model shoehorns irrelevant existing tags)
        2. Reconcile generated tags against existing tags, merging only true synonyms

        Args:
            text: Document text (OCR'd or extracted)
            filename: Original filename (optional, provides context)
            existing_tags: List of existing tag names to reconcile against (optional)

        Returns:
            Dictionary containing extracted metadata

        Raises:
            ModelError: If the extraction call fails. It is not caught here: a
                description that never reached the model is not an empty description,
                and the stage is retried on it rather than recording nothing and
                calling the Document described (ADR 0007). The reconciliation pass is
                different, because it has the generated tags to fall back on.
        """
        # Step 1: Extract metadata without existing tags (no anchoring bias)
        prompt = self._build_extraction_prompt(text, filename)

        response_text = self._extract(prompt)
        metadata = self._parse_metadata_response(response_text)
        logger.info(f"Extracted metadata using {self.model!r}: {metadata}")

        # Step 2: Reconcile generated tags against existing tags
        if existing_tags and metadata.get("suggested_tags"):
            metadata["suggested_tags"] = self._reconcile_tags(
                metadata["suggested_tags"], existing_tags
            )
            logger.info(f"Reconciled tags: {metadata['suggested_tags']}")

        return metadata

    def _build_extraction_prompt(
        self, text: str, filename: Optional[str] = None
    ) -> str:
        """Build prompt for metadata extraction (without existing tags to avoid bias)."""
        # Truncate text if too long (keep first 4000 chars for context)
        truncated_text = text[:4000] if len(text) > 4000 else text

        prompt = f"""Analyze the following document and extract structured metadata.

Document text:
{truncated_text}
"""

        if filename:
            prompt += f"\nOriginal filename: {filename}\n"

        prompt += """
Please extract the following information and respond ONLY with a valid JSON object (no markdown, no explanation):

{
  "title": "The document's title or subject (50 chars max)",
  "correspondent": "The sender, author, or organization (if identifiable)",
  "document_date": "The document date in YYYY-MM-DD format (if found)",
  "document_type": "The type of document (e.g., invoice, letter, receipt, report, contract)",
  "summary": "A brief 1-2 sentence summary",
  "suggested_tags": ["tag1", "tag2", "tag3"]
}

Guidelines:
- Use "Unknown" if information cannot be determined
- For document_date, use null if no date is found
- For summary: If the document is primarily about one specific person (e.g., birth certificate, death certificate, medical record, diploma), include that person's full name in the summary. For example: "Birth certificate for John Smith, born January 15, 1990"
- For suggested_tags:
  * Suggest 5-7 relevant tags that specifically describe this document's content and purpose
  * Tags should be concrete and specific (e.g., "tax return", "veterinary receipt", "birth certificate")
  * Avoid vague or generic tags like "unknown", "document", "correspondence", "application", "information"
  * Each tag must be directly and specifically relevant — not tangentially related
  * Do NOT generate tags that overlap or subsume each other (e.g., don't emit both "tax" and "tax notification" — pick the most specific one)
- Keep responses concise and factual
- Return ONLY the JSON object, nothing else
"""
        return prompt

    def _reconcile_tags(
        self, generated_tags: List[str], existing_tags: List[str]
    ) -> List[str]:
        """
        Reconcile generated tags against existing tags using a model call.

        For each generated tag, checks if an existing tag is a true synonym.
        Only merges when the meaning is essentially identical.
        """
        if not generated_tags or not existing_tags:
            return generated_tags

        prompt = f"""I have a list of tags generated for a document and a list of existing tags in the system.
Your job is to produce a clean final tag list by doing two things:

1. DEDUPLICATE within the generated tags: if two generated tags overlap heavily (one is a subset/extension of the other), keep only the more specific one. For example: ["delinquent tax", "delinquent tax notification"] → keep "delinquent tax notification".

2. MAP to existing tags: for each remaining generated tag, if an existing tag means THE SAME THING (true synonym or trivial plural/singular variant), use the existing tag name instead.

Generated tags: {json.dumps(generated_tags)}
Existing tags: {json.dumps(existing_tags)}

Rules for mapping to existing tags:
- ONLY map if they are true synonyms (e.g., "tax returns" → "tax return", "invoices" → "invoice")
- DO NOT map tags that are merely in the same general category
- "veterinary receipt" is NOT a synonym for "dog license"
- "letter" is NOT a synonym for "customer service"
- "2024 tax return" should map to "tax return" if it exists

Respond ONLY with a JSON array of the final tags (no explanation):
["tag1", "tag2", "tag3"]"""

        try:
            reconciled = json.loads(_strip_code_fences(self._extract(prompt)))
            if isinstance(reconciled, list):
                return reconciled[:10]
            logger.warning("Tag reconciliation reply was not a JSON array, using generated tags")
        except (ModelError, ValueError) as e:
            logger.warning(f"Tag reconciliation failed, using generated tags: {e}")

        return generated_tags

    def _extract(self, prompt: str) -> str:
        """Send a prompt with the extraction system prompt and settings. Raises ModelError."""
        return self.model.chat(
            [
                Message(role="system", content=EXTRACTION_SYSTEM_PROMPT),
                Message(role="user", content=prompt),
            ],
            temperature=EXTRACTION_TEMPERATURE,
            max_tokens=EXTRACTION_MAX_TOKENS,
        )

    def _parse_metadata_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the model's reply into structured metadata."""
        cleaned = _strip_code_fences(response_text)
        logger.info(f"Parsing metadata response (length: {len(cleaned)} chars): {cleaned}...")
        try:
            metadata = json.loads(cleaned)

            # Validate and normalize
            return {
                "title": metadata.get("title", "Unknown")[:500],  # Limit length
                "correspondent": metadata.get("correspondent", "Unknown")[:200],
                "document_date": metadata.get("document_date"),  # Can be null
                "document_type": metadata.get("document_type", "Unknown")[:100],
                "summary": metadata.get("summary", "")[:1000],
                "suggested_tags": metadata.get("suggested_tags", [])[:10],  # Max 10 tags
            }
        except (ValueError, TypeError, AttributeError) as e:
            # The reply wasn't the JSON object we asked for.
            logger.error(f"Failed to parse metadata from model reply: {e}")
            logger.debug(f"Reply was: {response_text}")
            return self._get_empty_metadata()

    def _get_empty_metadata(self) -> Dict[str, Any]:
        """Return empty metadata structure."""
        return {
            "title": "Unknown",
            "correspondent": "Unknown",
            "document_date": None,
            "document_type": "Unknown",
            "summary": "",
            "suggested_tags": [],
        }

    def rewrite_query(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Rewrite a user question into a standalone search query using conversation context.

        Follow-up questions like "But you don't know anything about Bella?" won't embed
        well for vector search. This rewrites them into content-focused queries like
        "Bella the dog information".

        Returns the rewritten query, or the original question if rewriting fails.
        """
        if not conversation_history:
            return question

        history_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in conversation_history[-6:]
        )

        prompt = f"""Given this conversation history and a follow-up question, rewrite the question as a short, standalone document search query (5-10 words max). Focus on the key entities and topics being asked about, not the conversational framing.

Conversation history:
{history_text}

Follow-up question: {question}

Respond with ONLY the rewritten search query, nothing else."""

        try:
            rewritten = self._extract(prompt).strip().strip('"').strip("'")
        except ModelError as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return question
        logger.info(f"Rewrote query '{question}' -> '{rewritten}'")
        return rewritten if rewritten else question

    def generate_answer(
        self,
        question: str,
        context_chunks: List[str],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Generate an answer to a question based on document context using RAG.

        Args:
            question: User's question
            context_chunks: List of relevant document chunks to use as context
            conversation_history: Optional list of previous messages [{"role": "user"|"assistant", "content": str}]

        Returns:
            Generated answer text
        """
        # Build context from chunks
        context_text = "\n\n---\n\n".join(
            [f"Document excerpt {i+1}:\n{chunk}" for i, chunk in enumerate(context_chunks)]
        )

        # Build the prompt
        prompt = f"""Answer the user's question based on the following document excerpts. Be concise and accurate.

Context from documents:
{context_text}

Question: {question}

Instructions:
- Answer based ONLY on the information provided in the document excerpts above
- If the answer is not in the provided context, say "I don't have enough information in the documents to answer that question"
- Be specific and cite which document excerpt(s) you used when relevant
- Keep your answer clear and concise"""

        messages = [Message(role="system", content=ANSWER_SYSTEM_PROMPT)]
        if conversation_history:
            # Keep the last 10 messages for context
            messages.extend(
                Message(role=msg["role"], content=msg["content"])  # type: ignore[arg-type]
                for msg in conversation_history[-10:]
            )
        messages.append(Message(role="user", content=prompt))

        try:
            return self.model.chat(
                messages, temperature=ANSWER_TEMPERATURE, max_tokens=ANSWER_MAX_TOKENS
            )
        except ModelError as e:
            logger.error(f"Failed to generate answer with {self.model!r}: {e}")
            return ANSWER_ERROR_TEXT


def _strip_code_fences(text: str) -> str:
    """Remove a markdown code fence wrapped around a reply, if present."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
