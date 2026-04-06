"""LLM service for metadata extraction and auto-tagging."""
import logging
import json
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class LLMService:
    """Service for LLM-based metadata extraction and auto-tagging."""

    def __init__(
        self,
        provider: str,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize LLM service.

        Args:
            provider: LLM provider (openai, gemini, ollama)
            model_name: Model to use
            api_key: API key (required for OpenAI and Gemini)
            base_url: Base URL for API (optional, mainly for Ollama)
        """
        self.provider = LLMProvider(provider)
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url or self._get_default_base_url()

        # Initialize provider-specific client
        self.client = self._initialize_client()

    def _get_default_base_url(self) -> str:
        """Get default base URL for provider."""
        if self.provider == LLMProvider.OLLAMA:
            return "http://localhost:11434"
        return ""

    def _initialize_client(self):
        """Initialize provider-specific client."""
        if self.provider == LLMProvider.OPENAI:
            try:
                from openai import OpenAI

                return OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "OpenAI library not installed. Install with: pip install openai"
                )

        elif self.provider == LLMProvider.GEMINI:
            try:
                import google.generativeai as genai

                if self.api_key:
                    genai.configure(api_key=self.api_key)
                return genai
            except ImportError:
                raise ImportError(
                    "Google Generative AI library not installed. "
                    "Install with: pip install google-generativeai"
                )

        elif self.provider == LLMProvider.OLLAMA:
            try:
                from ollama import Client

                return Client(host=self.base_url)
            except ImportError:
                raise ImportError(
                    "Ollama library not installed. Install with: pip install ollama"
                )

        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def extract_metadata(
        self, text: str, filename: Optional[str] = None, existing_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata from document text using LLM.

        Uses a two-step approach for tags:
        1. Extract metadata and generate tags with NO knowledge of existing tags
           (prevents anchoring bias where the LLM shoehorns irrelevant existing tags)
        2. Reconcile generated tags against existing tags, merging only true synonyms

        Args:
            text: Document text (OCR'd or extracted)
            filename: Original filename (optional, provides context)
            existing_tags: List of existing tag names to reconcile against (optional)

        Returns:
            Dictionary containing extracted metadata
        """
        # Step 1: Extract metadata without existing tags (no anchoring bias)
        prompt = self._build_extraction_prompt(text, filename)

        try:
            response_text = self._call_llm(prompt)
            metadata = self._parse_metadata_response(response_text)
            logger.info(f"Extracted metadata using {self.provider}: {metadata}")

            # Step 2: Reconcile generated tags against existing tags
            if existing_tags and metadata.get("suggested_tags"):
                metadata["suggested_tags"] = self._reconcile_tags(
                    metadata["suggested_tags"], existing_tags
                )
                logger.info(f"Reconciled tags: {metadata['suggested_tags']}")

            return metadata
        except Exception as e:
            logger.error(f"Failed to extract metadata with {self.provider}: {e}")
            return self._get_empty_metadata()

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
        Reconcile generated tags against existing tags using an LLM call.

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
            response_text = self._call_llm(prompt)
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            reconciled = json.loads(cleaned)
            if isinstance(reconciled, list):
                return reconciled[:10]
        except Exception as e:
            logger.warning(f"Tag reconciliation failed, using generated tags: {e}")

        return generated_tags

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with the given prompt."""
        if self.provider == LLMProvider.OPENAI:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a document metadata extraction assistant. "
                        "Extract structured information from documents and return it as JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,  # Deterministic for metadata extraction
                max_tokens=500,
            )
            return response.choices[0].message.content

        elif self.provider == LLMProvider.GEMINI:
            model = self.client.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            return response.text

        elif self.provider == LLMProvider.OLLAMA:
            response = self.client.chat(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a document metadata extraction assistant. "
                        "Extract structured information from documents and return it as JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return response["message"]["content"]

        raise ValueError(f"Unsupported provider: {self.provider}")

    def _parse_metadata_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response into structured metadata."""
        try:
            # Remove markdown code blocks if present
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Parse JSON
            logger.info(f"Parsing LLM metadata response (length: {len(cleaned)} chars): {cleaned}...")
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
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"Response was: {response_text}")
            return self._get_empty_metadata()
        except Exception as e:
            logger.error(f"Error parsing metadata: {e}")
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
            rewritten = self._call_llm(prompt).strip().strip('"').strip("'")
            logger.info(f"Rewrote query '{question}' -> '{rewritten}'")
            return rewritten if rewritten else question
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return question

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

        try:
            # Build messages array for chat-based models
            messages = []
            
            # System message
            messages.append({
                "role": "system",
                "content": "You are a helpful assistant that answers questions about documents. "
                "You only answer based on the provided document context and clearly state when "
                "information is not available in the documents."
            })
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-10:]:  # Keep last 10 messages for context
                    messages.append(msg)
            
            # Add current question
            messages.append({"role": "user", "content": prompt})
            
            # Call LLM based on provider
            if self.provider == LLMProvider.OPENAI:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.3,  # Slightly creative but mostly factual
                    max_tokens=1000,
                )
                return response.choices[0].message.content

            elif self.provider == LLMProvider.GEMINI:
                # Gemini doesn't use the same message format, build a single prompt
                full_prompt = prompt
                if conversation_history:
                    history_text = "\n".join([
                        f"{msg['role'].upper()}: {msg['content']}"
                        for msg in conversation_history[-10:]
                    ])
                    full_prompt = f"Previous conversation:\n{history_text}\n\n{prompt}"
                
                model = self.client.GenerativeModel(self.model_name)
                response = model.generate_content(full_prompt)
                return response.text

            elif self.provider == LLMProvider.OLLAMA:
                response = self.client.chat(
                    model=self.model_name,
                    messages=messages,
                )
                return response["message"]["content"]

            raise ValueError(f"Unsupported provider: {self.provider}")
            
        except Exception as e:
            logger.error(f"Failed to generate answer with {self.provider}: {e}")
            return "I encountered an error while trying to answer your question. Please try again."
