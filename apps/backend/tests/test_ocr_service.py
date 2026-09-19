"""Tests for OCRService."""
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import fitz
import pytest

from app.providers import ModelError
from app.services.ocr_service import OCRService
from tests.fakes import ConcurrentChatModel, ScriptedChatModel

LONG_TEXT = "This page carries plenty of embedded text, well over fifty characters."
SHORT_TEXT = "Page 2"
VISION_TEXT = "Raw text the vision model read off the page"
FORMATTED_TEXT = "# Formatted markdown"
# Generous: it bounds how long a wedged concurrency test hangs, not how fast one passes.
BARRIER_TIMEOUT = 10.0


def make_pdf(tmp_path: Path, pages: List[Optional[str]]) -> str:
    """Write a PDF with one page per entry: its embedded text, or None for a blank page."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    path = tmp_path / "doc.pdf"
    doc.save(path)
    doc.close()
    return str(path)


@pytest.fixture
def ocr_service() -> OCRService:
    """OCR service with no models, for tests that never reach a model."""
    return OCRService()


@pytest.fixture
def image_path(tmp_path) -> str:
    """A tiny PNG image file."""
    path = tmp_path / "scan.png"
    path.write_bytes(fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), False).tobytes("png"))
    return str(path)


class TestExtractTextFromPdf:
    """Tests for OCRService.extract_text() on PDFs."""

    def test_uses_long_embedded_text_without_vision(self, tmp_path):
        """A page with at least 50 chars of embedded text is used as-is."""
        vision = ScriptedChatModel()
        service = OCRService(vision_model=vision, formatter_model=ScriptedChatModel())

        text = service.extract_text(make_pdf(tmp_path, [LONG_TEXT]))

        assert text.strip() == LONG_TEXT
        assert vision.calls == []

    def test_short_embedded_text_goes_to_vision_then_formatter(self, tmp_path):
        """A page with under 50 chars of embedded text is read by the vision model."""
        vision = ScriptedChatModel(VISION_TEXT)
        formatter = ScriptedChatModel(FORMATTED_TEXT)
        service = OCRService(vision_model=vision, formatter_model=formatter)

        text = service.extract_text(make_pdf(tmp_path, [SHORT_TEXT]))

        assert text == FORMATTED_TEXT
        assert len(vision.calls) == 1
        assert VISION_TEXT in formatter.calls[0][-1].content

    def test_force_ocr_ignores_embedded_text(self, tmp_path):
        """Forcing OCR sends even a page with long embedded text to the vision model."""
        vision = ScriptedChatModel(VISION_TEXT)
        service = OCRService(vision_model=vision, formatter_model=ScriptedChatModel(FORMATTED_TEXT))

        text = service.extract_text(make_pdf(tmp_path, [LONG_TEXT]), force_ocr=True)

        assert text == FORMATTED_TEXT
        assert LONG_TEXT not in text
        assert len(vision.calls) == 1

    def test_force_ocr_failure_does_not_fall_back_to_embedded_text(self, tmp_path):
        """When forced OCR fails, the page yields nothing rather than its embedded text."""
        service = OCRService(vision_model=ScriptedChatModel(ModelError("timed out")))

        assert service.extract_text(make_pdf(tmp_path, [LONG_TEXT]), force_ocr=True) == ""

    def test_short_vision_output_skips_formatter(self, tmp_path):
        """Vision output under 10 chars is used as-is, without calling the formatter."""
        formatter = ScriptedChatModel()
        service = OCRService(vision_model=ScriptedChatModel("  tiny \n"), formatter_model=formatter)

        text = service.extract_text(make_pdf(tmp_path, [None]))

        assert text == "tiny"
        assert formatter.calls == []

    def test_no_formatter_model_returns_raw_vision_text(self, tmp_path):
        """With no formatter model, pass 2 is skipped."""
        service = OCRService(vision_model=ScriptedChatModel(f"  {VISION_TEXT}\n"))

        assert service.extract_text(make_pdf(tmp_path, [None])) == VISION_TEXT

    def test_model_error_on_one_page_keeps_other_pages(self, tmp_path):
        """A vision failure on one page doesn't lose the text of the others."""
        vision = ScriptedChatModel(ModelError("model went away"), VISION_TEXT)
        service = OCRService(vision_model=vision)

        text = service.extract_text(make_pdf(tmp_path, [None, LONG_TEXT, None]))

        assert LONG_TEXT in text
        assert VISION_TEXT in text
        assert len(vision.calls) == 2

    def test_page_image_reaches_vision_model_as_png(self, tmp_path):
        """The rendered page is sent to the vision model as PNG bytes."""
        vision = ScriptedChatModel(VISION_TEXT)
        service = OCRService(vision_model=vision)

        service.extract_text(make_pdf(tmp_path, [None]))

        [message] = vision.calls[0]
        [image] = message.images
        assert image.startswith(b"\x89PNG\r\n\x1a\n")

    def test_no_vision_model_uses_embedded_text_only(self, tmp_path, ocr_service):
        """With no vision model, short embedded text is still used and blank pages yield nothing."""
        text = ocr_service.extract_text(make_pdf(tmp_path, [SHORT_TEXT, None, LONG_TEXT]))

        assert SHORT_TEXT in text
        assert LONG_TEXT in text


