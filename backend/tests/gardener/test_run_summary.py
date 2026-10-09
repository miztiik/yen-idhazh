"""Does each shard write a summary a person reads at a glance, whether it passes or fails?

The summary is Markdown that GitHub shows on the shard's job page. It is built
from the shard's own events, so most of what it says is pinned here on events
built by hand: the one heading, where the record went or why nothing landed,
the downloads against their budget, one row a task, what each word means, and
what the tasks handled without stopping. What `done` and `dry-run` mean is also
read under a compaction pass the runner runs over a tree whose only due work is
an expired year. The rest runs a real shard end to end through
`backend/utilities/gardener_publish.py`, against a bare repository standing in
for origin, with real fixture tasks: one whose service is down and one whose
code is wrong, whose exception quotes a row the way fetched text could.

**Nothing a shard prints may repeat an exception's text** (Guardrail #11): not
a printed line, not a log line with GitHub's commands beside it, and not the
summary. Those tests plant text in an exception and look for it everywhere.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import config
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import Recovery, StopReason
from idhazh.contracts.gardener_events import (
    PeriodsTaken,
    ShardPublished,
    ShardStop,
    TaskFinished,
    TaskOutcome,
)
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.contracts.knobs.gardener import PrunableCollection
from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener import event_log, github_collections, report, run_summary, runner
from idhazh.gardener.outcome import (
    EXIT_INTEGRITY,
    EXIT_OK,
    EXIT_PUSH_REFUSED,
    EXIT_TASK_FAILED,
    MEANS,
    Outcome,
)
from idhazh.site_weight import BYTES_PER_MB
from utilities import gardener_publish

from ._events import the_event
from ._garden import (
    GARDENER_FIXTURES,
    TASK_PACKAGES,
    a_config,
    an_origin,
    git,
    named_task_package,
    on_origin,
    quiet_git,
    task_package,
)
from .tasks.test_yearly_expiry import caught_up, run_by_the_runner, summary_of

WAKE: Final = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID: Final = "2026-09-27-18012345678"
RECORD: Final = "state/raw/gardener/2026/10/08/0b6f8a52-4f0e-4c55-9a7a-3d1b2c9e7f10.parquet"
BREAKS: Final = GARDENER_FIXTURES / "breaks"

#: A day the three-day window of the `breaks` fixtures has aged out.
AGED: Final = "state/old-days/2026/09/19/2026-09-19.txt"

#: What a fetched page might say, planted in an exception's text; and the part of
#: it no line a shard prints may hold.
FETCHED: Final = "Breaking: click https://example.invalid/now"
PLANTED: Final = "example.invalid"

#: What `done` means, as the page shows it under the table: the work is finished
#: for this wake, which says nothing about what data is left.
DONE_LINE: Final = (
    "- *done*: it finished its work for this wake, and the next wake takes what reaches its "
    "line by then"
)

#: What `dry-run` means, as the page shows it under the table: `dry_run` lets a
#: task do the work it found, an expired year included, and `month_deletes_dry_run`
#: holds back only a compaction's old months and raw days.
DRY_RUN_LINE: Final = (
    "- *dry-run*: nothing was changed: it only named the work it found. Set dry\\_run: false "
    "in config/gardener/&lt;task&gt;.json to let it do that work, except that a compaction "
    "keeps the old months and raw days it found until month\\_deletes\\_dry\\_run: false is "
    "set there too"
)


def a_task(task: str, outcome: TaskOutcome, **changed: Any) -> TaskFinished:
    """One task's ending: nothing taken or written unless `changed` says so."""
    said: dict[str, Any] = {
        "task": task,
        "outcome": outcome,
        "dry_run": outcome is TaskOutcome.DRY_RUN,
        "seen": 0,
        "selected": 0,
        "taken": [],
        "written": [],
        "bytes_freed": 0,
        "stopped_because": StopReason.EXHAUSTED,
        "recovered": [],
        "next": report.NEXT[outcome],
        "duration_ms": 3,
    }
    return TaskFinished.model_validate({**said, **changed})


