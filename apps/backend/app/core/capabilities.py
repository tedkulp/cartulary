"""How an endpoint refuses work a disabled capability cannot do.

A capability — OCR, embeddings, chat, metadata extraction — is on when its builder
in `app/providers/factory.py` returns a model rather than None. Every endpoint that
needs one refuses the same way, through this one function, so the status code and
the instruction to the operator live here rather than in each handler. See ADR 0003.
"""
from fastapi import HTTPException, status

CAPABILITY_DISABLED_STATUS = status.HTTP_503_SERVICE_UNAVAILABLE

CAPABILITY_DISABLED_RESPONSE = {
    CAPABILITY_DISABLED_STATUS: {
        "description": "The capability this endpoint needs is turned off in configuration."
    }
}

# What an operator has to do to turn each model back on. Shared by every endpoint
# needing that model, so the instruction is written once and cannot drift.
TURN_ON_ASSISTANT_MODEL = (
    "Set LLM_ENABLED=true, along with LLM_PROVIDER, LLM_MODEL and the "
    "matching API key, then restart the backend."
)
TURN_ON_EMBEDDER = (
    "Set EMBEDDING_ENABLED=true, along with EMBEDDING_PROVIDER, EMBEDDING_MODEL "
    "and EMBEDDING_DIMENSION, then restart the backend."
)


def capability_disabled_error(missing: str, turn_on: str) -> HTTPException:
    """The refusal to raise when a capability this endpoint needs is off.

    Args:
        missing: What this endpoint needs and did not get, in the caller's terms,
            e.g. "Chat needs an assistant model, and none is configured."
        turn_on: How an operator turns it back on — one of the TURN_ON_* constants.
            Nothing the caller sends can fix this, so the detail is written for
            whoever runs the deployment.
    """
    return HTTPException(
        status_code=CAPABILITY_DISABLED_STATUS, detail=f"{missing} {turn_on}"
    )
