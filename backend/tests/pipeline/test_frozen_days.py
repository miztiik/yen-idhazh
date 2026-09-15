"""When is a day re-validated, and when is its receipt taken as the answer?"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.base import ChangelogEntry
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_view import DigestView
from idhazh.stages import validate_days
from idhazh.stages.validate_days import (
    _picture_faults,
    _proved,
    _receipts_for,
    _validator_identity,
    day_validations_path,
    stage_validate_days,
)

#
# `validate-days` opened every committed day on every publication and on every
# CI run, parsed it and put it through both contracts a reader holds. A
# published day is frozen, so a second reading can only reach the verdict the
# first one did - what can move is the shape the day is read through. That is a
# bill arriving for an answer the tree already holds, and it grows on a day
# nobody writes any code (Guardrail #12).
#
# Every fixture below is built in the test from the committed contract fixture.
# None of it reads `frontend/public/digest`, whose cost follows what the
# pipeline has piled up (CLAUDE.md section 13).

A_COMMITTED_DAY = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"


def a_published_day(public_root: Path, *, pretty: bool = False) -> Path:
    """One published day on disk, in the layout `published_days` globs for.

    The marks the payload names are written as well, because `_picture_faults`
    compares the two and a day naming a file that is not there is a fault rather
    than the clean day these tests need. `pretty` re-serialises the same payload
    over more bytes, which is what a re-encode does to a closed day.
    """
    payload = json.loads(read_text(A_COMMITTED_DAY))
    year, month, dom = str(payload["date"]).split("-")
    where = public_root / "digest" / year / month / dom
    where.mkdir(parents=True, exist_ok=True)
    for item in payload["items"]:
        visual = item.get("visual")
        if visual and visual.get("data_path"):
            marks = public_root / visual["data_path"]
            marks.parent.mkdir(parents=True, exist_ok=True)
            marks.write_text('{"item_id": "ai-01"}', encoding="utf-8")
    text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
    (where / "digest.json").write_text(text, encoding="utf-8")
    return where / "digest.json"


def days_opened(root: Path, work: Callable[[], int]) -> tuple[int, set[str]]:
    """What `work` returned, and which files under `root` it opened.

    Measured at the file boundary rather than by timing, so the answer is the
    same on a loaded machine. Both doors into a committed day are watched, and
    the set collapses a file reached through both.

    It takes its own `MonkeyPatch` context rather than the fixture, because a
    caller that has patched something else wants that patch to survive this
    call - `monkeypatch.undo()` undoes everything a test set, not just what the
    helper set.
    """
    seen: set[str] = set()

    def note(path: Path) -> None:
        try:
            seen.add(path.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            return

    real_open = Path.open
    real_read = Path.read_bytes

    def spy_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        note(self)
        return real_open(self, *args, **kwargs)

    def spy_read(self: Path) -> bytes:
        note(self)
        return real_read(self)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Path, "open", spy_open)
        patch.setattr(Path, "read_bytes", spy_read)
        return work(), seen


def test_a_day_with_no_receipt_is_validated_and_earns_one(tmp_path: Path) -> None:
    """Case one, and what every tree looks like the first time this runs.

    Nothing is skipped on trust it has not earned, so a tree with no receipts
    costs exactly what this stage cost before the receipt existed. What it
    leaves behind is the record that makes the next run free, and the record is
    a claim about the payload it read: the length and the digest are taken from
    the bytes that passed.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    day = a_published_day(public)
    root = public / "digest"

    code, opened = days_opened(root, lambda: stage_validate_days(root, state_dir=state))

    assert code == 0
    assert "2026/08/21/digest.json" in opened, "a day with no receipt has to be read"
    held = _receipts_for(state, _validator_identity())
    assert set(held) == {"2026-08-21"}
    (receipt,) = held["2026-08-21"]
    assert receipt.payload_bytes == day.stat().st_size
    assert receipt.payload_digest == hashlib.sha256(day.read_bytes()).hexdigest()


def test_an_unchanged_day_under_an_unchanged_validator_is_not_opened(tmp_path: Path) -> None:
    """Case two, and the whole saving, counted rather than timed.

    A published day cannot stop matching a contract on its own, so the second
    reading of it buys nothing. Measured 2026-09-08 on an Intel Core i7-1265U
    over the 18 committed days: 0.45 s median with nothing recorded against
    0.02 s with every receipt current.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"

    first_code, first = days_opened(root, lambda: stage_validate_days(root, state_dir=state))
    second_code, second = days_opened(root, lambda: stage_validate_days(root, state_dir=state))

    assert (first_code, second_code) == (0, 0)
    assert "2026/08/21/digest.json" in first
    assert second == set(), f"a frozen day was opened again: {sorted(second)}"


def test_a_day_whose_payload_moved_is_opened_again(tmp_path: Path) -> None:
    """The receipt is a claim about a payload, never a claim about a date.

    `backfill.yml` re-encodes closed days and then validates with no day named.
    A record keyed on the date alone would wave those days through unread, which
    is the one way this row could weaken the guarantee it is speeding up. The
    recorded length is what `os.stat` answers without opening anything, and a
    re-encode moves it.

    The rewritten day then settles down. The row about the payload that used to
    be there is still in the file - `merge=union` makes the file append-only -
    and it is ignored rather than held against the day, so the next run is free
    again.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert stage_validate_days(root, state_dir=state) == 0

    rewritten = a_published_day(public, pretty=True)
    code, opened = days_opened(root, lambda: stage_validate_days(root, state_dir=state))
    after, quiet = days_opened(root, lambda: stage_validate_days(root, state_dir=state))

    assert (code, after) == (0, 0)
    assert "2026/08/21/digest.json" in opened, "a rewritten day was skipped on a stale receipt"
    assert quiet == set(), "the rewritten day never settled down"
    held = _receipts_for(state, _validator_identity())
    assert len(held["2026-08-21"]) == 2, "the superseded row should still be on file"
    assert _proved(held["2026-08-21"], rewritten.stat().st_size)