def periods(**listed: list[str]) -> PeriodsTaken:
    """What a compaction did: every list empty unless `listed` names it."""
    said: dict[str, Any] = {
        "days_packed": [],
        "days_retaken": [],
        "months_closed": [],
        "years_packed": [],
        "years_expired": [],
        "months_dropped": [],
        "raw_days_dropped": [],
        "empty_periods": [],
        "lost_days": [],
        "set_aside_paths": [],
        "daily_mark": None,
        "monthly_mark": None,
        "yearly_mark": None,
    }
    return PeriodsTaken.model_validate({**said, **listed})


def a_shard(tasks: Sequence[TaskFinished], **changed: Any) -> ShardPublished:
    """Shard 2's last word: its record landed on the first try, unless `changed` says otherwise."""
    code = changed.get("exit_code", EXIT_OK)
    said: dict[str, Any] = {
        "shard": 2,
        "run_id": RUN_ID,
        "attempt": 1,
        "tasks": [each.task for each in tasks],
        "failed_tasks": [each.task for each in tasks if each.outcome is TaskOutcome.FAILED],
        "landing": ShardLanding.LANDED,
        "push_try": 1,
        "push_tries": 6,
        "record": RECORD,
        "downloaded_bytes": 13_002_342,
        "max_downloaded_mb": 128,
        "exit_code": code,
        "means": MEANS[code],
    }
    return ShardPublished.model_validate({**said, **changed})


def passing() -> list[TaskFinished]:
    """Four tasks of one shard that passed: a dry run, a pass with notes, an idle one, a deferral."""
    return [
        a_task(
            "compact-gardener",
            TaskOutcome.DRY_RUN,
            periods=periods(days_packed=["2026-10-05", "2026-10-06"]),
        ),
        a_task(
            "compact-visual-prunes",
            TaskOutcome.DONE,
            periods=periods(
                days_packed=["2026-09-20", "2026-09-21", "2026-09-22"], months_closed=["2026-08"]
            ),
            recovered=[
                Recovery(note=RecoveryNote.REPACKED_FROM_RAW, subject="2026-09-20"),
                Recovery(note=RecoveryNote.REPACKED_FROM_RAW, subject="2026-09-21"),
            ],
        ),
        a_task("traces", TaskOutcome.NOT_DUE),
        a_task(
            "workflow-runs",
            TaskOutcome.DEFERRED,
            collection=PrunableCollection.WORKFLOW_RUNS,
            taken=["123454", "123455", "123456"],
            stopped_because=StopReason.DEFERRED,
            resume_from="123457",
            fault=GardenerFault.API_UNAVAILABLE,
            next=report.WHY[GardenerFault.API_UNAVAILABLE],
        ),
    ]


def failing() -> list[TaskFinished]:
    """A task a code defect stopped, beside one that did its work."""
    return [
        a_task(
            "defect",
            TaskOutcome.FAILED,
            stopped_because=StopReason.FAILED,
            fault=GardenerFault.RAISED,
            error="KeyError",
            where="idhazh.gardener.runner:302",
            next=report.WHY[GardenerFault.RAISED],
        ),
        a_task("old-days", TaskOutcome.DONE, taken=[AGED], bytes_freed=6),
    ]


def test_a_shard_that_passed_says_where_its_record_went_and_one_row_a_task() -> None:
    """THE PICTURE of a passing shard: one heading, the record, the budget, a row a task, the words."""
    tasks = passing()

    page = run_summary.markdown(a_shard(tasks), tasks)

    assert page == (
        "### No task failed; deferred: `workflow-runs` (exit 0)\n"
        "\n"
        "The shard's changes and its record landed on main on try 1 of up to 6: "
        f"`{RECORD}`.\n"
        "\n"
        "The tasks downloaded 12.4 MB of their 128 MB budget (`max_downloaded_mb`).\n"
        "\n"
        "| Task | How it ended | What it did |\n"
        "| --- | --- | --- |\n"
        "| `compact-gardener` | dry-run | would pack 2 days |\n"
        "| `compact-visual-prunes` | done | packed 3 days, closed 1 month |\n"
        "| `traces` | not-due | nothing |\n"
        "| `workflow-runs` | deferred (api-unavailable) | deleted 3 runs, then stopped while it "
        "worked on 123457 |\n"
        "\n"
        "What the words mean, and what happens next:\n"
        "\n"
        f"{DRY_RUN_LINE}\n"
        f"{DONE_LINE}\n"
        "- *not-due*: nothing has reached its line yet\n"
        "- *api-unavailable*: GitHub's API did not answer, so the next wake asks again\n"
        "\n"
        "Handled without stopping:\n"
        "\n"
        "- `compact-visual-prunes`, 2026-09-20 and 1 more: packed again from its raw files, "
        "because no index named it (repacked-from-raw)\n"
    )


