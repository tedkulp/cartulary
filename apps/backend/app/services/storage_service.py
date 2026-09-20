"""Storage service for handling file operations."""
import logging
import mimetypes
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredFile:
    """The persisted result of storing source bytes."""

    relative_path: str
    filename: str
    mime_type: str
    size: int


class StorageService:
    """Service for handling file storage operations."""

    def __init__(self, base_path: Optional[str] = None) -> None:
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

    def _is_image_file(self, filename: str) -> bool:
        """Check if filename is an image type that should be converted to PDF."""
        image_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
        ext = Path(filename).suffix.lower()
        return ext in image_extensions

    def save_bytes(self, content: bytes, document_id: UUID, filename: str) -> StoredFile:
        """Store source bytes, converting a valid image to PDF when possible."""
        doc_path = self._get_document_path(document_id)
        safe_filename = os.path.basename(filename.replace("\\", "/"))
        file_path = doc_path / safe_filename
        try:
            file_path.write_bytes(content)
            final_path = file_path
            if self._is_image_file(safe_filename):
                from PIL import Image

                try:
                    with Image.open(file_path) as image:
                        actual_format = image.format
                        image.verify()
                except Exception as error:
                    raise ValueError("Image content is invalid") from error
                expected_format = {
                    ".jpg": "JPEG",
                    ".jpeg": "JPEG",
                    ".png": "PNG",
                    ".tif": "TIFF",
                    ".tiff": "TIFF",
                    ".bmp": "BMP",
                }[Path(safe_filename).suffix.lower()]
                if actual_format != expected_format:
                    raise ValueError("Image content does not match filename extension")
                final_path = self._convert_image_to_pdf(file_path)

            mime_type = mimetypes.guess_type(final_path.name)[0] or "application/octet-stream"
            return StoredFile(
                relative_path=str(final_path.relative_to(self.base_path)),
                filename=final_path.name,
                mime_type=mime_type,
                size=final_path.stat().st_size,
            )
        except Exception:
            shutil.rmtree(doc_path, ignore_errors=True)
            try:
                doc_path.parent.rmdir()
            except OSError:
                pass
            raise

    def _convert_image_to_pdf(self, image_path: Path) -> Path:
        """
        Convert an image file to PDF.

        Args:
            image_path: Path to image file

        Returns:
            Path to generated PDF file
        """
        pdf_path = image_path.with_suffix(".pdf")
        temp_path = image_path.with_suffix(".tmp.jpg")
        try:
            import img2pdf
            from PIL import Image

            logger.info("Converting image to PDF: %s -> %s", image_path, pdf_path)

            # Open image to check if it needs conversion
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if needed (img2pdf doesn't support RGBA)
                if img.mode in ("RGBA", "LA", "P"):
                    logger.info("Converting image mode from %s to RGB", img.mode)
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
                    rgb_img.paste(img, mask=mask)
                    rgb_img.save(temp_path, "JPEG", quality=95)
                    image_to_convert = temp_path
                else:
                    image_to_convert = image_path

            # Convert to PDF
            with open(pdf_path, "wb") as pdf_file:
                pdf_file.write(img2pdf.convert(str(image_to_convert)))

            # Clean up temp file if it was created
            if image_to_convert != image_path:
                image_to_convert.unlink()

            # Delete original image
            image_path.unlink()

            logger.info("Successfully converted image to PDF: %s", pdf_path)
            return pdf_path

        except Exception:
            logger.exception("Failed to convert image to PDF; retaining original image")
            for partial_path in (pdf_path, temp_path):
                if partial_path.exists():
                    partial_path.unlink()
            return image_path

    def get_file_path(self, relative_path: str) -> Path:
        """
        Get absolute path for a stored file.

        Args:
            relative_path: Relative path from save_bytes()

        Returns:
            Absolute path to file
        """
        return self.base_path / relative_path

    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            relative_path: Relative path from save_bytes()

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
            relative_path: Relative path from save_bytes()

        Returns:
            True if file exists
        """
        return self.get_file_path(relative_path).exists()

    def get_file_size(self, relative_path: str) -> int:
        """
        Get size of stored file in bytes.

        Args:
            relative_path: Relative path from save_bytes()

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = self.get_file_path(relative_path)
        return file_path.stat().st_size
