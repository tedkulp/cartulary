# A share expires at an instant

`document_shares.expires_at` is `timestamptz`. `share_is_live()` is
`expires_at IS NULL OR expires_at > now()`, and the sharing API reads an expiry
arriving without an offset as UTC.

Before this the column was `timestamp without time zone`. Every writer meant
UTC, but nothing said so, so the comparison had to say it instead:
`expires_at > timezone('UTC', now())` converted the database clock down to a
naive UTC value to match. That was correct, and it was correct because a
convention was held in three places at once — the writers, the column and the
comparison — rather than because of the schema. ADR 0004 named this and left it
alone; this is the fix it deferred (#31).

The failure it was one deployment away from: `timestamp` has no zone, so
Postgres reads a value written into it in the server's `TimeZone` setting. On a
server set to anything but UTC, a share written from a client an hour in the
future was stored as a wall-clock reading hours away from the instant meant, and
`share_is_live()` answered the opposite of the truth in both directions — a
lapsed share still granting access, a live one already refused. Access control
that depends on an environment variable nobody set deliberately is the worst
shape a rule can have.

Two other shapes were considered. Storing UTC epoch integers makes the instant
unambiguous and makes every query and every migration read it back by hand.
Validating at the edge alone — attaching UTC to naive input and leaving the
column naive — fixes what the API writes and leaves the schema still not saying
what it holds, so the next writer starts the convention over. The column is
where the meaning belongs; the edge validator is there so the column is never
handed a timestamp whose zone is a guess.

The migration's `USING expires_at AT TIME ZONE 'UTC'` is the part that matters.
Without it, the same `TimeZone` setting decides how existing rows are reinterpreted,
which would shift every stored expiry on exactly the deployments this change is for.

## Scope

This stops at `expires_at`. Every other `DateTime` column in the schema —
`documents.created_at` and `updated_at`, the tag, user, activity-log and import
timestamps — has the same shape, and none of them decides access: a `created_at`
read in the wrong zone shows a date a few hours off, it does not grant or refuse
a document. They are worth converting and they are not worth converting in the
change that fixes an access rule, where a wider migration is a wider thing to be
wrong about.

The convention the rest should follow when they are converted, and which new
timestamp columns follow now: **a column that stores a moment in time is
`DateTime(timezone=True)`, and any naive value is given UTC at the API boundary,
not further in.**

## Consequences

- `share_is_live()` compares two instants and no longer converts anything, so it
  reads as the rule it is. The database clock still decides, so app containers
  still cannot disagree about when a share ends.
- Expiry no longer depends on the Postgres server's `TimeZone`.
  `tests/test_document_access.py::TestShareExpiryIsAnInstant` sets the session to
  UTC+14 and UTC-11 and asserts the answer does not move; both cases failed
  before this change.
- `DocumentShareResponse.expires_at` now serialises with an offset. Clients
  parsing it with `new Date(...)` already treated it as UTC by guessing right;
  they now get told. `created_at` in the same response is still naive, and will
  stay that way until the columns above are converted.
- The schema is now inconsistent on purpose: one `timestamptz` column among many
  naive ones. The comment on the column and this ADR are what stop that reading
  as an oversight.