def test_a_shard_a_code_defect_failed_names_the_task_in_its_heading() -> None:
    """THE PICTURE of a failing shard: the defect leads, and its row names the error's place."""
    tasks = failing()
    shard = a_shard(tasks, exit_code=EXIT_TASK_FAILED, downloaded_bytes=0)

    page = run_summary.markdown(shard, tasks)

    assert page == (
        "### A task or the shard itself failed, and a person reads why; a code defect stopped "
        "`defect` (exit 1)\n"
        "\n"
        "The shard's changes and its record landed on main on try 1 of up to 6: "
        f"`{RECORD}`.\n"
        "\n"
        "The tasks downloaded 0.0 MB of their 128 MB budget (`max_downloaded_mb`).\n"
        "\n"
        "| Task | How it ended | What it did |\n"
        "| --- | --- | --- |\n"
        "| `defect` | **failed** (raised) | stopped by `KeyError` at "
        "`idhazh.gardener.runner:302` |\n"
        "| `old-days` | done | deleted 1 file, freed 6 bytes |\n"
        "\n"
        "What the words mean, and what happens next:\n"
        "\n"
        "- *raised*: a code defect stopped it, and the log names the error\n"
        f"{DONE_LINE}\n"
    )


TWO_STALE: Final = ["state/compact/x/index/daily.json", "state/compact/x/index/monthly.json"]


