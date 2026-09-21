"""The stage functions: what each stage decides, given its inputs and its models.

Pure, so these run with no database, no broker and no model server — the models are
the fakes from `tests/fakes.py`. A stage returns what should be written; whether it
lands is the runner's business and is tested in `test_processing_runner.py`.
"""
import json
from datetime import date
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from app.processing import ProcessingStatus, run_embedding, run_metadata, run_ocr
from app.processing.stages import NO_TEXT_EXTRACTED, enrich_text
from app.providers.ports import ModelError
from tests.fakes import FakeEmbedder, ScriptedChatModel


class TestRunOcr:
    """The status a read ends at says whether there is anything to go on with."""

    def _run(self, extracted: Optional[str], *, path: str = "/tmp/invoice.png"):
        with patch("app.services.ocr_service.OCRService.extract_text", return_value=extracted), \
             patch("app.services.ocr_service.OCRService.detect_language", return_value="en"):
            return run_ocr(file_path=path, vision_model=None, formatter_model=None)

    def test_text_read_lands_at_ocr_complete_with_its_language(self) -> None:
        result = self._run("Invoice for one ton of Borrowdale slate.")

        assert result.status is ProcessingStatus.OCR_COMPLETE
        assert result.fields["ocr_text"] == "Invoice for one ton of Borrowdale slate."
        assert result.fields["ocr_language"] == "en"
        assert "processing_error" not in result.fields

    @pytest.mark.parametrize("extracted", [None, "", "   \n  "])
    def test_nothing_read_lands_at_ocr_failed_with_the_reason(
        self, extracted: Optional[str]
    ) -> None:
        """A page of whitespace is a page that could not be read."""
        result = self._run(extracted)

        assert result.status is ProcessingStatus.OCR_FAILED
        assert result.fields["ocr_text"] == ""
        assert result.fields["processing_error"] == NO_TEXT_EXTRACTED

    def test_reports_how_much_it_read(self) -> None:
        result = self._run("Six words is not very many")

        assert result.info["text_length"] == len("Six words is not very many")

    def test_counts_no_pages_for_a_file_that_is_not_a_pdf(self) -> None:
        result = self._run("Some text", path="/tmp/scan.png")

        assert "page_count" not in result.fields
        assert result.info["page_count"] is None

    def test_writes_nothing_itself(self) -> None:
        """A stage function returns fields; it never has a session to write them with."""
        result = self._run("Some text")

        assert result.embeddings is None
        assert result.tags is None
        assert not result.notify_updated


class TestRunOcrWithModels:
    """The same stage over a real OCRService, with the models scripted rather than patched."""

    def test_reads_an_image_with_the_vision_model_and_formats_it_with_the_formatter(
        self, tmp_path
    ) -> None:
        page = tmp_path / "scan.png"
        page.write_bytes(b"not really a png, but the vision model never looks")
        vision = ScriptedChatModel("two tons of borrowdale slate")
        formatter = ScriptedChatModel("# Invoice\n\nTwo tons of Borrowdale slate.")

        result = run_ocr(
            file_path=str(page), vision_model=vision, formatter_model=formatter
        )

        assert result.status is ProcessingStatus.OCR_COMPLETE
        assert result.fields["ocr_text"] == "# Invoice\n\nTwo tons of Borrowdale slate."
        assert len(vision.calls) == 1
        assert vision.calls[0][-1].images  # the page went to the model as an image
        assert len(formatter.calls) == 1

    def test_an_image_with_no_vision_model_reads_as_nothing(self, tmp_path) -> None:
        """With OCR off, an image yields nothing and the Document says why."""
        page = tmp_path / "scan.png"
        page.write_bytes(b"some bytes")

        result = run_ocr(file_path=str(page), vision_model=None, formatter_model=None)

        assert result.status is ProcessingStatus.OCR_FAILED
        assert result.fields["processing_error"] == NO_TEXT_EXTRACTED


