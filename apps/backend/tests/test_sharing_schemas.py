"""
What the sharing API accepts as an expiry.

`document_shares.expires_at` is `timestamptz`: it stores an instant. A client
may send one with an offset or without. A naive value is read as UTC here, at
the edge, so nothing further in — the column, `share_is_live()`, the response —
ever handles a timestamp whose zone is a guess. See ADR 0008.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.sharing import DocumentShareCreate, DocumentShareUpdate


UTC_MINUS_5 = timezone(timedelta(hours=-5))


def create(expires_at):
    return DocumentShareCreate(
        shared_with_user_id="00000000-0000-0000-0000-000000000001",
        permission_level="read",
        expires_at=expires_at,
    )


class TestExpiryIsAlwaysAware:
    def test_a_naive_expiry_is_read_as_utc(self):
        share = create(datetime(2026, 6, 1, 12, 0))

        assert share.expires_at == datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    def test_an_offset_expiry_keeps_its_instant(self):
        share = create(datetime(2026, 6, 1, 12, 0, tzinfo=UTC_MINUS_5))

        assert share.expires_at == datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc)

    def test_no_expiry_stays_none(self):
        assert create(None).expires_at is None

    @pytest.mark.parametrize(
        "sent, expected",
        [
            (datetime(2026, 6, 1, 12, 0), datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)),
            (
                datetime(2026, 6, 1, 12, 0, tzinfo=UTC_MINUS_5),
                datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc),
            ),
            (None, None),
        ],
    )
    def test_an_update_reads_an_expiry_the_same_way(self, sent, expected):
        assert DocumentShareUpdate(expires_at=sent).expires_at == expected