@pytest.mark.parametrize(
    ("changed", "tasks", "said"),
    [
        pytest.param(
            {"landing": ShardLanding.ALREADY_ON_MAIN, "push_try": 2},
            (),
            "A previous try in this job had already landed the shard's changes and its record: "
            f"`{RECORD}`.",
            id="already-on-main",
        ),
        pytest.param(
            {"landing": ShardLanding.STALE, "stale_paths": TWO_STALE[:1]},
            (),
            f"Nothing landed, not even the record (stale): main changed `{TWO_STALE[0]}` after "
            "the commit the shard ran on. The next wake does the work again.",
            id="stale-one-path",
        ),
        pytest.param(
            {"landing": ShardLanding.STALE, "stale_paths": TWO_STALE},
            (),
            f"Nothing landed, not even the record (stale): main changed `{TWO_STALE[0]}` and 1 "
            "more of the shard's files after the commit the shard ran on. The next wake does "
            "the work again.",
            id="stale-two-paths",
        ),
        pytest.param(
            {"landing": ShardLanding.LOST, "push_try": 6},
            (),
            "Nothing landed (lost): all 6 tries failed, and main changed during the last one, so "
            "other writers were landing first. The next wake does the work again.",
            id="lost",
        ),
        pytest.param(
            {"landing": ShardLanding.REFUSED, "push_try": 6, "exit_code": EXIT_PUSH_REFUSED},
            (),
            "Nothing landed (refused): main did not change during try 6 of 6, so no other "
            "writer beat that push, and main refused it. The next wake tries again.",
            id="refused",
        ),
        pytest.param(
            {
                "landing": None,
                "push_try": None,
                "stopped_because": ShardStop.CHECK_REFUSED,
                "exit_code": EXIT_INTEGRITY,
            },
            (),
            f"The tasks ran, but nothing landed, not even the record (`{RECORD}`). The log says "
            "which check refused it.",
            id="a-check-refused-a-written-record",
        ),
        pytest.param(
            {
                "landing": None,
                "push_try": None,
                "record": None,
                "stopped_because": ShardStop.CHECK_REFUSED,
                "exit_code": EXIT_INTEGRITY,
            },
            (a_task("old-days", TaskOutcome.DONE, taken=[AGED]),),
            "The tasks ran, but the shard wrote no record and nothing landed. The log says "
            "which check refused it.",
            id="a-check-refused-after-a-task-ran",
        ),
        pytest.param(
            {
                "landing": None,
                "push_try": None,
                "record": None,
                "downloaded_bytes": None,
                "stopped_because": ShardStop.CHECK_REFUSED,
                "exit_code": EXIT_INTEGRITY,
            },
            (),
            "The shard stopped before its first task, so no task ran and nothing landed. The "
            "log says why.",
            id="a-check-refused-before-any-task",
        ),
        pytest.param(
            {
                "landing": None,
                "push_try": None,
                "record": None,
                "downloaded_bytes": None,
                "stopped_because": ShardStop.LISTING_FAILED,
                "error": "ValueError",
                "where": "idhazh.gardener.period_inputs:134",
                "exit_code": EXIT_TASK_FAILED,
            },
            (),
            "No task ran and nothing landed: the shard could not list the files its tasks work "
            "on (`ValueError` at `idhazh.gardener.period_inputs:134`). The next wake tries again.",
            id="a-listing-that-failed",
        ),
        pytest.param(
            {
                "landing": None,
                "push_try": None,
                "record": None,
                "downloaded_bytes": None,
                "stopped_because": ShardStop.CRASHED,
                "error": "RuntimeError",
                "exit_code": EXIT_TASK_FAILED,
            },
            (),
            "The shard crashed on `RuntimeError`. This summary cannot say what ran or what "
            "landed; the log holds the rest.",
            id="a-crash",
        ),
    ],
)
def test_the_line_under_the_heading_says_where_the_record_went_or_why_nothing_landed(
    changed: dict[str, Any], tasks: tuple[TaskFinished, ...], said: str
) -> None:
    page = run_summary.markdown(a_shard(tasks, **changed), tasks)

    assert page.split("\n\n")[1].removesuffix("\n") == said


def test_downloads_are_read_against_the_budget_and_said_over_it_as_a_defect() -> None:
    over = round(140.2 * BYTES_PER_MB)

    within = run_summary.markdown(a_shard(()), ())
    beyond = run_summary.markdown(
        a_shard((), downloaded_bytes=over, over_budget=True, exit_code=EXIT_TASK_FAILED), ()
    )
    unmeasured = run_summary.markdown(a_shard((), downloaded_bytes=None), ())

    assert "The tasks downloaded 12.4 MB of their 128 MB budget (`max_downloaded_mb`)." in within
    assert (
        "The tasks downloaded 140.2 MB, 12.2 MB over the shard's 128 MB budget "
        "(`max_downloaded_mb`). A task did not fit its work to the budget: a code defect that "
        "repeats at every wake until a person fixes it. The log names the heaviest folders."
    ) in beyond
    assert "downloaded" not in unmeasured, "a shard nothing measured printed a number"


