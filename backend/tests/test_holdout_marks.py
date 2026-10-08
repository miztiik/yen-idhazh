"""Do the marks a harvest saves read back once a pair, each with the mark it was given last?

The harvest in `backend/utilities/sample_sheet.py` files one labelling's marks
through the ledger door under the day they were made, and
`idhazh.similarity.holdout.marked_pairs` reads them over the reach
`similarity.holdout_reach_days` sets. A pair a person marks again is read once,
with its newest mark, so a corrected mark replaces the one it corrects rather
than counting beside it.

Every case writes its own state root under `tmp_path`, and nothing reads the
committed marks or the published archive (CLAUDE.md section 13).
"""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob, derive_url_key
from idhazh.contracts.ledger_name import LedgerName
from idhazh.similarity import holdout
from utilities import sample_sheet
from utilities.sample_sheet import Article, Pair, band_of, harvest

pytestmark = pytest.mark.contract

HOLDOUT: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS

#: The day a person first labels the sheet, and a later day they correct a mark.
FIRST_DAY: Final = "2026-09-19"
SECOND_DAY: Final = "2026-10-08"

A_LABELLER: Final = "a-labeller"

#: The run and the commit a person's harvest names. Any run id and full SHA will do.
A_RUN: Final = "2026-09-19-1"
A_LATER_RUN: Final = "2026-10-08-1"
A_COMMIT: Final = "0735031c2a9e4b8f1d6c3a5e7b9d0f2a4c6e8b1d"

LINE: Final = 0.94
CORRIDOR: Final = 0.02


def a_pair(key: str, *, score: float = 0.95) -> Pair:
    """One drawn pair of two different articles, published on the first day."""
    left, right = (
        Article(
            url=f"https://{side}.test/{key}",
            title=f"{side} story {key}",
            summary="",
            source=side,
            date="2026-09-17",
        )
        for side in ("left", "right")
    )
    return Pair(
        date="2026-09-17",
        pair_key=key,
        score=score,
        cosine=score,
        headline=False,
        band=band_of(score, LINE, corridor=CORRIDOR),
        left=left,
        right=right,
    )


def a_batch(sheet: Path, name: str, labels: dict[str, bool]) -> str:
    """One labels batch beside the sheet, as a labeller writes it."""
    sheet.mkdir(parents=True, exist_ok=True)
    (sheet / name).write_text(json.dumps({"by_pair_key": labels}), encoding="utf-8")
    return name


def harvested(
    sheet: Path, state: Path, pairs: list[Pair], batch: str, *, on: str, run_id: str
) -> int:
    """One harvest of one batch, filed on `on` under the run named."""
    return harvest(
        sheet,
        state,
        pairs,
        labeller=A_LABELLER,
        labelled_on=on,
        batches=[batch],
        run_id=run_id,
        commit_sha=A_COMMIT,
    )


def committed_reach() -> int:
    """The committed `similarity.holdout_reach_days`, read inside a test."""
    return config.load(CONFIG_DIR).app.similarity.holdout_reach_days


def test_the_oracle_a_pair_marked_again_reads_once_with_its_second_mark(tmp_path: Path) -> None:
    """Two harvests on two days, the second correcting one pair, read back as one row a pair.

    Before the marks moved onto the door a harvest rewrote one file whole, so the
    second harvest here would have left only the pair it named. Read through the
    door, the first pair carries the second day's mark and the second pair keeps
    the first day's.
    """
    sheet, state = tmp_path / "sheet", tmp_path / "state"
    corrected, kept = a_pair("corrected"), a_pair("kept")
    pairs = [corrected, kept]
    first = a_batch(sheet, "labels-batch-01.json", {"corrected": True, "kept": True})
    second = a_batch(sheet, "labels-batch-02.json", {"corrected": False})

    assert harvested(sheet, state, pairs, first, on=FIRST_DAY, run_id=A_RUN) == 2
    assert harvested(sheet, state, pairs, second, on=SECOND_DAY, run_id=A_LATER_RUN) == 1

    marks = holdout.marked_pairs(state, today=SECOND_DAY, reach_days=committed_reach())

    assert sorted((mark.left_url, mark.same_story, mark.marked_on) for mark in marks) == [
        (corrected.left.url, False, SECOND_DAY),
        (kept.left.url, True, FIRST_DAY),
    ]


