"""How one gardener shard's commit came to rest on main.

The publisher, `backend/utilities/gardener_publish.py`, decides which of these
words applies from facts it reads from git: whether `main` holds the shard's
record, whether `main` changed one of the shard's paths after the commit the
shard ran on, whether a push was taken, and whether `main`'s tip moved after the
last try. It never reads a push's error text, because git's words are not a
contract: they change with versions and languages.

It sits with the contracts so that a gardener event can carry the word. It is
not persisted: a record lands inside the commit, so it cannot describe how that
commit landed.
"""

from __future__ import annotations

from enum import StrEnum


class ShardLanding(StrEnum):
    """How one shard's commit came to rest on main."""

    #: A push took the shard's commit.
    LANDED = "landed"
    #: Main already holds the shard's record with the same bytes: an earlier try landed it.
    ALREADY_ON_MAIN = "already-on-main"
    #: Main changed a path the shard writes or deletes after the commit the shard
    #: ran on, so the shard's version is older than main's. Nothing landed.
    STALE = "stale"
    #: Every push failed, and main moved after the last one: other writers are
    #: landing. Nothing landed.
    LOST = "lost"
    #: Every push failed, and main did not move after the last one: main refused
    #: the push. Nothing landed.
    REFUSED = "refused"