@pytest.mark.parametrize(
    ("task", "did"),
    [
        pytest.param(
            a_task(
                "workflow-artifacts",
                TaskOutcome.DRY_RUN,
                collection=PrunableCollection.WORKFLOW_ARTIFACTS,
                selected=1,
                taken=["987"],
            ),
            "would delete 1 artifact",
            id="a-dry-collection-names-its-members",
        ),
        pytest.param(
            a_task("old-days", TaskOutcome.DONE, taken=["a", "b"], bytes_freed=3 * 1024 // 2),
            "deleted 2 files, freed 1.5 KB",
            id="a-retention-task-deletes-files",
        ),
        pytest.param(
            a_task(
                "compact-seen",
                TaskOutcome.DONE,
                periods=periods(
                    days_packed=["2026-09-20"],
                    lost_days=["2026-09-18"],
                    months_dropped=["2026-05", "2026-06"],
                    raw_days_dropped=["2026-05-31"],
                ),
            ),
            "packed 1 day, recorded 1 lost day; found 2 old months and 1 old raw day past the "
            "keep line",
            id="a-compaction-finds-what-its-keep-line-passed-whether-it-deleted-it-or-not",
        ),
        pytest.param(
            a_task(
                "compact-seen",
                TaskOutcome.DRY_RUN,
                periods=periods(days_packed=["2026-09-20"], months_closed=["2026-08"]),
            ),
            "would pack 1 day, close 1 month",
            id="a-dry-compaction",
        ),
        pytest.param(
            a_task(
                "compact-published",
                TaskOutcome.DONE,
                periods=periods(years_expired=["2026", "2027"], days_packed=["2030-12-30"]),
            ),
            "deleted 2 expired years, packed 1 day",
            id="a-compaction-says-first-the-years-it-deleted-as-expired",
        ),
        pytest.param(
            a_task(
                "compact-published",
                TaskOutcome.DRY_RUN,
                periods=periods(years_expired=["2026"], days_packed=["2030-12-30"]),
            ),
            "would delete 1 expired year, pack 1 day",
            id="a-dry-compaction-says-only-that-it-would-delete-an-expired-year",
        ),
        pytest.param(
            a_task(
                "compact-seen",
                TaskOutcome.FAILED,
                periods=periods(days_packed=["2026-09-20", "2026-09-21"]),
                stopped_because=StopReason.FAILED,
                resume_from="2026-09-22",
                fault=GardenerFault.RAISED,
                next=report.WHY[GardenerFault.RAISED],
            ),
            "packed 2 days, then stopped while it worked on 2026-09-22",
            id="a-compaction-a-refusal-stopped-says-what-it-did-first",
        ),
    ],
)
def test_what_a_task_did_names_the_thing_it_took_and_what_stopped_it(
    task: TaskFinished, did: str
) -> None:
    page = run_summary.markdown(a_shard((task,)), (task,))

    (row,) = [line for line in page.splitlines() if line.startswith(f"| `{task.task}` |")]
    assert row.rsplit(" | ", 1)[1] == f"{did} |"


def test_both_kinds_of_dry_run_share_one_line_tying_each_switch_to_what_it_holds_back() -> None:
    """A dry run and a live compaction whose monthly window only reports end on one word.

    A page says each word once, so its one line has to be true beside both rows:
    `dry_run` lets a task do the work it found, an expired year included, and
    `month_deletes_dry_run` holds back only a compaction's old months and raw days.
    """
    tasks = [
        a_task("compact-published", TaskOutcome.DRY_RUN, periods=periods(years_expired=["2026"])),
        a_task(
            "compact-trial-item-health",
            TaskOutcome.DRY_RUN,
            dry_run=False,
            periods=periods(
                months_dropped=["2026-05", "2026-06"], raw_days_dropped=["2026-06-30"]
            ),
        ),
    ]

    page = run_summary.markdown(a_shard(tasks), tasks)

    assert [line for line in page.splitlines() if line.startswith(("| `", "- *"))] == [
        "| `compact-published` | dry-run | would delete 1 expired year |",
        "| `compact-trial-item-health` | dry-run | found 2 old months and 1 old raw day past "
        "the keep line |",
        DRY_RUN_LINE,
    ]


@pytest.mark.parametrize(
    ("dry_run", "row", "meant"),
    [
        pytest.param(
            False,
            "| `compact-visual-prunes` | done | deleted 1 expired year |",
            DONE_LINE,
            id="live",
        ),
        pytest.param(
            True,
            "| `compact-visual-prunes` | dry-run | would delete 1 expired year |",
            DRY_RUN_LINE,
            id="dry-run",
        ),
    ],
)
def test_beside_an_expired_year_done_claims_no_data_and_dry_run_names_the_switch_that_lets_it_go(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dry_run: bool, row: str, meant: str
) -> None:
    """THE ORACLE: the runner's pass over a tree whose only due work is to expire 2026.

    A live pass deletes the year and ends `done`, and the line under its row
    says the work for this wake is finished, which claims nothing about what
    data is left; it once said "nothing is left". A dry run keeps the year and
    ends `dry-run`, and its line names `dry_run`, the one switch that lets the
    year go, and ties `month_deletes_dry_run` to old months and raw days alone;
    it once offered that switch as another way to let the work happen.
    """
    caught_up(tmp_path)

    with caplog.at_level(logging.INFO):
        outcome = run_by_the_runner(tmp_path, dry_run=dry_run)

    page = summary_of(tmp_path, outcome, the_event(caplog.records, TaskFinished))
    assert [line for line in page.splitlines() if line.startswith(("| `", "- *"))] == [row, meant]


def test_a_sentence_shows_as_written_whatever_markup_it_holds() -> None:
    """A fixed sentence is text, so a `<`, a `|` or a `*` in it cannot become markup."""
    odd = a_task("traces", TaskOutcome.DONE, next="keep <task> | *all* of [it]")

    page = run_summary.markdown(a_shard((odd,)), (odd,))

    assert "- *done*: keep &lt;task&gt; \\| \\*all\\* of \\[it\\]" in page


def every_page() -> list[str]:
    """A summary for every way a shard can end that the tests above build."""
    pages = [
        run_summary.markdown(a_shard(passing()), passing()),
        run_summary.markdown(a_shard(failing(), exit_code=EXIT_TASK_FAILED), failing()),
    ]
    for word in ShardStop:
        thrown = word in (ShardStop.LISTING_FAILED, ShardStop.CRASHED)
        stopped = a_shard(
            (),
            landing=None,
            push_try=None,
            stopped_because=word,
            error="ValueError" if thrown else None,
            exit_code=EXIT_INTEGRITY,
        )
        pages.append(run_summary.markdown(stopped, ()))
    return pages


def test_every_summary_has_one_heading_and_is_ascii() -> None:
    """Sufficiency gate 3: exactly one lede, and only a heading is larger than the table's words."""
    for page in every_page():
        headings = [line for line in page.splitlines() if line.startswith("#")]
        assert len(headings) == 1 and headings[0].startswith("### "), page
        assert page.isascii(), page
        assert page.endswith("\n") and not page.endswith("\n\n"), page


# --- A shard run end to end -------------------------------------------------------


def a_garden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str], *declared: Path
) -> tuple[Path, Path, GardenerSettings]:
    """An origin holding `files`, a clone of it, and these fixture declarations loaded."""
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, files)
    return origin, checkout, config.load_gardener(a_config(checkout, *declared))