def test_a_harvest_files_one_raw_file_under_the_person_who_ran_it(tmp_path: Path) -> None:
    """The marks are one door file under the day they were made, written by `operator`.

    No workflow job ran the harvest, so its job is `operator`, at attempt 1 and
    shard 0. The run and the commit are the ones the person named, so the file
    points back at the code that saved the marks.
    """
    sheet, state = tmp_path / "sheet", tmp_path / "state"
    batch = a_batch(sheet, "labels-batch-01.json", {"a-pair": False})

    assert harvested(sheet, state, [a_pair("a-pair")], batch, on=FIRST_DAY, run_id=A_RUN) == 1

    assert ledger.raw_days(state, HOLDOUT) == [FIRST_DAY]
    (raw_file,) = ledger.list_raw_files(state, HOLDOUT, days=[FIRST_DAY])
    identity = raw_file.envelope.identity
    assert (identity.job, identity.attempt, identity.shard) == (ServerJob.OPERATOR, 1, 0)
    assert (identity.run_id, identity.git_sha, identity.producer) == (
        A_RUN,
        A_COMMIT,
        sample_sheet.PRODUCER,
    )
    assert raw_file.path.parent == ledger.raw_root(state, HOLDOUT) / "2026" / "09" / "19"


def test_a_harvest_that_found_no_label_files_nothing(tmp_path: Path) -> None:
    """A harvest adds marks, so one with none to add leaves no file, empty or not."""
    sheet, state = tmp_path / "sheet", tmp_path / "state"
    batch = a_batch(sheet, "labels-batch-01.json", {})

    assert harvested(sheet, state, [a_pair("a-pair")], batch, on=FIRST_DAY, run_id=A_RUN) == 0
    assert not ledger.raw_root(state, HOLDOUT).exists()


def test_a_mark_filed_before_the_reach_is_not_read(tmp_path: Path) -> None:
    """The read opens the reach and nothing older, so its cost never grows with the ledger.

    Both ends are named: a mark filed exactly `reach` days back still counts,
    and one a day older does not, until somebody marks the pair again.
    """
    sheet, state = tmp_path / "sheet", tmp_path / "state"
    batch = a_batch(sheet, "labels-batch-01.json", {"a-pair": True})
    harvested(sheet, state, [a_pair("a-pair")], batch, on=FIRST_DAY, run_id=A_RUN)
    reach = 30
    edge = (date.fromisoformat(FIRST_DAY) + timedelta(days=reach)).isoformat()
    past = (date.fromisoformat(FIRST_DAY) + timedelta(days=reach + 1)).isoformat()

    assert len(holdout.marked_pairs(state, today=edge, reach_days=reach)) == 1
    assert holdout.marked_pairs(state, today=past, reach_days=reach) == []


@pytest.mark.parametrize(
    ("later", "kept", "wins"),
    [
        ("2026-10-08", "2026-09-19", True),
        ("2026-09-19", "2026-09-19", True),
        ("2026-09-18", "2026-09-19", False),
    ],
)
def test_the_newer_mark_wins_and_a_same_day_mark_filed_later_wins_too(
    later: str, kept: str, wins: bool
) -> None:
    """The door's preference for the marks' key: a later `marked_on`, or the same day filed later."""
    rule = ledger.preference_for(ledger.door_key(HOLDOUT))

    assert ledger.door_key(HOLDOUT) == ("left_url", "right_url")
    assert rule is ledger.HOLDOUT_PAIR_RULE
    assert rule({"marked_on": later}, {"marked_on": kept}) is wins


