"""
Which Documents a user can reach, over every read path.

One test file for a rule that used to be written in six places. Each read path
is asked the same question about the same fixture data, so a path that forgets
the access filter fails here rather than in production. See ADR 0004 and 0005.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from app.config import settings
from app.core.permissions import PermissionLevel, accessible_documents
from app.models.document import Document
from app.models.sharing import DocumentShare
from app.models.user import User
from app.services.search_service import SearchService
from app.services.vector_search_service import VectorSearchService


# The embedding column is built from this setting, so the fixture vectors must
# match whatever the environment running the tests is configured for.
DIMENSION = settings.EMBEDDING_DIMENSION


def make_user(email: str, is_superuser: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x",
        is_active=True,
        is_superuser=is_superuser,
    )


def make_document(title: str, owner: User, is_public: bool = False) -> Document:
    return Document(
        id=uuid.uuid4(),
        title=title,
        original_filename=f"{title}.pdf",
        file_path=f"/tmp/{title}.pdf",
        file_size=1,
        mime_type="application/pdf",
        checksum=uuid.uuid4().hex,
        ocr_text=f"{title} borrowdale slate invoice",
        owner_id=owner.id,
        is_public=is_public,
        processing_status="llm_complete",
    )


class FakeEmbedder:
    """An embedder that always returns the same vector, so every chunk matches."""

    dimension = DIMENSION

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * DIMENSION for _ in texts]


@pytest.fixture
def world(db_session):
    """
    One document of each kind, and the users who can or cannot reach them.

    - owned: the reader's own document
    - public: a stranger's document marked public
    - shared: a stranger's document shared with the reader, no expiry
    - expired: a stranger's document whose share has lapsed
    - private: a stranger's document, nothing granted
    """
    from app.models.document import DocumentEmbedding

    reader = make_user("reader@example.com")
    stranger = make_user("stranger@example.com")
    root = make_user("root@example.com", is_superuser=True)
    db_session.add_all([reader, stranger, root])
    db_session.flush()

    documents = {
        "owned": make_document("owned", reader),
        "public": make_document("public", stranger, is_public=True),
        "shared": make_document("shared", stranger),
        "expired": make_document("expired", stranger),
        "private": make_document("private", stranger),
    }
    db_session.add_all(documents.values())
    db_session.flush()

    db_session.add_all(
        [
            DocumentShare(
                id=uuid.uuid4(),
                document_id=documents["shared"].id,
                shared_with_user_id=reader.id,
                shared_by_user_id=stranger.id,
                permission_level=PermissionLevel.WRITE,
                expires_at=None,
            ),
            DocumentShare(
                id=uuid.uuid4(),
                document_id=documents["expired"].id,
                shared_with_user_id=reader.id,
                shared_by_user_id=stranger.id,
                permission_level=PermissionLevel.READ,
                expires_at=datetime.utcnow() - timedelta(days=1),
            ),
        ]
    )

    # Every document gets one chunk, so semantic search can reach all of them
    # and only the access filter decides what comes back.
    db_session.add_all(
        [
            DocumentEmbedding(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=0,
                chunk_text=f"{name} chunk",
                embedding=[0.1] * DIMENSION,
                embedding_model="fake",
            )
            for name, document in documents.items()
        ]
    )
    db_session.commit()

    return {
        "reader": reader,
        "stranger": stranger,
        "root": root,
        "documents": documents,
    }


READABLE = {"owned", "public", "shared"}
UNREADABLE = {"expired", "private"}


def titles(documents) -> set:
    return {document.title for document in documents}


class TestAccessibleDocuments:
    """The filter itself."""

    def test_reader_sees_owned_public_and_shared(self, db_session, world):
        found = (
            db_session.query(Document).filter(accessible_documents(world["reader"])).all()
        )

        assert titles(found) == READABLE

    def test_expired_share_grants_nothing(self, db_session, world):
        found = (
            db_session.query(Document).filter(accessible_documents(world["reader"])).all()
        )

        assert "expired" not in titles(found)

    def test_public_confers_read_only(self, db_session, world):
        writable = (
            db_session.query(Document)
            .filter(accessible_documents(world["reader"], PermissionLevel.WRITE))
            .all()
        )

        # "shared" is a write share; "public" is readable but not writable.
        assert titles(writable) == {"owned", "shared"}

    def test_a_read_share_does_not_grant_write(self, db_session, world):
        share = (
            db_session.query(DocumentShare)
            .filter(DocumentShare.document_id == world["documents"]["expired"].id)
            .one()
        )
        share.expires_at = datetime.utcnow() + timedelta(days=1)
        db_session.commit()

        writable = (
            db_session.query(Document)
            .filter(accessible_documents(world["reader"], PermissionLevel.WRITE))
            .all()
        )

        assert "expired" not in titles(writable)

    def test_superuser_sees_everything(self, db_session, world):
        found = db_session.query(Document).filter(accessible_documents(world["root"])).all()

        assert titles(found) == READABLE | UNREADABLE

    def test_stranger_sees_only_their_own(self, db_session, world):
        found = (
            db_session.query(Document).filter(accessible_documents(world["stranger"])).all()
        )

        assert titles(found) == {"public", "shared", "expired", "private"}

    def test_each_document_appears_once(self, db_session, world):
        """A second share must not duplicate the document in the results."""
        db_session.add(
            DocumentShare(
                id=uuid.uuid4(),
                document_id=world["documents"]["shared"].id,
                shared_with_user_id=world["reader"].id,
                shared_by_user_id=world["stranger"].id,
                permission_level=PermissionLevel.READ,
            )
        )
        db_session.commit()

        found = (
            db_session.query(Document).filter(accessible_documents(world["reader"])).all()
        )

        assert len(found) == len(READABLE)


class TestFullTextSearch:
    """Read path: SearchService."""

    def test_search_reaches_shared_and_public_documents(self, db_session, world):
        results = SearchService(db_session).search_documents("slate", world["reader"])

        assert titles(results) == READABLE

    def test_blank_query_obeys_the_same_rule(self, db_session, world):
        results = SearchService(db_session).search_documents("  ", world["reader"])

        assert titles(results) == READABLE

    def test_count_matches_what_search_returns(self, db_session, world):
        service = SearchService(db_session)

        results = service.search_documents("slate", world["reader"])
        count = service.count_search_results("slate", world["reader"])

        assert count == len(results) == len(READABLE)


class TestSemanticSearch:
    """Read path: VectorSearchService."""

    @pytest.fixture
    def service(self, db_session) -> VectorSearchService:
        return VectorSearchService(db=db_session, embedder=FakeEmbedder())

    def test_semantic_search_reaches_shared_and_public_documents(self, service, world):
        results = service.vector_search("slate", world["reader"], limit=50)

        assert titles(document for document, _, _ in results) == READABLE

    def test_semantic_results_are_real_documents(self, service, world):
        results = service.vector_search("slate", world["reader"], limit=50)

        # The old implementation rebuilt Documents from selected columns and
        # dropped these fields. Real entities carry them.
        for document, _, _ in results:
            assert document.owner_id is not None
            assert document.is_public is not None

    def test_hybrid_search_reaches_shared_and_public_documents(self, service, world):
        results = service.hybrid_search("slate", world["reader"], limit=50)

        assert titles(document for document, _, _ in results) == READABLE


class TestSharedWithMe:
    """Read path: the shares behind GET /shared-with-me."""

    def live_shares_for(self, db_session, user):
        from app.core.permissions import share_is_live

        return (
            db_session.query(DocumentShare)
            .filter(DocumentShare.shared_with_user_id == user.id, share_is_live())
            .all()
        )

    def test_an_expired_share_is_not_listed(self, db_session, world):
        shares = self.live_shares_for(db_session, world["reader"])

        assert [share.document_id for share in shares] == [world["documents"]["shared"].id]

    def test_expiry_agrees_with_the_access_filter(self, db_session, world):
        """A share that lists here must also make its document accessible."""
        shares = self.live_shares_for(db_session, world["reader"])
        accessible = (
            db_session.query(Document).filter(accessible_documents(world["reader"])).all()
        )

        shared_ids = {share.document_id for share in shares}
        assert shared_ids <= {document.id for document in accessible}


class TestCanAccessDocument:
    """Single-document checks agree with the list."""

    @pytest.fixture
    def permissions(self, db_session):
        from app.core.permissions import PermissionService

        return PermissionService(db_session)

    @pytest.mark.parametrize("name", sorted(READABLE))
    def test_readable_documents_are_accessible(self, permissions, world, name):
        assert permissions.can_access_document(world["reader"], world["documents"][name])

    @pytest.mark.parametrize("name", sorted(UNREADABLE))
    def test_unreadable_documents_are_not(self, permissions, world, name):
        assert not permissions.can_access_document(world["reader"], world["documents"][name])

    def test_write_needs_more_than_public(self, permissions, world):
        assert not permissions.can_access_document(
            world["reader"], world["documents"]["public"], PermissionLevel.WRITE
        )

    def test_a_write_share_grants_write(self, permissions, world):
        assert permissions.can_access_document(
            world["reader"], world["documents"]["shared"], PermissionLevel.WRITE
        )

    def test_superuser_reaches_a_private_document(self, permissions, world):
        assert permissions.can_access_document(
            world["root"], world["documents"]["private"], PermissionLevel.ADMIN
        )


class TestShareExpiryIsAnInstant:
    """
    Expiry is a moment in time, not a wall-clock reading.

    `expires_at` is `timestamptz`, so a share ends at the instant it names and
    the database's own `TimeZone` setting cannot move it. These tests put the
    session in a zone far from UTC, which is what a naive column would silently
    read the value in. See ADR 0008.
    """

    def expiry_is_honoured(self, db_session, world, zone: str, expires_at) -> bool:
        """Set a share's expiry with the session in `zone`; is its document reachable?"""
        from sqlalchemy import text

        db_session.execute(text("SELECT set_config('TimeZone', :zone, false)"), {"zone": zone})

        share = (
            db_session.query(DocumentShare)
            .filter(DocumentShare.document_id == world["documents"]["expired"].id)
            .one()
        )
        share.expires_at = expires_at
        db_session.commit()

        return "expired" in titles(
            db_session.query(Document).filter(accessible_documents(world["reader"])).all()
        )

    def test_a_lapsed_share_stays_lapsed_east_of_utc(self, db_session, world):
        """Kiritimati is UTC+14: read as wall clock, an hour ago reads as 13 hours hence."""
        lapsed = datetime.now(timezone.utc) - timedelta(hours=1)

        assert not self.expiry_is_honoured(db_session, world, "Pacific/Kiritimati", lapsed)

    def test_a_live_share_stays_live_west_of_utc(self, db_session, world):
        """Etc/GMT+11 is UTC-11: read as wall clock, an hour hence reads as 10 hours ago."""
        still_live = datetime.now(timezone.utc) + timedelta(hours=1)

        assert self.expiry_is_honoured(db_session, world, "Etc/GMT+11", still_live)

    def test_an_offset_expiry_keeps_its_instant(self, db_session, world):
        """A caller writing in their own zone gets the instant they wrote."""
        lapsed = datetime.now(timezone(timedelta(hours=-5))) - timedelta(hours=1)

        assert not self.expiry_is_honoured(db_session, world, "UTC", lapsed)