def landed(
    names: tuple[str, ...],
    settings: GardenerSettings,
    checkout: Path,
    monkeypatch: pytest.MonkeyPatch,
    summary: Path,
    *,
    period_range: tuple[str, str] | None = None,
) -> tuple[Outcome, list[str]]:
    """One shard run and landed the way a wake does it, with a summary page to write."""
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        names,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        period_range=period_range,
        package=task_package("garden_tasks_breaks", monkeypatch),
        clock=lambda: WAKE,
        say=said.append,
        summary=summary,
    )
    return outcome, said


def on_github(records: Sequence[logging.LogRecord]) -> list[str]:
    """Every line the GitHub handler writes for these records, commands included."""
    github = event_log.GitHubLines()
    return [line for record in records for line in github.format(record).split("\n")]


def test_a_shard_whose_task_failed_lands_its_record_writes_its_summary_and_still_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for a failing shard: the landing line and the failed row, and exit 1."""
    files = {AGED: "aged\n", "state/defect/.keep": ""}
    origin, checkout, settings = a_garden(
        tmp_path, monkeypatch, files, BREAKS / "defect.json", BREAKS / "old-days.json"
    )
    summary = tmp_path / "summary.md"

    with caplog.at_level(logging.INFO):
        outcome, _ = landed(("defect", "old-days"), settings, checkout, monkeypatch, summary)

    assert outcome.exit_code == EXIT_TASK_FAILED
    assert outcome.record is not None
    record = outcome.record.relative_to(checkout).as_posix()
    assert on_origin(origin, record) is not None, "the failing shard's record did not land"
    page = summary.read_text(encoding="ascii")
    assert page.startswith(
        "### A task or the shard itself failed, and a person reads why; a code defect stopped "
        "`defect` (exit 1)\n"
    )
    assert (
        f"The shard's changes and its record landed on main on try 1 of up to 6: `{record}`."
        in page
    )
    (row,) = [line for line in page.splitlines() if line.startswith("| `defect` |")]
    assert row.startswith(
        "| `defect` | **failed** (raised) | stopped by `KeyError` at `idhazh.gardener.runner:"
    )
    assert "| `old-days` | done | deleted 1 file, freed 5 bytes |" in page
    published = the_event(caplog.records, ShardPublished)
    assert (published.landing, published.failed_tasks, published.exit_code) == (
        ShardLanding.LANDED,
        ["defect"],
        EXIT_TASK_FAILED,
    )
    (said_last,) = [held for held in caplog.records if event_log.payload(held) is published]
    assert said_last.levelno == logging.ERROR


def test_a_shard_with_only_deferred_and_done_tasks_writes_its_summary_and_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for a green shard that still has something to say: the deferral is named."""
    files = {AGED: "aged\n", "state/broken/.keep": ""}
    _, checkout, settings = a_garden(
        tmp_path, monkeypatch, files, BREAKS / "broken.json", BREAKS / "old-days.json"
    )
    summary = tmp_path / "summary.md"

    with caplog.at_level(logging.INFO):
        outcome, _ = landed(("broken", "old-days"), settings, checkout, monkeypatch, summary)

    assert outcome.exit_code == EXIT_OK
    page = summary.read_text(encoding="ascii")
    assert page.startswith("### No task failed; deferred: `broken` (exit 0)\n")
    assert "| `broken` | deferred (api-unavailable) | stopped by `ConnectionError` at " in page
    assert "| `old-days` | done | deleted 1 file, freed 5 bytes |" in page
    assert "- *api-unavailable*: GitHub's API did not answer, so the next wake asks again" in page
    published = the_event(caplog.records, ShardPublished)
    assert (published.landing, published.failed_tasks) == (ShardLanding.LANDED, [])
    (said_last,) = [held for held in caplog.records if event_log.payload(held) is published]
    assert said_last.levelno == logging.INFO


