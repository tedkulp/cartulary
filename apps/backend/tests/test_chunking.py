"""Chunking: the rules a chunk follows, and the invariant that it cannot hang.

Pure, so these run with no database, no broker and no model server. The regression
case is the input that hung the chunker this replaces (#24): a sentence boundary
landing inside the overlap used to move the next start backwards.
"""
import pytest

from app.processing.chunking import chunk


class TestSizeAndTermination:
    """A chunk never exceeds the cap, and the start position always advances."""

    def test_text_shorter_than_the_size_is_one_chunk(self) -> None:
        assert chunk("Two tons of slate.", size=500, overlap=50) == ["Two tons of slate."]

    def test_empty_text_yields_no_chunks(self) -> None:
        assert chunk("", size=500, overlap=50) == []
        assert chunk("   \n\t ", size=500, overlap=50) == []

    def test_no_chunk_is_empty_or_over_the_cap(self) -> None:
        chunks = chunk("A. " * 400, size=100, overlap=20)

        assert chunks
        assert all(piece.strip() for piece in chunks)
        assert all(len(piece) <= 100 for piece in chunks)

    def test_a_sentence_boundary_inside_the_overlap_still_terminates(self) -> None:
        """The #24 regression: "A. " + 600 x's at the defaults used to hang."""
        chunks = chunk("A. " + "x" * 600, size=500, overlap=50)

        assert 1 < len(chunks) <= 3
        assert "".join(chunks).count("x") >= 600
        assert all(len(piece) <= 500 for piece in chunks)

    def test_every_chunk_covers_new_text(self) -> None:
        text = "".join(f"Sentence number {n}. " for n in range(200))

        chunks = chunk(text, size=120, overlap=40)

        starts = [text.index(piece) for piece in chunks]
        assert starts == sorted(set(starts))
        assert all(later > earlier for earlier, later in zip(starts, starts[1:]))

    def test_an_overlap_as_large_as_the_size_cannot_stall(self) -> None:
        chunks = chunk("x" * 1000, size=100, overlap=100)

        assert chunks
        assert "".join(chunks).count("x") >= 1000
        assert len(chunks) < 1000

    def test_a_size_below_one_is_a_programming_error(self) -> None:
        with pytest.raises(ValueError):
            chunk("Two tons of slate.", size=0, overlap=0)

    def test_a_negative_overlap_is_a_programming_error(self) -> None:
        with pytest.raises(ValueError):
            chunk("Two tons of slate.", size=100, overlap=-1)


class TestOverlap:
    """The overlap operators configure is carried into the next chunk."""

    def test_consecutive_chunks_share_the_configured_overlap(self) -> None:
        text = "".join(str(n % 10) for n in range(1000))

        chunks = chunk(text, size=100, overlap=30)

        assert len(chunks) > 3
        for earlier, later in zip(chunks, chunks[1:]):
            assert later.startswith(earlier[-30:])

    def test_no_overlap_means_the_chunks_are_disjoint(self) -> None:
        text = "".join(str(n % 10) for n in range(300))

        chunks = chunk(text, size=100, overlap=0)

        assert "".join(chunks) == text


class TestSentenceBoundaries:
    """A chunk ends on a sentence where one is available, and at the cap where none is."""

    def test_ends_at_the_last_sentence_boundary_before_the_cap(self) -> None:
        text = "One sentence here. Two sentences here. " + "x" * 200

        first = chunk(text, size=60, overlap=0)[0]

        assert first == "One sentence here. Two sentences here."

    def test_ends_at_the_cap_when_no_sentence_boundary_falls_before_it(self) -> None:
        first = chunk("x" * 300, size=100, overlap=0)[0]

        assert first == "x" * 100

    def test_a_question_or_exclamation_ends_a_sentence(self) -> None:
        text = "Is this slate? Yes, it is! " + "x" * 200

        first = chunk(text, size=60, overlap=0)[0]

        assert first == "Is this slate? Yes, it is!"

    def test_a_boundary_inside_the_overlap_is_ignored(self) -> None:
        """Ending there would put the next chunk's start back where this one began."""
        chunks = chunk("A. " + "x" * 300, size=100, overlap=20)

        assert chunks[0] == "A. " + "x" * 97
        assert chunks[1].startswith("x")
