"""Does every day already committed still read, and does the gate that checks them fail loudly?"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.cli import main
from idhazh.contracts.app_config import UiConfig
from idhazh.contracts.digest_day import DigestDay, DigestVerticalRef
from idhazh.stages.validate_days import stage_validate_days

from ._fixtures import (
    RANKING_SIGNAL,
    a_day_missing,
)

pytestmark = pytest.mark.contract


DESK_SHORTFALL = ("considered", "too_old", "below_feed_floor")


def committed_days() -> list[Path]:
    """Published days a test may read. The newest date is still being written to."""
    return sorted((REPO_ROOT / "frontend" / "public" / "digest").glob("*/*/*/digest.json"))[:-1]


def test_the_published_tree_holds_days_to_migrate() -> None:
    """The denominator for the one check below that still opens a real day.

    `a_day_that_validates` reads the newest committed payload, and an empty tree
    would leave it reading nothing while reporting the same pass as a tree it
    read. The read-side migrations beside it are driven from a fixture instead,
    so they no longer need this. `committed_days` already drops the date still
    being written, so a tree holding only that one date reads as empty here.
    """
    assert committed_days(), "frontend/public/digest holds no finished day"


def a_day_that_validates() -> dict[str, Any]:
    """A finished committed day, taken off the real tree rather than written here.

    A day composed by hand drifts from the one the pipeline writes, and the
    guard under test is about the real file. The test below needs a day longer
    than `ui.shell_seed_items`, which is 15, and the date still being written
    has no floor - one run in on 2026-09-06 it held 78 stories against 374.
    `committed_days` is what keeps that date out of reach.
    """
    day: dict[str, Any] = json.loads(read_text(committed_days()[-1]))
    return day


def a_tree_holding(tmp_path: Path, day: dict[str, Any], date: str = "2026-08-30") -> Path:
    """One committed day on disk, in the layout `published_days` globs for."""
    year, month, dom = date.split("-")
    where = tmp_path / "digest" / year / month / dom
    where.mkdir(parents=True)
    (where / "digest.json").write_text(json.dumps(day), encoding="utf-8")
    return tmp_path / "digest"


def test_a_story_past_the_seed_is_the_one_this_gate_exists_for(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The exact hole the migration opened, and the reason a step replaced a build.

    The story is broken at the END of a day longer than `ui.shell_seed_items`,
    so no prerendered document carries it and no build would ever open it. A
    reader's browser fetches it. The gate has to find it there.
    """
    day = a_day_that_validates()
    seed = UiConfig().shell_seed_items
    assert len(day["items"]) > seed, "a day no longer than the seed proves nothing here"
    day["items"][-1]["key_points"] = []

    root = a_tree_holding(tmp_path, day)
    with caplog.at_level(logging.ERROR):
        assert stage_validate_days(root) == 1
    assert "2026-08-30" in caplog.text, "the failing day has to be named"
    assert "digest-view.schema.json" in caplog.text, "which contract refused it"


def test_a_day_that_is_not_json_at_all_is_named_rather_than_thrown(tmp_path: Path) -> None:
    """Degrade, do not fail: one unreadable file must not stop the other days."""
    root = a_tree_holding(tmp_path, a_day_that_validates(), date="2026-08-29")
    broken = root / "2026" / "08" / "30"
    broken.mkdir(parents=True)
    (broken / "digest.json").write_text("{ not json", encoding="utf-8")

    assert stage_validate_days(root) == 1


def test_a_tree_with_no_committed_day_fails_rather_than_passes(tmp_path: Path) -> None:
    """A run over nothing prints the same line as a run over every day."""
    empty = tmp_path / "digest"
    empty.mkdir()
    assert stage_validate_days(empty) == 1


def test_the_gate_defaults_to_the_one_committed_tree(tmp_path: Path) -> None:
    """Unlike `--site-tree`, which has no default because there are two trees.

    There is exactly one committed digest tree, so a default cannot point at the
    wrong one - and a step nobody has to give a path to is a step nobody gets
    wrong in a workflow.

    One day is named, so this costs one day rather than every day the archive
    has piled up (Guardrail #12). The receipts go to a directory this test owns: the
    state root defaults to the committed one, and a test that appended to it
    would leave the repository dirty for whoever ran it.
    """
    newest = committed_days()[-1]
    day = "-".join(newest.parts[-4:-1])

    assert main(["validate-days", "--day", day, "--state-root", str(tmp_path)]) == 0