def test_no_line_command_or_summary_of_a_failed_task_repeats_its_exception_s_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The defect's exception quotes a row; the shard names its type and place and nothing more."""
    assert PLANTED in (TASK_PACKAGES / "garden_tasks_breaks" / "defect.py").read_text("ascii")
    files = {AGED: "aged\n", "state/defect/.keep": ""}
    _, checkout, settings = a_garden(
        tmp_path, monkeypatch, files, BREAKS / "defect.json", BREAKS / "old-days.json"
    )
    summary = tmp_path / "summary.md"

    with caplog.at_level(logging.INFO):
        _, said = landed(("defect", "old-days"), settings, checkout, monkeypatch, summary)

    lines = on_github(caplog.records)
    assert any(
        line.startswith("::error title=defect::raised (KeyError at idhazh.gardener.runner:")
        for line in lines
    ), lines
    for printed in (*said, *lines, summary.read_text(encoding="ascii")):
        assert PLANTED not in printed and "Breaking" not in printed, printed


def test_a_listing_that_fails_names_its_exception_by_type_and_never_quotes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A range that is not a date fails the listing, and its exception quotes the range.

    Before this, the shard printed that exception's text whole; a message can
    quote fetched text as easily as a person's range.
    """
    _, checkout, settings = a_garden(tmp_path, monkeypatch, {AGED: "aged\n"}, BREAKS / "old-days.json")
    summary = tmp_path / "summary.md"

    with caplog.at_level(logging.INFO):
        outcome, said = landed(
            ("old-days",),
            settings,
            checkout,
            monkeypatch,
            summary,
            period_range=(FETCHED, "2026-09-26"),
        )

    assert outcome.exit_code == EXIT_TASK_FAILED
    (line,) = said
    assert line.startswith(
        "shard 0: the files under its folders could not be listed, so no task ran (ValueError"
    ), line
    page = summary.read_text(encoding="ascii")
    assert (
        "No task ran and nothing landed: the shard could not list the files its tasks work on "
        "(`ValueError`"
    ) in page
    published = the_event(caplog.records, ShardPublished)
    assert (published.stopped_because, published.error) == (ShardStop.LISTING_FAILED, "ValueError")
    for printed in (*said, *on_github(caplog.records), page):
        assert PLANTED not in printed, printed


def test_a_crash_is_said_by_its_type_and_still_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Origin is gone, so the push loop's first fetch fails: the summary says so, and the error goes on.

    Git's own message names the missing folder; the summary and the event name
    the exception's type and nothing it said.
    """
    _, checkout, settings = a_garden(tmp_path, monkeypatch, {AGED: "aged\n"}, BREAKS / "old-days.json")
    git(checkout, "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))
    summary = tmp_path / "summary.md"

    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError, match="nowhere"):
        landed(("old-days",), settings, checkout, monkeypatch, summary)

    page = summary.read_text(encoding="ascii")
    assert page.startswith("### A task or the shard itself failed, and a person reads why (exit 1)\n")
    assert "The shard crashed on `RuntimeError`" in page
    published = the_event(caplog.records, ShardPublished)
    assert (published.stopped_because, published.exit_code, published.error) == (
        ShardStop.CRASHED,
        EXIT_TASK_FAILED,
        "RuntimeError",
    )
    for printed in (page, *on_github(caplog.records)):
        assert "nowhere" not in printed, printed


