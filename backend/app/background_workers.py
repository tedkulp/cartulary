"""Background worker manager for FastAPI."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI

logger = logging.getLogger(__name__)


class BackgroundWorkerManager:
    """Manages background workers that run alongside FastAPI."""

    def __init__(self):
        self.tasks: List[asyncio.Task] = []
        self.should_stop = False

    async def start_directory_watcher(self):
        """Start the directory watcher in the background."""
        from app.workers.directory_watcher import run_directory_watcher

        logger.info("Starting directory watcher background task...")
        try:
            # Run in executor since it's a blocking function
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_directory_watcher)
        except Exception as e:
            logger.error(f"Directory watcher error: {e}", exc_info=True)

    async def start_imap_watcher(self):
        """Start the IMAP watcher in the background."""
        from app.workers.imap_watcher import run_imap_watcher

        logger.info("Starting IMAP watcher background task...")
        try:
            # Run in executor since it's a blocking function
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_imap_watcher)
        except Exception as e:
            logger.error(f"IMAP watcher error: {e}", exc_info=True)

    async def start_all(self):
        """Start all enabled background workers."""
        # Check environment variables to see which workers to enable
        enable_directory_watcher = os.getenv("ENABLE_DIRECTORY_WATCHER", "false").lower() == "true"
        enable_imap_watcher = os.getenv("ENABLE_IMAP_WATCHER", "false").lower() == "true"

        if enable_directory_watcher:
            task = asyncio.create_task(self.start_directory_watcher())
            self.tasks.append(task)
            logger.info("Directory watcher enabled and started")

        if enable_imap_watcher:
            task = asyncio.create_task(self.start_imap_watcher())
            self.tasks.append(task)
            logger.info("IMAP watcher enabled and started")

        if not self.tasks:
            logger.info("No background workers enabled")

    async def stop_all(self):
        """Stop all background workers."""
        self.should_stop = True
        logger.info("Stopping background workers...")

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        logger.info("All background workers stopped")


# Global instance
worker_manager = BackgroundWorkerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for background workers."""
    # Startup
    logger.info("Starting background workers...")
    await worker_manager.start_all()

    yield

    # Shutdown
    logger.info("Shutting down background workers...")
    await worker_manager.stop_all()
