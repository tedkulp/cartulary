"""Writing the tags a stage asked for onto a Document.

Tag policy — what a tag name may be, when one is coined rather than reused, what
colour a new one gets — lives here rather than in the runner, so the runner reads as
plumbing and changes only when the plumbing does.
"""
import logging
import random
from typing import List, Optional, Sequence, Set
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.tag import Tag

logger = logging.getLogger(__name__)

MAX_TAG_LENGTH = 50


def replace_tags(db: Session, doc: Document, names: Sequence[str]) -> int:
    """Replace the Document's tags with these, creating any the archive lacks.

    Returns how many landed, which is not how many were asked for: a name that cleans
    away to nothing, or repeats one already taken, was never a tag.
    """
    wanted: List[Tag] = []
    seen: Set[str] = set()

    for raw in names:
        name = raw.strip().lower()[:MAX_TAG_LENGTH]
        if not name or name in seen:
            continue
        seen.add(name)
        wanted.append(_tag_named(db, name, created_by=doc.owner_id))

    doc.tags = wanted
    return len(wanted)


def _tag_named(db: Session, name: str, *, created_by: Optional[UUID]) -> Tag:
    """The archive's tag of this name, coining it if there is none.

    Tags are global and named uniquely, so two workers describing two documents can
    reach for the same new name at once; the loser of that race re-reads rather than
    losing the tag or failing the stage.
    """
    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing is not None:
        return existing

    tag = Tag(name=name, color=_random_color(), created_by=created_by)
    try:
        with db.begin_nested():
            db.add(tag)
        logger.info(f"Created new tag: {name}")
        return tag
    except IntegrityError:
        logger.info(f"Tag {name} was created concurrently; using the existing one")
        return db.query(Tag).filter(Tag.name == name).one()


def _random_color() -> str:
    """A random mid-range hex colour for a tag background.

    HSL with the hue free, saturation 40-70% (vivid enough to read, not garish) and
    lightness 35-60% (dark enough for white text, light enough not to look black).
    """
    h = random.randint(0, 359)
    s = random.randint(40, 70) / 100.0
    lightness = random.randint(35, 60) / 100.0

    c = (1 - abs(2 * lightness - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = lightness - c / 2

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    r, g, b = int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"
