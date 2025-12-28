"""OCR service for extracting text from documents."""
import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR text extraction."""

    def __init__(self):
        """Initialize OCR service."""
        self.enabled = settings.OCR_ENABLED
        self.languages = settings.OCR_LANGUAGES
        self.use_gpu = settings.OCR_USE_GPU
        self._ocr_engine = None

    def _initialize_engine(self):
        """Lazy initialize OCR engine."""
        if not self.enabled:
            return

        if self._ocr_engine is None:
            try:
                import easyocr

                # Auto-detect GPU availability if use_gpu is True
                use_gpu = self.use_gpu
                if use_gpu:
                    try:
                        import torch
                        if not torch.cuda.is_available():
                            logger.warning("GPU requested but CUDA not available, falling back to CPU")
                            use_gpu = False
                        else:
                            logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
                    except ImportError:
                        logger.warning("PyTorch not available for GPU detection, falling back to CPU")
                        use_gpu = False

                # EasyOCR supports multiple languages and works well on ARM64
                # Map our language codes to EasyOCR format
                lang_list = [lang if lang != "en" else "en" for lang in self.languages]

                self._ocr_engine = easyocr.Reader(
                    lang_list=lang_list,
                    gpu=use_gpu
                )
                logger.info(f"EasyOCR engine initialized successfully with languages: {lang_list}, GPU: {use_gpu}")
            except ImportError:
                logger.warning(
                    "EasyOCR not installed. OCR features will be disabled. "
                    "Install with: pip install easyocr"
                )
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self.enabled = False

    def extract_text(self, file_path: str) -> Optional[str]:
        """
        Extract text from an image or PDF file.

        Args:
            file_path: Path to the file to process

        Returns:
            Extracted text or None if extraction failed
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Handle PDF files - always try to extract embedded text first
            if file_path_obj.suffix.lower() == ".pdf":
                return self._extract_text_from_pdf(file_path)

            # For images, we need OCR
            if not self.enabled:
                logger.info("OCR is disabled, cannot extract text from images")
                return None

            self._initialize_engine()
            if self._ocr_engine is None:
                return None

            return self._extract_text_from_image(file_path)

        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            return None

    def _extract_text_from_image(self, image_path: str) -> Optional[str]:
        """
        Extract text from a single image.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        try:
            logger.info(f"Starting EasyOCR text extraction for: {image_path}")

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

            # For large images, resize to reduce memory usage
            # Images larger than 2MB should be resized to prevent OOM
            processed_image_path = image_path
            if file_size > 2 * 1024 * 1024:  # 2MB
                logger.info(f"Image is large ({file_size} bytes), resizing to reduce memory usage")
                processed_image_path = self._resize_image_for_ocr(image_path)

            # EasyOCR returns: [([bbox], text, confidence), ...]
            result = self._ocr_engine.readtext(processed_image_path)

            if not result:
                logger.warning(f"EasyOCR returned no text detections for: {image_path}")
                return ""

            # Extract text from OCR results
            text_lines = []
            for detection in result:
                if len(detection) >= 3:
                    bbox, text, confidence = detection
                    if confidence > 0.5:  # Only include confident results
                        text_lines.append(text)

            extracted_text = "\n".join(text_lines)
            logger.info(f"EasyOCR extracted {len(text_lines)} text lines, {len(extracted_text)} total characters")

            # Clean up resized temp file if it was created
            if processed_image_path != image_path:
                try:
                    Path(processed_image_path).unlink(missing_ok=True)
                    logger.info(f"Cleaned up temporary resized image: {processed_image_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {processed_image_path}: {e}")

            return extracted_text

        except Exception as e:
            logger.error(f"Failed to extract text from image {image_path}: {type(e).__name__}: {str(e)}", exc_info=True)
            # Clean up temp file even on error
            if 'processed_image_path' in locals() and processed_image_path != image_path:
                try:
                    Path(processed_image_path).unlink(missing_ok=True)
                except:
                    pass
            return None

    def _extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from PDF file.

        Args:
            pdf_path: Path to PDF file

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

            for page_num in range(page_count):
                try:
                    page = doc[page_num]

                    # First try to extract embedded text
                    text = page.get_text()

                    # If no embedded text or very little, use OCR (if available)
                    if (not text or len(text.strip()) < 50) and self.enabled:
                        logger.info(f"Page {page_num + 1}: Embedded text too short ({len(text.strip())} chars), attempting OCR")
                        self._initialize_engine()
                        if self._ocr_engine:
                            # Convert page to image
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better OCR
                            img_path = f"/tmp/page_{page_num}.png"
                            pix.save(img_path)

                            # Run OCR on the image
                            ocr_text = self._extract_text_from_image(img_path)
                            if ocr_text:
                                text = ocr_text

                            # Clean up temp file
                            Path(img_path).unlink(missing_ok=True)
                    else:
                        logger.info(f"Page {page_num + 1}: Extracted {len(text.strip())} chars of embedded text")

                    if text:
                        all_text.append(text)

                except Exception as e:
                    logger.error(f"Failed to process page {page_num + 1} of {pdf_path}: {type(e).__name__}: {str(e)}", exc_info=True)
                    # Continue with other pages even if one fails
                    continue

            doc.close()
            total_text = "\n\n".join(all_text)
            logger.info(f"PDF extraction complete: {len(all_text)} pages processed, {len(total_text)} total characters")
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
        # For now, just return the first configured language
        return self.languages[0] if self.languages else "en"

    def _resize_image_for_ocr(self, image_path: str, max_dimension: int = 2048) -> str:
        """
        Resize large images to reduce memory usage during OCR.

        Args:
            image_path: Path to original image
            max_dimension: Maximum width or height in pixels

        Returns:
            Path to resized image (temp file)
        """
        try:
            from PIL import Image
            import tempfile
            import os

            # Open the image
            img = Image.open(image_path)
            original_size = img.size
            logger.info(f"Original image dimensions: {original_size[0]}x{original_size[1]}")

            # Calculate new size maintaining aspect ratio
            width, height = img.size
            if width > max_dimension or height > max_dimension:
                if width > height:
                    new_width = max_dimension
                    new_height = int((max_dimension / width) * height)
                else:
                    new_height = max_dimension
                    new_width = int((max_dimension / height) * width)

                logger.info(f"Resizing image to: {new_width}x{new_height}")

                # Resize with high quality
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save to temp file
                suffix = Path(image_path).suffix
                fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix="ocr_resized_")
                os.close(fd)  # Close the file descriptor, PIL will handle the file

                img.save(temp_path, quality=95, optimize=False)
                temp_size = Path(temp_path).stat().st_size
                logger.info(f"Resized image saved to {temp_path}, size: {temp_size} bytes")

                return temp_path
            else:
                logger.info(f"Image dimensions are within limits, no resize needed")
                return image_path

        except Exception as e:
            logger.error(f"Failed to resize image {image_path}: {e}")
            # Return original path if resize fails
            return image_path