def test_a_page_that_will_not_take_the_summary_costs_the_summary_and_never_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout, settings = a_garden(tmp_path, monkeypatch, {AGED: "aged\n"}, BREAKS / "old-days.json")
    folder = tmp_path / "not-a-file"
    folder.mkdir()

    outcome, said = landed(("old-days",), settings, checkout, monkeypatch, folder)

    assert outcome.exit_code == EXIT_OK
    assert said[-1].startswith("shard 0: its job summary could not be written ("), said


def test_the_landing_utility_writes_the_summary_where_github_says_and_only_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub names the page in the step's environment; a shard refused before its tasks still writes it."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {"state/old-days/.keep": ""})
    config_dir = a_config(checkout, GARDENER_FIXTURES / "runner" / "old-days.json")
    summary = tmp_path / "step-summary.md"
    monkeypatch.setenv(gardener_publish.STEP_SUMMARY_ENV, str(summary))
    monkeypatch.setenv(gardener_publish.GITHUB_ACTIONS_ENV, "true")

    code = gardener_publish.main(
        [
            "old-days",
            "--run-id",
            RUN_ID,
            "--attempt",
            "1",
            "--repo-root",
            str(checkout),
            "--config",
            str(config_dir),
        ]
    )

    assert code == EXIT_INTEGRITY
    assert summary.read_text(encoding="ascii") == (
        "### A gardener check refused the shard, and a person fixes the cause (exit 2)\n"
        "\n"
        "The shard stopped before its first task, so no task ran and nothing landed. The log "
        "says why.\n"
    )


def test_a_collection_task_s_ending_names_its_collection_so_its_members_have_a_noun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real collection task, with no repository named, fails before its first member."""
    monkeypatch.delenv(github_collections.REPO_ENV, raising=False)
    declared = a_config(tmp_path, GARDENER_FIXTURES / "garden" / "workflow-artifacts.json")

    outcome = runner.run(
        ("workflow-artifacts",),
        settings=config.load_gardener(declared),
        repo_root=tmp_path,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha="0" * 40,
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        package=named_task_package(tmp_path, monkeypatch),
        clock=lambda: WAKE,
        say=lambda _: None,
    )

    (ended,) = outcome.finished_tasks
    assert (ended.task, ended.outcome) == ("workflow-artifacts", TaskOutcome.FAILED)
    assert ended.collection is PrunableCollection.WORKFLOW_ARTIFACTS
