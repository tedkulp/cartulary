"""The transition table: status and capabilities in, the next stage or nothing out.

Exhaustive and pure — every status by every capability combination, no fixtures and
no database. The table is the whole description of the machine, so a test that only
sampled it would leave the interesting rows unread.
"""
import itertools
from typing import Optional

import pytest

from app.processing import ProcessingStatus, Stage, next_stage

CAPABILITIES = list(itertools.product([False, True], repeat=2))


class TestProcessingStatus:
    """The stored strings are the contract with the database; nothing may drift."""

    def test_holds_exactly_the_seven_stored_values(self) -> None:
        assert {status.value for status in ProcessingStatus} == {
            "pending",
            "processing",
            "ocr_complete",
            "ocr_failed",
            "embedding_complete",
            "llm_complete",
            "failed",
        }

    def test_compares_equal_to_the_stored_string(self) -> None:
        """A StrEnum, so a row read back as a bare string still matches."""
        assert ProcessingStatus.OCR_COMPLETE == "ocr_complete"
        assert ProcessingStatus("ocr_failed") is ProcessingStatus.OCR_FAILED


class TestNextStage:
    """A capability is on when its builder returned a model, never by a setting (ADR 0003)."""

    @pytest.mark.parametrize("has_embedder,has_assistant", CAPABILITIES)
    def test_pending_starts_at_ocr_whatever_else_is_on(
        self, has_embedder: bool, has_assistant: bool
    ) -> None:
        assert next_stage(ProcessingStatus.PENDING, has_embedder, has_assistant) is Stage.OCR

    @pytest.mark.parametrize(
        "status",
        [
            ProcessingStatus.PROCESSING,
            ProcessingStatus.OCR_FAILED,
            ProcessingStatus.LLM_COMPLETE,
            ProcessingStatus.FAILED,
        ],
    )
    @pytest.mark.parametrize("has_embedder,has_assistant", CAPABILITIES)
    def test_terminal_and_in_flight_states_lead_nowhere(
        self, status: ProcessingStatus, has_embedder: bool, has_assistant: bool
    ) -> None:
        """In flight, failed, or finished: nothing to enqueue, whatever is configured."""
        assert next_stage(status, has_embedder, has_assistant) is None

    @pytest.mark.parametrize(
        "has_embedder,has_assistant,expected",
        [
            (True, True, Stage.EMBEDDING),
            (True, False, Stage.EMBEDDING),
            (False, True, Stage.METADATA),
            (False, False, None),
        ],
    )
    def test_ocr_complete_prefers_embedding_then_metadata(
        self, has_embedder: bool, has_assistant: bool, expected: Optional[Stage]
    ) -> None:
        """With no embedder OCR chains straight to metadata extraction."""
        assert next_stage(ProcessingStatus.OCR_COMPLETE, has_embedder, has_assistant) is expected

    @pytest.mark.parametrize(
        "has_embedder,has_assistant,expected",
        [
            (True, True, Stage.METADATA),
            (False, True, Stage.METADATA),
            (True, False, None),
            (False, False, None),
        ],
    )
    def test_embedding_complete_leads_to_metadata_when_there_is_an_assistant(
        self, has_embedder: bool, has_assistant: bool, expected: Optional[Stage]
    ) -> None:
        assert next_stage(
            ProcessingStatus.EMBEDDING_COMPLETE, has_embedder, has_assistant
        ) is expected

    @pytest.mark.parametrize("status", list(ProcessingStatus))
    @pytest.mark.parametrize("has_embedder,has_assistant", CAPABILITIES)
    def test_every_status_and_capability_pair_answers(
        self, status: ProcessingStatus, has_embedder: bool, has_assistant: bool
    ) -> None:
        """Total over its domain: no status by capability pair raises or falls through."""
        assert next_stage(status, has_embedder, has_assistant) in (None, *Stage)