class TestRunEmbedding:
    """What gets embedded is the document's metadata followed by its content."""

    def test_returns_a_chunk_and_a_vector_for_each_piece_of_text(self) -> None:
        embedder = FakeEmbedder(dimension=4)

        result = run_embedding(
            ocr_text="x" * 250, embedder=embedder, chunk_size=100, chunk_overlap=0
        )

        assert result.status is ProcessingStatus.EMBEDDING_COMPLETE
        assert result.embeddings is not None
        assert [len(chunk.text) for chunk in result.embeddings.chunks] == [100, 100, 50]
        assert all(len(chunk.vector) == 4 for chunk in result.embeddings.chunks)
        assert result.embeddings.model_name == "fake-embedder"
        assert result.info == {"embedding_count": 3, "chunk_count": 3}

    def test_overlaps_the_chunks_by_the_configured_amount(self) -> None:
        embedder = FakeEmbedder(dimension=4)

        result = run_embedding(
            ocr_text="".join(str(n % 10) for n in range(300)),
            embedder=embedder,
            chunk_size=100,
            chunk_overlap=30,
        )

        assert result.embeddings is not None
        first, second = (chunk.text for chunk in result.embeddings.chunks[:2])
        assert second.startswith(first[-30:])

    def test_embeds_the_title_tags_and_description_along_with_the_text(self) -> None:
        embedder = FakeEmbedder()

        result = run_embedding(
            ocr_text="Two tons of slate.",
            embedder=embedder,
            title="Slate invoice",
            description="From the quarry",
            tags=["invoice", "quarry"],
            chunk_size=10_000,
            chunk_overlap=0,
        )

        assert result.embeddings is not None
        embedded = result.embeddings.chunks[0].text
        assert "Title: Slate invoice" in embedded
        assert "Tags: invoice, quarry" in embedded
        assert "Description: From the quarry" in embedded
        assert embedded.endswith("Content:\nTwo tons of slate.")

    @pytest.mark.parametrize("ocr_text", [None, ""])
    def test_a_document_with_no_text_is_skipped_rather_than_moved(
        self, ocr_text: Optional[str]
    ) -> None:
        result = run_embedding(
            ocr_text=ocr_text, embedder=FakeEmbedder(), chunk_size=500, chunk_overlap=50
        )

        assert result.outcome == "skipped"
        assert result.status is None
        assert result.embeddings is None

    def test_a_provider_failure_is_raised_for_the_runner_to_record(self) -> None:
        class FailingEmbedder(FakeEmbedder):
            def embed(self, texts):
                raise ModelError("embedder unreachable")

        with pytest.raises(ModelError):
            run_embedding(
                ocr_text="Some text",
                embedder=FailingEmbedder(),
                chunk_size=500,
                chunk_overlap=50,
            )


class TestEnrichText:
    def test_text_with_no_metadata_is_embedded_as_it_stands(self) -> None:
        assert enrich_text("Just the words.") == "Just the words."


def _reply(**metadata: Any) -> ScriptedChatModel:
    """An assistant model scripted to answer one extraction with this metadata."""
    payload: Dict[str, Any] = {
        "title": "Unknown",
        "correspondent": "Unknown",
        "document_date": None,
        "document_type": "Unknown",
        "summary": "",
        "suggested_tags": [],
    }
    payload.update(metadata)
    return ScriptedChatModel(json.dumps(payload))


