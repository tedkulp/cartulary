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
                import ollama

                return ollama
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

        Args:
            text: Document text (OCR'd or extracted)
            filename: Original filename (optional, provides context)
            existing_tags: List of existing tag names to prefer (optional)

        Returns:
            Dictionary containing extracted metadata:
            {
                "title": str,
                "correspondent": str,
                "document_date": str (ISO format),
                "document_type": str,
                "summary": str,
                "suggested_tags": List[str]
            }
        """
        prompt = self._build_extraction_prompt(text, filename, existing_tags)

        try:
            response_text = self._call_llm(prompt)
            metadata = self._parse_metadata_response(response_text)
            logger.info(f"Extracted metadata using {self.provider}: {metadata}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to extract metadata with {self.provider}: {e}")
            return self._get_empty_metadata()

    def _build_extraction_prompt(
        self, text: str, filename: Optional[str] = None, existing_tags: Optional[List[str]] = None
    ) -> str:
        """Build prompt for metadata extraction."""
        # Truncate text if too long (keep first 4000 chars for context)
        truncated_text = text[:4000] if len(text) > 4000 else text

        prompt = f"""Analyze the following document and extract structured metadata.

Document text:
{truncated_text}
"""

        if filename:
            prompt += f"\nOriginal filename: {filename}\n"

        if existing_tags and len(existing_tags) > 0:
            prompt += f"\nExisting tags in the system: {', '.join(existing_tags)}\n"

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
  * Suggest 3-5 relevant tags based on content
  * If any of the existing tags listed above are absolutely relevant to this document, use those exact tag names
  * Suggest new tags if the existing tags are not relevant or if additional categorization would be helpful
  * Prefer existing tags when they accurately describe the document's content, subject, or category
  * Consider all the words in a tag, not just a single word when determining its relevance. For example for the tag "commitment form", if the document is a form for membership to an organization, then the tag isn't relevant.
  * DO NOT return existing tags that are not relevant to the document. They ABSOLUTELY must be relevant to the document!
- Keep responses concise and factual
- Return ONLY the JSON object, nothing else
"""
        return prompt

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