class TestExtractTextFromImage:
    """Tests for OCRService.extract_text() on image files."""

    def test_image_bytes_reach_vision_model(self, image_path):
        """An image file's bytes are sent to the vision model unchanged."""
        vision = ScriptedChatModel(VISION_TEXT)
        service = OCRService(vision_model=vision)

        assert service.extract_text(image_path) == VISION_TEXT
        assert list(vision.calls[0][0].images) == [Path(image_path).read_bytes()]

    def test_no_vision_model_yields_nothing(self, image_path, ocr_service):
        """With no vision model, images yield nothing."""
        assert ocr_service.extract_text(image_path) is None

    def test_model_error_yields_nothing(self, image_path):
        """A vision failure on an image is reported as no text, not raised."""
        service = OCRService(vision_model=ScriptedChatModel(ModelError("timed out")))

        assert service.extract_text(image_path) is None


class TestFormatterOutputCleanup:
    """Artifacts a reasoning or chatty formatter model leaves around its markdown are removed."""

    def extracted_given_reply(
        self, image_path: str, formatter_reply: str, vision_text: str = VISION_TEXT
    ) -> Optional[str]:
        """The text extracted from an image when the formatter model replies as given."""
        service = OCRService(
            vision_model=ScriptedChatModel(vision_text),
            formatter_model=ScriptedChatModel(formatter_reply),
        )
        return service.extract_text(image_path)

    def test_removes_think_blocks(self, image_path):
        """Reasoning inside <think> tags, anywhere in the reply, is dropped."""
        reply = (
            "<think>\nThe user wants markdown.\n</think>\n\n# Invoice\n\n"
            "<THINK>keep order</THINK>Total: 42.00"
        )

        assert self.extracted_given_reply(image_path, reply) == "# Invoice\n\nTotal: 42.00"

    def test_removes_leading_reasoning_closed_without_opening_tag(self, image_path):
        """Reasoning whose opening tag the chat template supplied ends at a bare </think>."""
        reply = "Okay, the text is an invoice.\n</think>\n\n# Invoice"

        assert self.extracted_given_reply(image_path, reply) == "# Invoice"

    def test_drops_reasoning_that_never_closes(self, image_path):
        """A reply cut off inside <think> keeps only the text before the tag."""
        reply = "# Invoice\n\n<think>\nWait, should the total be a heading? Let me"

        assert self.extracted_given_reply(image_path, reply) == "# Invoice"

    def test_reply_that_is_only_unfinished_reasoning_yields_nothing(self, image_path):
        """A reply cut off inside a leading <think> has no document text in it."""
        reply = "<think>\nThe user wants markdown. First I should"

        assert self.extracted_given_reply(image_path, reply) == ""

    @pytest.mark.parametrize("opening", ["```", "```markdown", "```md", "``` Markdown"])
    def test_unwraps_outer_code_fence(self, image_path, opening):
        """A reply wrapped whole in one code fence is unwrapped."""
        reply = f"\n{opening}\n# Invoice\n\nTotal: 42.00\n```\n"

        assert self.extracted_given_reply(image_path, reply) == "# Invoice\n\nTotal: 42.00"

    def test_keeps_separate_code_blocks_that_open_and_close_the_reply(self, image_path):
        """Two code blocks with text between them are content, not one wrapper."""
        reply = "```\nSKU 1001\n```\n\nShipped together with\n\n```\nSKU 2002\n```"

        assert self.extracted_given_reply(image_path, reply) == reply

    @pytest.mark.parametrize(
        "preamble",
        [
            "Here is the formatted text:",
            "Here's the Markdown:",
            "Sure! Here is the text converted to Markdown:",
            "Certainly, below is the formatted output:",
        ],
    )
    def test_strips_leading_preamble(self, image_path, preamble):
        """A chatty line introducing the markdown is dropped."""
        reply = f"{preamble}\n\n# Invoice\n\nTotal: 42.00"

        assert self.extracted_given_reply(image_path, reply) == "# Invoice\n\nTotal: 42.00"

    def test_strips_preamble_before_fenced_reply(self, image_path):
        """A preamble followed by a fenced reply loses both."""
        reply = "Here is the Markdown:\n```markdown\n# Invoice\n```"

        assert self.extracted_given_reply(image_path, reply) == "# Invoice"

    def test_keeps_preamble_like_lines_after_the_start(self, image_path):
        """Only the reply's first line can be a preamble; later lines are document content."""
        reply = "# Lab report\n\nBelow is the output of the test run:\n\nPassed"

        assert self.extracted_given_reply(image_path, reply) == reply


    def test_keeps_think_tags_the_page_itself_contains(self, image_path):
        """Tags the vision model read off the page are document content, not reasoning."""
        page = "Use the <think> tag to open a block and </think> to close it."
        reply = f"# Tag guide\n\n{page}\n\nMore content"

        assert self.extracted_given_reply(image_path, reply, vision_text=page) == reply

    def test_keeps_an_opening_line_the_page_itself_contains(self, image_path):
        """A first line the vision model read off the page is document content, not a preamble."""
        opening = "Here is the text of the agreement between the parties:"
        reply = f"{opening}\n\n1. Terms"

        assert self.extracted_given_reply(image_path, reply, vision_text=opening) == reply