def test_a_tree_that_is_not_the_committed_one_has_to_name_its_own_receipts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pairing is enforced rather than remembered, because forgetting it lies.

    A receipt records a payload's LENGTH and `_proved` settles a day on that
    length, never on a re-read. So the committed receipts will settle a
    same-length day in any other tree without opening it. Measured 2026-09-13: a
    copy of the newest committed day with `"items"` overwritten by `"itemz"`,
    one byte for one byte, passed against the committed receipt store and
    reported `0 of them opened`; against an empty store the same file was
    refused. `frontend/tests/malformed-day.spec.ts` was making exactly that
    call, so the control arm that exists because a guard which only ever refuses
    proves nothing was passing on a receipt about a different file - and the
    receipts it filed about its scratch trees landed in the tracked
    `state/day-validations.csv`, which `frontend/scripts/build-state.ts`
    fingerprints, so the `publishing` group changed one of its own build's
    inputs while it ran. That was defect 20, and this is what stops the next
    caller repeating it.

    Bounded by construction: one fabricated day under `tmp_path`, no archive
    walk, and nothing here can age out.
    """
    day = a_day_that_validates()
    # The pictures stay on the committed tree, so a copy that still named them
    # would fail on the missing files and say nothing about the receipts.
    for item in day["items"]:
        item.pop("visual", None)
    copy = a_tree_holding(tmp_path / "copy", day)

    with pytest.raises(SystemExit) as refused:
        main(["validate-days", "--digest-root", str(copy)])

    assert refused.value.code == 2, "a forgotten pair is a wrong answer, not a warning"
    said = capsys.readouterr().err
    assert "--state-root" in said, "the refusal has to name the flag that settles it"
    assert "--digest-root" in said, "and the flag that caused it"

    store = tmp_path / "receipts"
    assert main(["validate-days", "--digest-root", str(copy), "--state-root", str(store)]) == 0
    assert (store / "day-validations.csv").is_file(), "the receipt belongs beside the tree it is about"


def test_a_committed_day_reads_an_absent_ranking_field_as_unknown() -> None:
    """The read-side migration (`CLAUDE.md` section 11).

    A day written before the five fields existed omits them, and every one must
    come back as `None`. `0` for `carried_by` would claim no feed carried the
    story, `false` for `on_front_page` would claim a vote that was never
    counted, and `0.0` for `rank_score` would put the story bottom of its desk -
    three different false claims dressed as a default.
    """
    text, stripped = a_day_missing(RANKING_SIGNAL)
    assert stripped, "the fixture carries no story, so removing the fields proved nothing"

    day = DigestDay.from_json(text)
    assert len(day.items) == stripped
    for item in day.items:
        for name in RANKING_SIGNAL:
            assert getattr(item, name) is None, f"{item.item_id}: {name} invented"


def test_every_committed_day_revalidates_with_no_shortfall_counts() -> None:
    """The read-side migration for the desk shortfall (`CLAUDE.md` section 11).

    Every day published before 2026-09-02 carries a desk as three keys - id,
    name and count - so the three counts appended later have to be absent and
    have to come back as `None`. A `0` for `considered` would say the sources
    offered that desk nothing, which is the opposite of what a day with 216
    stories on it means.
    """
    text, stripped = a_day_missing(DESK_SHORTFALL, where="verticals")
    assert stripped, "the fixture carries no desk, so removing the counts proved nothing"

    day = DigestDay.from_json(text)
    assert len(day.verticals) == stripped
    for desk in day.verticals:
        for name in DESK_SHORTFALL:
            assert getattr(desk, name) is None, f"{desk.id}: {name} invented"


def test_a_desk_carries_every_shortfall_count_or_none_of_them() -> None:
    """Three fields written by one step, so a desk holding two is a writer bug.

    It also keeps the read side simple: a page asks whether the desk knows why
    it is thin, not whether it knows two thirds of it.
    """
    with pytest.raises(ValueError, match="every shortfall field or none"):
        DigestVerticalRef(id="ai", display_name="AI", count=3, considered=40)

    whole = DigestVerticalRef(
        id="ai", display_name="AI", count=3, considered=40, too_old=31, below_feed_floor=False
    )
    assert whole.considered == 40


def test_a_desk_cannot_drop_more_stories_than_it_considered() -> None:
    """The same bound `VerticalPlan` carries, kept on the field a reader sees.

    The sentence names both numbers, so a payload where the second exceeds the
    first prints a page saying more stories were too old than were ever offered.
    """
    with pytest.raises(ValueError, match="more stories than it considered"):
        DigestVerticalRef(
            id="ai", display_name="AI", count=1, considered=3, too_old=4, below_feed_floor=False
        )