def a_drawn_tree(root: Path) -> tuple[Path, Path, Path]:
    """One published day of two articles, one draw naming them as a pair, and a labelled sheet."""
    draws, digest, sheet = root / "draws", root / "digest", root / "sheet"
    urls = ("https://left.test/bridge", "https://right.test/bridge")
    day = digest / "2026" / "09" / "17" / "digest.json"
    day.parent.mkdir(parents=True)
    day.write_text(
        json.dumps(
            {
                "date": "2026-09-17",
                "items": [
                    {"source_url": url, "title": f"Bridge {n}", "summary": "", "source_name": "x"}
                    for n, url in enumerate(urls)
                ],
            }
        ),
        encoding="utf-8",
    )
    draws.mkdir()
    with (draws / "draw.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "pair_key", "left_url_key", "right_url_key", "composite_score"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2026-09-17",
                "pair_key": "a-pair",
                "left_url_key": derive_url_key(urls[0]),
                "right_url_key": derive_url_key(urls[1]),
                "composite_score": "0.95",
            }
        )
    a_batch(sheet, "labels-batch-01.json", {"a-pair": False})
    return draws, digest, sheet


def a_typed_harvest(root: Path, state: Path, *extra: str) -> list[str]:
    """The harvest as a person types it, against this test's own tree."""
    draws, digest, sheet = a_drawn_tree(root)
    return [
        "--draw-root", str(draws),
        "--digest-root", str(digest),
        "--out", str(sheet),
        "--line", str(LINE),
        "--day", "2026-09-17",
        "--draw", "draw.csv",
        "--labels", "labels-batch-01.json",
        "--harvest",
        "--state-root", str(state),
        "--labeller", A_LABELLER,
        "--labelled-on", FIRST_DAY,
        *extra,
    ]  # fmt: skip


def test_the_typed_harvest_saves_the_marks_through_the_door(tmp_path: Path) -> None:
    """Through the command, the labelled pair reaches the ledger the panel reads."""
    state = tmp_path / "state"

    typed = a_typed_harvest(tmp_path, state, "--run-id", A_RUN, "--commit", A_COMMIT)
    assert sample_sheet.main(typed) == 0

    (mark,) = holdout.marked_pairs(state, today=FIRST_DAY, reach_days=committed_reach())
    assert (mark.left_url, mark.same_story, mark.marked_on) == (
        "https://left.test/bridge",
        False,
        FIRST_DAY,
    )


@pytest.mark.parametrize(
    ("given", "refusal"),
    [
        (("--commit", A_COMMIT), "--harvest needs --run-id"),
        (("--run-id", A_RUN), "--harvest needs --commit"),
        (("--run-id", "the-first-one", "--commit", A_COMMIT), "is not a run id"),
        (("--run-id", A_RUN, "--commit", "HEAD"), "is not a full commit id"),
    ],
)
def test_the_typed_harvest_refuses_a_file_that_could_not_name_its_writer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], given: tuple[str, ...], refusal: str
) -> None:
    """A door file names the run and the commit that wrote it, so a harvest needs both."""
    state = tmp_path / "state"

    with pytest.raises(SystemExit) as stopped:
        sample_sheet.main(a_typed_harvest(tmp_path, state, *given))

    assert stopped.value.code == 2
    assert refusal in capsys.readouterr().err
    assert not ledger.raw_root(state, HOLDOUT).exists()


def test_the_old_harvest_spelling_that_named_a_csv_file_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--harvest` once took the CSV file to rewrite; handed one now, it stops rather than guessing."""
    state = tmp_path / "state"
    typed = a_typed_harvest(tmp_path, state, "--run-id", A_RUN, "--commit", A_COMMIT)
    typed.insert(typed.index("--harvest") + 1, "state/content-similarity-judge/holdout-pairs.csv")

    with pytest.raises(SystemExit) as stopped:
        sample_sheet.main(typed)

    assert stopped.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    assert not ledger.raw_root(state, HOLDOUT).exists()