def test_a_telemetry_shard_the_contract_refuses_is_named_by_the_gate(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The seventh producer, which read back nowhere until 2026-09-13.

    `frontend/public/telemetry/` is a published mirror a reader's console
    fetches, and it was the one no producer gate opened. A pytest walk over the
    committed shards stood in for it, which section 13 refuses, so the check
    moved to the producer's own gate - where it runs against the tree the run
    wrote rather than against whatever the repository has accumulated.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert stage_validate_days(root, state_dir=state) == 0, "the day itself has to be clean"

    shard = public / "telemetry" / "2026-08.csv"
    shard.parent.mkdir(parents=True)
    shard.write_text("date,not_the_contract\n2026-08-21,1\n", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        assert stage_validate_days(root, state_dir=state) == 1
    assert "frontend/public/telemetry/2026-08.csv" in caplog.text, "name the file"
    assert "header is" in caplog.text, "and say what the contract wanted instead"


def test_a_named_day_is_opened_even_when_it_carries_a_receipt(tmp_path: Path) -> None:
    """Naming a day is how a run says it just wrote that day.

    The publishing job names the date it published, and the receipt on file at
    that moment is about the payload that stood there before this run replaced
    it. So a named day is read, and the receipt is never consulted for it.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert stage_validate_days(root, state_dir=state) == 0

    code, opened = days_opened(
        root, lambda: stage_validate_days(root, ["2026-08-21"], state_dir=state)
    )

    assert code == 0
    assert "2026/08/21/digest.json" in opened


def test_the_validator_identity_moves_when_a_rule_moves() -> None:
    """Case three, first half: what the receipt is keyed on cannot go stale by hand.

    A hand-maintained version is a check that stops checking on the day somebody
    forgets to bump it, and it fails silently - the gate goes on printing a
    pass. So the identity is derived from the two generated schemas and the
    source of the functions that do the checking.

    The replacement here returns exactly what the shipped rule returns, so the
    only thing that moved is the source. That is the point: the receipt is a
    claim about the rules a day was read under, not about the verdict they
    happened to reach.
    """
    before = _validator_identity()
    shipped = _picture_faults

    def reworded(public_root: Path, day: DigestDay) -> list[str]:
        """The shipped rule under another name. Same verdict, different source."""
        return shipped(public_root, day)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(validate_days, "_picture_faults", reworded)
        assert _validator_identity() != before


def test_the_validator_identity_moves_when_a_contract_moves() -> None:
    """Case three, second half: a shape change invalidates every receipt too.

    Section 11 makes a changelog entry mandatory for any change to a persisted
    shape, and that entry lands in the generated schema. Digesting the schema is
    what ties a receipt to the contract the day was read through, so a widened
    field cannot be waved past on a record earned under the old one.
    """
    before = _validator_identity()
    moved = (
        ChangelogEntry(version="2099-01-01", change="a shape change", why="this test's own"),
        *DigestView.__changelog__,
    )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(DigestView, "__changelog__", moved)
        assert _validator_identity() != before


def test_a_moved_validator_reopens_every_day_once(tmp_path: Path) -> None:
    """Case three, and the reason an uninvalidatable receipt is worse than none.

    The receipt is earned, the day goes unread, and then the rules move. Every
    day is opened again - not on a window and not one at a time - and the sweep
    that does it leaves a fresh record, so it happens once rather than on every
    later run.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert stage_validate_days(root, state_dir=state) == 0
    _, quiet = days_opened(root, lambda: stage_validate_days(root, state_dir=state))
    assert quiet == set()

    shipped = _picture_faults

    def reworded(public_root: Path, day: DigestDay) -> list[str]:
        """The shipped rule under another name. Same verdict, different source."""
        return shipped(public_root, day)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(validate_days, "_picture_faults", reworded)
        first, reopened = days_opened(root, lambda: stage_validate_days(root, state_dir=state))
        second, again = days_opened(root, lambda: stage_validate_days(root, state_dir=state))

    assert (first, second) == (0, 0)
    assert "2026/08/21/digest.json" in reopened, "a moved rule left the archive unread"
    assert again == set(), "the sweep after a rule change has to happen once"


def test_two_receipts_that_disagree_about_one_day_leave_it_unproved(tmp_path: Path) -> None:
    """`merge=union` concatenates, so two runs really can leave two rows.

    Where they disagree about the payload the day has no single claim, and a day
    with no single claim is read rather than trusted. This is what the recorded
    digest is for: the lengths can match while the bytes do not.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    day = a_published_day(public)
    root = public / "digest"
    assert stage_validate_days(root, state_dir=state) == 0

    receipts = day_validations_path(state)
    rows = list(csv.DictReader(receipts.read_text(encoding="utf-8").splitlines()))
    disagreeing = {**rows[0], "payload_digest": "b" * 64}
    with receipts.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n").writerow(disagreeing)

    held = _receipts_for(state, _validator_identity())
    assert not _proved(held["2026-08-21"], day.stat().st_size)

    code, opened = days_opened(root, lambda: stage_validate_days(root, state_dir=state))

    assert code == 0
    assert f"2026/08/21/{day.name}" in opened
