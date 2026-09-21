"""Splitting a Document's text into the pieces that get embedded.

One rule and one invariant. The rule: a chunk ends at the last sentence boundary
before the size cap, or at the cap when no boundary falls there. The invariant: each
chunk starts strictly after the one before it, so chunking always terminates.

The invariant is the whole point. The chunker this replaces moved the next start
back by the overlap unconditionally, so a sentence boundary landing within `overlap`
characters of a chunk's start moved the start *backwards* and the loop never
advanced: `"A. " + "x" * 600` at 500/50 hung. Here a boundary inside the overlap is
ignored in favour of the cap, and the next start is floored at `previous + 1`
regardless.

Pure: no settings, no database, no model. The embedding stage passes
`EMBEDDING_CHUNK_SIZE` and `EMBEDDING_CHUNK_OVERLAP` in.
"""
import re
from typing import List, Optional

__all__ = ["chunk"]

# A sentence ends at .!? — with any closing quote or bracket — followed by whitespace.
# Requiring the whitespace keeps "3.14" and "U.S.A." from ending a sentence.
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*(?=\s)")


def chunk(text: str, size: int, overlap: int) -> List[str]:
    """Split `text` into chunks of at most `size` characters overlapping by `overlap`.

    Chunks are stripped and never empty, so text that is empty or all whitespace
    yields no chunks and text shorter than `size` yields exactly one. Stripping can
    shave whitespace off an overlap that begins or ends on it; the words either side
    of the boundary still appear in both chunks, which is what the overlap is for.

    An `overlap` of `size` or more would leave no room to advance, so it is capped at
    `size - 1`. A `size` below 1, or a negative `overlap`, is a programming error.
    """
    if size < 1:
        raise ValueError(f"chunk size must be at least 1, got {size}")
    if overlap < 0:
        raise ValueError(f"chunk overlap cannot be negative, got {overlap}")
    overlap = min(overlap, size - 1)

    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        if end < length:
            boundary = _last_sentence_boundary(text, start, end, after=start + overlap)
            if boundary is not None:
                end = boundary

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break

        # The invariant, enforced here: the next chunk starts strictly after this one,
        # whatever the overlap asks for. Taking the overlap unconditionally is what let
        # the old chunker walk backwards and never finish.
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start

    return chunks


def _last_sentence_boundary(text: str, start: int, limit: int, *, after: int) -> Optional[int]:
    """Where the last sentence ends within `text[start:limit]`, past `after`.

    The result is the index one past the sentence's final character, so it can be used
    as an exclusive end. A boundary at or before `after` — that is, inside the overlap —
    is not offered, because ending there would put the next chunk's start back where
    this one began.
    """
    best: Optional[int] = None
    # One past `limit`, so a boundary whose whitespace sits at `limit` is still seen.
    for match in _SENTENCE_END.finditer(text, start, min(limit + 1, len(text))):
        end = match.end()
        if after < end <= limit:
            best = end
    return best