class TestDetectLanguage:
    """Tests for OCRService.detect_language()."""

    def test_detects_english(self, ocr_service):
        """English prose is detected as English."""
        text = (
            "This invoice covers the services rendered during the month of "
            "March, and payment is due within thirty days of receipt."
        )
        assert ocr_service.detect_language(text) == "en"

    def test_detects_german(self, ocr_service):
        """Non-English text is not silently reported as English."""
        text = (
            "Diese Rechnung umfasst die im Monat Marz erbrachten Leistungen, "
            "und die Zahlung ist innerhalb von dreissig Tagen zu leisten."
        )
        assert ocr_service.detect_language(text) == "de"

    @pytest.mark.parametrize("text", ["", "   ", "\n\n", "123 456", "..."])
    def test_returns_default_for_textless_input(self, ocr_service, text):
        """Empty or unusable text falls back to 'en' instead of raising."""
        assert ocr_service.detect_language(text) == "en"

    def test_is_deterministic(self, ocr_service):
        """Repeated detection of the same short text gives the same result.

        langdetect is randomized unless its factory is seeded, so this guards
        the seeding in ocr_service against being dropped.
        """
        text = "Total 42.00 Date 2026-01-26 Invoice"
        results = {ocr_service.detect_language(text) for _ in range(20)}
        assert len(results) == 1


