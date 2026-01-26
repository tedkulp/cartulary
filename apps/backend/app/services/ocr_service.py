"""OCR service for extracting text from documents using LLM vision."""
import logging
import base64
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """Service for LLM vision-based text extraction."""

    def __init__(self):
        """Initialize OCR service."""
        self.enabled = settings.OCR_ENABLED
        self.model = settings.VISION_OCR_MODEL
        self.base_url = settings.LLM_BASE_URL or "http://localhost:11434"
        self._ollama_client = None

    def _initialize_client(self):
        """Lazy initialize Ollama client."""
        if not self.enabled:
            return

        if self._ollama_client is None:
            try:
                import ollama
                # Create client with configured base URL
                self._ollama_client = ollama.Client(host=self.base_url)
                logger.info(
                    f"✅ Ollama vision OCR initialized successfully "
                    f"(model={self.model}, host={self.base_url})"
                )
            except ImportError:
                logger.error("Ollama library not installed. Install with: pip install ollama")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
                self.enabled = False

    def extract_text(self, file_path: str, force_ocr: bool = False) -> Optional[str]:
        """
        Extract text from an image or PDF file using LLM vision.

        Args:
            file_path: Path to the file to process
            force_ocr: If True, force OCR even if embedded text exists (for reprocessing)

        Returns:
            Extracted text or None if extraction failed
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Handle PDF files - try to extract embedded text first unless forced
            if file_path_obj.suffix.lower() == ".pdf":
                return self._extract_text_from_pdf(file_path, force_ocr=force_ocr)

            # For images, use vision OCR
            if not self.enabled:
                logger.info("Vision OCR is disabled, cannot extract text from images")
                return None

            self._initialize_client()
            if self._ollama_client is None:
                return None

            return self._extract_text_from_image(file_path)

        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            return None

    def _extract_text_from_image(self, image_path: str) -> Optional[str]:
        """
        Extract text from a single image using LLM vision.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        try:
            logger.info(f"Starting LLM vision text extraction for: {image_path}")

            # Check file exists and is readable
            file_path_obj = Path(image_path)
            if not file_path_obj.exists():
                logger.error(f"Image file does not exist: {image_path}")
                return None

            file_size = file_path_obj.stat().st_size
            logger.info(f"Image file size: {file_size} bytes")

            if file_size == 0:
                logger.error(f"Image file is empty: {image_path}")
                return None

            # Read and encode image as base64
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            # Call Ollama vision model
            logger.info(f"Calling Ollama vision model: {self.model}")
            response = self._ollama_client.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": """Perform Optical Character Recognition (OCR) on the following image data.
                    Process all the text on the entire iamge, exactly as it's written. This image is a scan of a document, so try to read every single word all the way to the end of the page.
                    The output should be the extracted text formatted in Markdown, preserving structure where possible, but do not include any code blocks (```) or anything else that looks like a code block (including plain text).
                    Do not add any commentary or explanation of the text, just the text itself.
                    Do no add any headers to the document that aren't written on the page.
                    Do not tell me that a block of text is a Header, or Body Text, etc. We can gather that through context.
                    If text is bold, italic, or underlined, it should be preserved in the output.""",
                    "images": [image_data]
                }]
            )

            extracted_text = response["message"]["content"]
            logger.info(f"Extracted {len(extracted_text)} characters from {image_path}")
            logger.info(f"Full Ollama response for {image_path}:")
            logger.info(f"--- BEGIN OLLAMA RESPONSE ---")
            logger.info(extracted_text)
            logger.info(f"--- END OLLAMA RESPONSE ---")

            return extracted_text

        except Exception as e:
            logger.error(f"Failed to extract text from image {image_path}: {type(e).__name__}: {str(e)}", exc_info=True)
            return None

    def _extract_text_from_pdf(self, pdf_path: str, force_ocr: bool = False) -> Optional[str]:
        """
        Extract text from PDF file using LLM vision.

        Args:
            pdf_path: Path to PDF file
            force_ocr: If True, skip embedded text and force vision OCR

        Returns:
            Extracted text from all pages
        """
        try:
            import fitz  # PyMuPDF

            logger.info(f"Starting PDF text extraction for: {pdf_path}")

            # Check file exists and is readable
            file_path_obj = Path(pdf_path)
            if not file_path_obj.exists():
                logger.error(f"PDF file does not exist: {pdf_path}")
                return None

            file_size = file_path_obj.stat().st_size
            logger.info(f"PDF file size: {file_size} bytes")

            if file_size == 0:
                logger.error(f"PDF file is empty: {pdf_path}")
                return None

            doc = fitz.open(pdf_path)
            page_count = len(doc)
            logger.info(f"PDF has {page_count} pages")

            all_text = []
            processed_pages = []

            for page_num in range(page_count):
                try:
                    page = doc[page_num]

                    text = None
                    
                    # If force_ocr is True, skip embedded text extraction entirely
                    if force_ocr:
                        logger.info(f"Page {page_num + 1}: Forcing vision OCR (ignoring embedded text)")
                    else:
                        # First try to extract embedded text
                        text = page.get_text()

                    # Use vision OCR if: forced, no embedded text, or embedded text too short
                    should_use_vision_ocr = force_ocr or (not text or len(text.strip()) < 50)
                    
                    if should_use_vision_ocr and self.enabled:
                        if not force_ocr:
                            logger.info(f"Page {page_num + 1}: Embedded text too short ({len(text.strip()) if text else 0} chars), attempting vision OCR")
                        
                        self._initialize_client()
                        if self._ollama_client:
                            # Convert page to image with unique temp file to avoid collisions
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better quality
                            
                            # Use tempfile to create unique file per page/document
                            fd, img_path = tempfile.mkstemp(suffix=".png", prefix=f"ocr_page_{page_num}_")
                            import os
                            os.close(fd)  # Close file descriptor, we'll write with PyMuPDF
                            
                            pix.save(img_path)
                            logger.info(f"Page {page_num + 1}: Saved page image to {img_path}, calling Ollama vision API...")

                            # Run vision OCR on the image
                            vision_text = self._extract_text_from_image(img_path)
                            if vision_text:
                                logger.info(f"Page {page_num + 1}: Vision OCR extracted {len(vision_text)} characters")
                                text = vision_text
                            else:
                                logger.warning(f"Page {page_num + 1}: Vision OCR returned None or empty text")

                            # Clean up temp file
                            Path(img_path).unlink(missing_ok=True)
                    else:
                        if text:
                            logger.info(f"Page {page_num + 1}: Extracted {len(text.strip())} chars of embedded text")

                    if text:
                        all_text.append(text)
                        processed_pages.append(page_num + 1)
                    else:
                        logger.warning(f"Page {page_num + 1}: No text extracted (text is None or empty)")

                except Exception as e:
                    logger.error(f"Failed to process page {page_num + 1} of {pdf_path}: {type(e).__name__}: {str(e)}", exc_info=True)
                    # Continue with other pages even if one fails
                    continue

            doc.close()
            total_text = "\n\n".join(all_text)
            logger.info(f"PDF extraction complete: {len(all_text)}/{page_count} pages processed successfully")
            logger.info(f"Successfully processed pages: {processed_pages}")
            logger.info(f"Total extracted text: {len(total_text)} characters")
            
            if len(all_text) < page_count:
                missing_pages = [p for p in range(1, page_count + 1) if p not in processed_pages]
                logger.warning(f"Missing {page_count - len(all_text)} pages: {missing_pages}")
            
            return total_text

        except ImportError:
            logger.error(
                "PyMuPDF not installed. Install with: pip install pymupdf"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {type(e).__name__}: {str(e)}", exc_info=True)
            return None

    def detect_language(self, text: str) -> str:
        """
        Detect language of extracted text.

        Args:
            text: Text to analyze

        Returns:
            Language code (e.g., 'en', 'de', 'fr')
        """
        # TODO: Implement language detection using langdetect or similar
        # For now, just return 'en' as default
        return "en"
