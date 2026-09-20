"""Capabilities API endpoint: what this deployment has turned on."""
import logging
from typing import Callable, Optional

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.providers.factory import get_assistant_model, get_embedder, get_vision_model
from app.schemas.capabilities import CapabilitiesResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


def _is_available(build: Callable[[], Optional[object]], capability: str) -> bool:
    """Whether `build` yields a model, treating a misconfigured one as unavailable.

    A builder raises on a setting it cannot make sense of, such as an unknown
    provider. This endpoint exists to tell a client what works, so it must still
    answer — but the operator needs to know, so the failure is logged in full.
    """
    try:
        return build() is not None
    except Exception:
        logger.exception("Capability %r is misconfigured; reporting it as off", capability)
        return False


@router.get(
    "",
    response_model=CapabilitiesResponse,
    summary="Report which optional capabilities are on",
    description=(
        "Report which optional capabilities this deployment can do, so a client can "
        "hide or disable a feature rather than offer one whose endpoints answer 503."
    ),
)
def get_capabilities(
    current_user: User = Depends(get_current_user),
) -> CapabilitiesResponse:
    """Read each capability off the factory: a capability is on when its model exists."""
    # Chat and metadata extraction are the same model, so they are asked once
    assistant = _is_available(get_assistant_model, "assistant model")
    return CapabilitiesResponse(
        ocr=_is_available(get_vision_model, "vision model"),
        embeddings=_is_available(get_embedder, "embedder"),
        chat=assistant,
        metadata=assistant,
    )
