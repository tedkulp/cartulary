"""Storage service for handling file operations."""
import hashlib
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import UUID

from fastapi import UploadFile

from app.config import settings


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

    async def save_file(
        self,
        file: UploadFile,
        document_id: UUID,
        filename: str
    ) -> str:
        """
        Save uploaded file to storage.

        Args:
            file: Uploaded file
            document_id: Document UUID
            filename: Original filename

        Returns:
            Relative path to saved file
        """
        doc_path = self._get_document_path(document_id)

        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        file_path = doc_path / safe_filename

        # Save file
        await file.seek(0)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Return relative path from base_path
        return str(file_path.relative_to(self.base_path))

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
