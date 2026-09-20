"""
Access rules are written in one module, and nowhere else.

Sharing shipped and search was never updated for it, so for two phases "which
documents can this user see" had two different answers — and share expiry had
three. This test is what keeps it at one: a new read path that decides ownership
or expiry for itself fails here, at the moment it is written. See ADR 0004.

A line that touches these columns for some reason other than access control opts
out with a trailing `# not an access check: <why>`.
"""
import re
from pathlib import Path
from typing import Iterator, Tuple

import pytest

APP = Path(__file__).resolve().parent.parent / "app"

# Where the rule lives, and is therefore allowed to say this.
HOME = APP / "core" / "permissions.py"

OPT_OUT = re.compile(r"#\s*not an access check:")

# Each rule that may only be written in `app/core/permissions.py`, and what to
# call instead when this test catches a second copy of it.
RULES = {
    "ownership": (
        re.compile(r"Document\.owner_id\s*=="),
        "Filter through accessible_documents() instead",
    ),
    "share expiry": (
        re.compile(r"DocumentShare\.expires_at|share\.expires_at\s*[<>]"),
        "Filter through share_is_live() instead",
    ),
}


def offences(pattern: re.Pattern) -> Iterator[Tuple[Path, int, str]]:
    """Every line under app/ matching a rule's pattern, with its opt-outs honoured."""
    for path in sorted(APP.rglob("*.py")):
        if path == HOME:
            continue

        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line) and not OPT_OUT.search(line):
                yield path, number, line.strip()


@pytest.mark.parametrize("rule", sorted(RULES))
def test_the_rule_is_written_only_where_it_lives(rule):
    pattern, instead = RULES[rule]
    found = list(offences(pattern))

    assert not found, f"{instead}:\n" + "\n".join(
        f"  {path.relative_to(APP.parent)}:{number}: {line}" for path, number, line in found
    )
