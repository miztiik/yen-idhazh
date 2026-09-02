"""Which addresses a run may ask, decided from committed events and nothing else.

Four different facts get four different answers here, and keeping them apart is
the whole design. **Permission** is what a site's own `robots.txt` said.
**Rest** is a circuit breaker that lifts itself. **Retirement** is the one
permanent answer, and only a server reporting `410 Gone` on five distinct runs
earns it. **Eligibility** is what the feed floor counts. A single credibility
score across the four was refused: they have different units and different
remedies, and one number cannot say which of them fired
(`docs/architecture/sources/health.md`).

Everything here is a fold over rows an earlier run committed. Nothing opens a
socket, nothing reads a clock and nothing edits `config/sources.json` - a run
may write evidence about curation and may never write curation.

**A row that cannot say which address it asked is invisible to this module.**
`endpoint_key` was appended to the health row on 2026-09-02 and deliberately
left empty on every row written before it, because the configured URL may have
moved since (Row #1 decision 6). Filing a retirement against a guessed address
is the one mistake here that cannot be undone by a later run, so an unkeyed row
carries no evidence about any endpoint. Rest is unaffected: it is decided per
feed, by `discover.resting`, over the same rows.

`discover.settled` and `discover.streak` are the neighbours of this fold and it
runs them rather than restating them - the console and the run have to agree
about what a feed did, and two reductions over one file is how they stop
agreeing.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from idhazh.contracts.feed_health import FeedHealthRow, RobotsOutcome, derive_endpoint_key
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.sources import FeedDef
from idhazh.discover import live, settled

#: The one status that says an address is not coming back. A 403, a 404, a
#: paywall, a transient failure and an empty feed all say something about today.
GONE: Final = 410

#: Permission that stops us asking. A refusal is the publisher's stated policy
#: and an unreachable `robots.txt` is our own failed read; neither one lets a
#: request go out, so neither address belongs in a count of what we may ask.
#: Both are reversible - the next run establishes permission again.
UNPERMITTED: Final[frozenset[RobotsOutcome]] = frozenset(
    {RobotsOutcome.DENIED, RobotsOutcome.UNREACHABLE}
)


@dataclass(frozen=True, slots=True)
class EndpointRecord:
    """What the committed events say about one address."""

    endpoint_key: str
    gone_runs: tuple[str, ...]
    """Distinct runs that read `410` since this address last delivered, oldest first."""
    permission: RobotsOutcome | None
    """The newest robots answer on record. `None` when no run has recorded one."""

    def retires(self, *, after_runs: int) -> bool:
        """Has the server said `gone` on enough distinct runs to stop asking?"""
        return len(self.gone_runs) >= after_runs

    @property
    def permitted(self) -> bool:
        """May we ask this address at all?

        An address nobody has recorded permission for is permitted. Absent is
        not denied: every row written before 2026-09-02 carries an empty cell,
        and reading those as refusals would take every desk under its floor on
        the day this landed.
        """
        return self.permission not in UNPERMITTED


def endpoint_records(history: Iterable[FeedHealthRow]) -> dict[str, EndpointRecord]:
    """Fold the committed health rows into one record per address.

    `history` is oldest run first, which is what `ledger.load_health` returns.
    It is settled first, so two accounts of one run count once: without that a
    single execution written down twice would supply two of the five distinct
    runs a retirement needs.

    Three kinds of evidence and three effects, and they are not the same three
    the availability streak uses:

    - **a read that carried entries** ends the `410` run: the address answers,
      so whatever it said before is history.
    - **a `410`** adds that run, once however many times the run wrote it down.
    - **everything else** leaves the count where it is. That includes an empty
      success, which adds an availability strike and says nothing about whether
      the address is permanently gone.

    Permission is separate and simply the newest answer on record. A rest and a
    plain failure carry no robots answer, so neither disturbs it.
    """
    gone: dict[str, list[str]] = {}
    permission: dict[str, RobotsOutcome | None] = {}
    for row in settled(history):
        key = row.endpoint_key
        if key is None:
            continue
        runs = gone.setdefault(key, [])
        permission.setdefault(key, None)
        if row.answered:
            runs.clear()
        elif row.status == GONE and row.run_id not in runs:
            runs.append(row.run_id)
        if row.robots_outcome is not None:
            permission[key] = row.robots_outcome
    return {
        key: EndpointRecord(
            endpoint_key=key, gone_runs=tuple(runs), permission=permission[key]
        )
        for key, runs in gone.items()
    }


def retirements(
    feeds: Sequence[FeedDef],
    *,
    records: Mapping[str, EndpointRecord],
    already: Collection[str],
    after_runs: int,
    date: str,
    run_id: str,
) -> list[FeedRetirementRow]:
    """The addresses this run is the first to find permanently gone.

    One row per address, ever. `already` is what the ledger holds, so a run that
    reads the same evidence tomorrow files nothing new - and two curated feeds
    pointing at one URL file one row between them rather than two.

    The row names the feed that was configured to ask, because that is who will
    stop asking. It is keyed on the address, so renaming that feed cannot revive
    a dead address and editing its URL produces a different key with a clean
    record.
    """
    filed: list[FeedRetirementRow] = []
    seen = set(already)
    for feed in feeds:
        key = derive_endpoint_key(feed.url)
        if key in seen:
            continue
        record = records.get(key)
        if record is None or not record.retires(after_runs=after_runs):
            continue
        seen.add(key)
        filed.append(
            FeedRetirementRow(
                version=FeedRetirementRow.schema_version(),
                feed_id=feed.id,
                endpoint_key=key,
                retired_on=date,
                decided_by_run=run_id,
                cause=RetirementCause.HTTP_410,
                evidence_run_ids=record.gone_runs,
            )
        )
    return filed


def retired(feeds: Iterable[FeedDef], keys: Collection[str]) -> frozenset[str]:
    """The feed ids whose configured address is on the retirement ledger.

    The ledger keys on the address and the fetch loop iterates feeds, so one of
    the two has to be translated. It is done here, once, against today's config:
    a feed whose URL has been edited since the retirement resolves to a
    different key and is asked again, which is exactly what editing it means.
    """
    return frozenset(feed.id for feed in feeds if derive_endpoint_key(feed.url) in keys)


def eligible(
    feeds: Sequence[FeedDef],
    vertical_id: str,
    *,
    retired_keys: Collection[str],
    records: Mapping[str, EndpointRecord],
) -> list[FeedDef]:
    """This desk's feeds whose address we may lawfully ask.

    The feed floor asks how many independent sources a desk has, so it counts
    the addresses we are allowed to ask rather than the ones that answered
    today. Four things take a feed out of the count and each is a different
    fact:

    - **a curated tombstone**, which is a person's decision and is enforced by
      `discover.live` rather than by a filter here.
    - **a retired endpoint**, which is a server saying the address is gone.
    - **a robots refusal**, which is a publisher's stated policy.
    - **permission we could not establish**, which fails closed, so the address
      is never asked.

    A resting or failing endpoint stays in the count, and that is the load-
    bearing half. Dropping it would let one bad afternoon take a desk under its
    floor and dark - and the desk's problem then is that today went badly, not
    that it is under-sourced. The floor measures lawful source diversity.
    """
    kept: list[FeedDef] = []
    for feed in live(list(feeds), vertical_id):
        key = derive_endpoint_key(feed.url)
        if key in retired_keys:
            continue
        record = records.get(key)
        if record is not None and not record.permitted:
            continue
        kept.append(feed)
    return kept
