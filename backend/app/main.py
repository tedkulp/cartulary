"""Main FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.startup import startup_checks

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Document management system with OCR, RAG search, and LLM metadata extraction",
    version="0.1.0",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)


@app.on_event("startup")
async def startup_event():
    """Run startup checks and initialization."""
    try:
        startup_checks()
    except Exception as e:
        logger.error(f"Startup validation failed: {e}")
        # Log the error but don't prevent startup (database might not be ready yet)
        # The validation will run again on first use

# Configure CORS
cors_origins = settings.BACKEND_CORS_ORIGINS or ["http://localhost:5173", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers
from app.api.v1 import auth, documents, search, tags, users, sharing, import_sources, oidc, activity_logs

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(search.router, prefix=settings.API_V1_PREFIX)
app.include_router(tags.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(sharing.router, prefix=settings.API_V1_PREFIX)
app.include_router(import_sources.router, prefix=settings.API_V1_PREFIX)
app.include_router(oidc.router, prefix=f"{settings.API_V1_PREFIX}/auth/oidc", tags=["oidc"])
app.include_router(activity_logs.router, prefix=f"{settings.API_V1_PREFIX}/activity-logs", tags=["activity-logs"])