def page_images(pdf_path: str) -> List[bytes]:
    """The page images OCRService renders, in page order, so a fake can key replies on them."""
    with fitz.open(pdf_path) as doc:
        return [page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png") for page in doc]


def page_index(pdf_path: str) -> Dict[bytes, int]:
    """Maps each page image to its zero-based page number."""
    return {image: number for number, image in enumerate(page_images(pdf_path))}


def numbered_pages(count: int) -> List[str]:
    """Short, visually distinct page texts: short enough that every page goes to vision OCR."""
    return [f"Page {number}" for number in range(1, count + 1)]


class TestPageConcurrency:
    """Tests for OCRService's concurrent per-page OCR."""

    def test_pages_keep_document_order_when_ocr_finishes_out_of_order(self, tmp_path):
        """Combined text follows page order even when later pages finish OCR first."""
        pdf = make_pdf(tmp_path, numbered_pages(4))
        index_of = page_index(pdf)
        replies = [f"text of page {number}" for number in range(1, 5)]
        started = threading.Barrier(4, timeout=BARRIER_TIMEOUT)
        finished = [threading.Event() for _ in replies]

        def reply(messages):
            page = index_of[messages[-1].images[0]]
            started.wait()
            # Each page waits for the one after it, so page 4 finishes first and page 1 last
            if page + 1 < len(replies):
                assert finished[page + 1].wait(timeout=BARRIER_TIMEOUT)
            finished[page].set()
            return replies[page]

        service = OCRService(vision_model=ConcurrentChatModel(reply), page_concurrency=4)

        assert service.extract_text(pdf) == "\n\n".join(replies)

    def test_runs_pages_in_parallel_up_to_the_concurrency_setting(self, tmp_path):
        """With a concurrency of 3, three pages are in the vision model at the same time."""
        pdf = make_pdf(tmp_path, numbered_pages(6))
        # Breaks, failing the test, unless three pages really are in flight together
        together = threading.Barrier(3, timeout=BARRIER_TIMEOUT)

        def reply(messages):
            together.wait()
            return "text of a page"

        vision = ConcurrentChatModel(reply)
        service = OCRService(vision_model=vision, page_concurrency=3)

        service.extract_text(pdf)

        assert vision.peak_running == 3
        assert len(vision.calls) == 6

    def test_a_slow_page_does_not_hold_back_the_pages_behind_it(self, tmp_path):
        """A page still running never blocks submission of pages whose slots have freed.

        Collecting the oldest in-flight page instead of any finished one would wedge here:
        page 1 only finishes once page 4 has started, and page 4 is only submitted once a
        slot frees, which under oldest-first means waiting for page 1.
        """
        pdf = make_pdf(tmp_path, numbered_pages(4))
        index_of = page_index(pdf)
        last_page_started = threading.Event()

        def reply(messages):
            page = index_of[messages[-1].images[0]]
            if page == len(index_of) - 1:
                last_page_started.set()
            elif page == 0:
                assert last_page_started.wait(timeout=BARRIER_TIMEOUT)
            return f"text of page {page + 1}"

        service = OCRService(vision_model=ConcurrentChatModel(reply), page_concurrency=2)

        assert service.extract_text(pdf) == "\n\n".join(
            f"text of page {number}" for number in range(1, 5)
        )

    def test_defaults_to_one_page_at_a_time(self, tmp_path):
        """Without a concurrency setting, pages are OCR'd one after another as before."""
        pdf = make_pdf(tmp_path, numbered_pages(3))

        def reply(messages):
            time.sleep(0.05)  # long enough that any overlap would be observed
            return "text of a page"

        vision = ConcurrentChatModel(reply)
        service = OCRService(vision_model=vision)

        service.extract_text(pdf)

        assert vision.peak_running == 1
        assert len(vision.calls) == 3

    def test_failure_on_one_page_keeps_the_pages_beside_it(self, tmp_path):
        """A vision failure is still isolated to its own page when pages run concurrently."""
        pdf = make_pdf(tmp_path, ["Page 1", LONG_TEXT, "Page 3"])
        index_of = page_index(pdf)

        def reply(messages):
            if index_of[messages[-1].images[0]] == 0:
                raise ModelError("model went away")
            return "text of page three"

        service = OCRService(vision_model=ConcurrentChatModel(reply), page_concurrency=3)

        text = service.extract_text(pdf)

        assert text.index("Page 1") < text.index(LONG_TEXT) < text.index("text of page three")

    def test_embedded_text_pages_keep_their_place_between_ocr_pages(self, tmp_path):
        """Pages that need no OCR are ordered against the concurrent ones correctly."""
        pdf = make_pdf(tmp_path, ["Page 1", LONG_TEXT, "Page 3", LONG_TEXT])
        service = OCRService(
            vision_model=ConcurrentChatModel(lambda messages: "text of an OCR'd page"),
            page_concurrency=2,
        )

        text = service.extract_text(pdf)

        assert [page.strip() for page in text.split("\n\n")] == [
            "text of an OCR'd page",
            LONG_TEXT,
            "text of an OCR'd page",
            LONG_TEXT,
        ]

    @pytest.mark.parametrize("concurrency", [0, -1])
    def test_rejects_a_concurrency_below_one(self, concurrency):
        """A page concurrency under 1 is a configuration error, not a silent no-op."""
        with pytest.raises(ValueError, match="page_concurrency"):
            OCRService(page_concurrency=concurrency)