class TestRunMetadata:
    """What the assistant model says a document is, turned into fields to write."""

    def _run(self, model: ScriptedChatModel, **kwargs: Any):
        return run_metadata(
            ocr_text=kwargs.pop("ocr_text", "Two tons of Borrowdale slate."),
            original_filename=kwargs.pop("original_filename", "scan-0042.pdf"),
            assistant_model=model,
            **kwargs,
        )

    def test_records_what_the_model_found_and_lands_at_llm_complete(self) -> None:
        result = self._run(
            _reply(
                title="Slate invoice",
                correspondent="Borrowdale Quarry",
                document_date="1897-04-02",
                document_type="Invoice",
                summary="An invoice for two tons of slate.",
            )
        )

        assert result.status is ProcessingStatus.LLM_COMPLETE
        assert result.fields["extracted_title"] == "Slate invoice"
        assert result.fields["extracted_correspondent"] == "Borrowdale Quarry"
        assert result.fields["extracted_date"] == date(1897, 4, 2)
        assert result.fields["extracted_document_type"] == "Invoice"
        assert result.fields["extracted_summary"] == "An invoice for two tons of slate."
        assert result.notify_updated

    def test_leaves_out_everything_the_model_answered_unknown(self) -> None:
        """"Unknown" is the model saying it could not tell, not a value to store."""
        result = self._run(_reply(summary="Something happened."))

        assert "extracted_title" not in result.fields
        assert "extracted_correspondent" not in result.fields
        assert "extracted_document_type" not in result.fields
        assert "extracted_date" not in result.fields

    def test_takes_over_a_title_that_is_still_the_filename(self) -> None:
        result = self._run(_reply(title="Slate invoice"), current_title="scan-0042.pdf")

        assert result.fields["title"] == "Slate invoice"

    def test_leaves_a_title_someone_chose_alone(self) -> None:
        result = self._run(_reply(title="Slate invoice"), current_title="The slate bill")

        assert "title" not in result.fields
        assert result.fields["extracted_title"] == "Slate invoice"

    def test_fills_an_empty_description_from_the_summary(self) -> None:
        result = self._run(_reply(summary="An invoice."), current_description="   ")

        assert result.fields["description"] == "An invoice."

    def test_leaves_a_description_someone_wrote_alone(self) -> None:
        result = self._run(_reply(summary="An invoice."), current_description="Mine, thanks")

        assert "description" not in result.fields
        assert result.fields["extracted_summary"] == "An invoice."

    def test_ignores_a_date_the_model_made_up(self) -> None:
        """A date that will not parse is dropped, not written and not fatal."""
        result = self._run(_reply(document_date="sometime in April"))

        assert "extracted_date" not in result.fields
        assert result.status is ProcessingStatus.LLM_COMPLETE

    def test_tags_suggested_are_handed_to_the_runner_to_write(self) -> None:
        result = self._run(_reply(suggested_tags=["invoice", "quarry"]))

        assert result.tags == ["invoice", "quarry"]

    def test_suggesting_no_tags_leaves_the_documents_tags_alone(self) -> None:
        """An empty list means "nothing to add", never "clear what is there"."""
        result = self._run(_reply(suggested_tags=[]))

        assert result.tags is None

    def test_a_reply_with_no_tag_field_leaves_the_documents_tags_alone(self) -> None:
        """A model that left the tags out said the same as one that suggested none."""
        result = self._run(ScriptedChatModel('{"title": "Slate invoice"}'))

        assert result.tags is None
        assert result.fields["extracted_title"] == "Slate invoice"

    @pytest.mark.parametrize("ocr_text", [None, ""])
    def test_a_document_with_no_text_is_skipped_rather_than_moved(
        self, ocr_text: Optional[str]
    ) -> None:
        result = run_metadata(
            ocr_text=ocr_text,
            original_filename="scan.pdf",
            assistant_model=ScriptedChatModel(),
        )

        assert result.outcome == "skipped"
        assert result.status is None
        assert result.info == {"reason": "No text content"}

    def test_a_model_that_could_not_be_reached_raises_for_the_runner_to_retry(self) -> None:
        """A provider failure comes out as the ModelError it is, not as empty metadata.

        Writing `llm_complete` with nothing extracted would call a Document described
        that no model ever saw, and leave it there. See ADR 0007."""
        with pytest.raises(ModelError, match="assistant unreachable"):
            self._run(ScriptedChatModel(ModelError("assistant unreachable")))
