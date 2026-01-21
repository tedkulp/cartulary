"""Storage service for handling file operations."""
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Tuple
from uuid import UUID

from fastapi import UploadFile

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file storage operations."""

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize storage service.

        Args:
            base_path: Base path for file storage. Defaults to settings.LOCAL_STORAGE_PATH
        """
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_document_path(self, document_id: UUID) -> Path:
        """
        Get the storage path for a document.

        Args:
            document_id: Document UUID

        Returns:
            Path to document directory
        """
        # Organize files by first two characters of UUID for better filesystem performance
        prefix = str(document_id)[:2]
        doc_path = self.base_path / prefix / str(document_id)
        doc_path.mkdir(parents=True, exist_ok=True)
        return doc_path

    async def calculate_checksum(self, file: UploadFile) -> str:
        """
        Calculate SHA-256 checksum of uploaded file.

        Args:
            file: Uploaded file

        Returns:
            Hex-encoded SHA-256 checksum
        """
        sha256_hash = hashlib.sha256()

        # Read file in chunks to handle large files
        chunk_size = 8192
        await file.seek(0)  # Ensure we're at the beginning

        while chunk := await file.read(chunk_size):
            sha256_hash.update(chunk)

        # Reset file pointer for subsequent reads
        await file.seek(0)

        return sha256_hash.hexdigest()

    def _is_image_file(self, filename: str) -> bool:
        """Check if filename is an image type that should be converted to PDF."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif'}
        ext = Path(filename).suffix.lower()
        return ext in image_extensions

    def _convert_image_to_pdf(self, image_path: Path) -> Path:
        """
        Convert an image file to PDF.

        Args:
            image_path: Path to image file

        Returns:
            Path to generated PDF file
        """
        try:
            import img2pdf
            from PIL import Image
            
            # Output PDF path (same location, .pdf extension)
            pdf_path = image_path.with_suffix('.pdf')
            
            logger.info(f"Converting image to PDF: {image_path} -> {pdf_path}")
            
            # Open image to check if it needs conversion
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if needed (img2pdf doesn't support RGBA)
                if img.mode in ('RGBA', 'LA', 'P'):
                    logger.info(f"Converting image mode from {img.mode} to RGB")
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    # Save as temporary RGB image
                    temp_path = image_path.with_suffix('.tmp.jpg')
                    rgb_img.save(temp_path, 'JPEG', quality=95)
                    image_to_convert = temp_path
                else:
                    image_to_convert = image_path
            
            # Convert to PDF
            with open(pdf_path, 'wb') as pdf_file:
                pdf_file.write(img2pdf.convert(str(image_to_convert)))
            
            # Clean up temp file if it was created
            if image_to_convert != image_path:
                image_to_convert.unlink()
            
            # Delete original image
            image_path.unlink()
            
            logger.info(f"Successfully converted image to PDF: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to convert image to PDF: {e}", exc_info=True)
            # If conversion fails, keep the original image
            return image_path

    async def save_file(
        self,
        file: UploadFile,
        document_id: UUID,
        filename: str,
        convert_images_to_pdf: bool = True
    ) -> Tuple[str, str, str]:
        """
        Save uploaded file to storage. Images are automatically converted to PDF.

        Args:
            file: Uploaded file
            document_id: Document UUID
            filename: Original filename
            convert_images_to_pdf: Whether to convert images to PDF (default: True)

        Returns:
            Tuple of (relative_path, final_filename, mime_type)
        """
        doc_path = self._get_document_path(document_id)

        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        file_path = doc_path / safe_filename

        # Save file initially
        await file.seek(0)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Convert images to PDF
        if convert_images_to_pdf and self._is_image_file(safe_filename):
            logger.info(f"Image file detected, converting to PDF: {safe_filename}")
            pdf_path = self._convert_image_to_pdf(file_path)
            final_path = pdf_path
            final_filename = pdf_path.name
            mime_type = "application/pdf"
        else:
            final_path = file_path
            final_filename = safe_filename
            mime_type = file.content_type or "application/octet-stream"

        # Return relative path from base_path
        relative_path = str(final_path.relative_to(self.base_path))
        return relative_path, final_filename, mime_type

    def get_file_path(self, relative_path: str) -> Path:
        """
        Get absolute path for a stored file.

        Args:
            relative_path: Relative path from save_file()

        Returns:
            Absolute path to file
        """
        return self.base_path / relative_path

    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            relative_path: Relative path from save_file()

        Returns:
            True if file was deleted, False if file didn't exist
        """
        file_path = self.get_file_path(relative_path)

        if file_path.exists():
            file_path.unlink()

            # Clean up empty directories
            try:
                file_path.parent.rmdir()  # Remove document directory
                file_path.parent.parent.rmdir()  # Remove prefix directory
            except OSError:
                # Directory not empty, which is fine
                pass

            return True

        return False

    def file_exists(self, relative_path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            relative_path: Relative path from save_file()

        Returns:
            True if file exists
        """
        return self.get_file_path(relative_path).exists()

    def get_file_size(self, relative_path: str) -> int:
        """
        Get size of stored file in bytes.

        Args:
            relative_path: Relative path from save_file()

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = self.get_file_path(relative_path)
        return file_path.stat().st_size
