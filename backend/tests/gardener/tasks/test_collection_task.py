"""Does the collection task prune the collection its declaration names, by its window, as it ships?

Driven through the task's own module and the committed declarations, found the
way the runner finds them, against answers GitHub really gave - the transport
is the declared injection point, so nothing here touches the network
(Guardrail #7). What a page becomes and how one member is deleted is tested
beside the adapter; this holds the task to its declaration, and each
collection's walk to the mark on its own record, filed through the ledger door
under `tmp_path`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, Recovery, StopReason
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.contracts.knobs.gardener import CollectionTaskPolicy, PrunableCollection
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import github_collections, registry, report
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass, PruneInterruptedError
from idhazh.gardener.tasks import collection

from .._garden import named_task_modules
from .._records import file_a_record
from ..test_github_collections import (
    ARTIFACT_PAGES,
    OVER_A_THOUSAND,
    RECORDED_LINE,
    REPOSITORY,
    RUNS_BY_DAY,
    RecordedAnswers,
    artifact_page,
    counted_through,
    day_search,
    fixture,
    oldest_first,
    recorded,
)
from ._task import context_for, declared

pytestmark = pytest.mark.contract

#: A wake the recorded pages were read against: the newest member is two days old.
WAKE = date(2026, 9, 18)

#: The day the plan's oracle names. Ninety days back is 2026-07-06, which fell
#: before the repository was created on 2026-08-20, so no run is that old yet.
ORACLE_WAKE: Final = date(2026, 10, 4)

#: The wake whose ninety-day line is 2026-08-22, the oldest day with a run.
OLDEST_RUN_WAKE: Final = date(2026, 11, 20)

#: The day the artifacts were recorded. Thirty days back is 2026-09-05, which
#: falls inside the last page: ten artifacts from 2026-08-22 to 2026-08-24.
ARTIFACT_WAKE: Final = date(2026, 10, 5)

#: A recorded transport for each collection, so the task can be run over every word.
SERVED: Final[dict[PrunableCollection, Callable[[], RecordedAnswers]]] = {
    PrunableCollection.WORKFLOW_ARTIFACTS: lambda: RecordedAnswers(
        fixture(ARTIFACT_PAGES), repository=fixture(REPOSITORY)
    ),
    PrunableCollection.WORKFLOW_RUNS: lambda: RecordedAnswers(repository=fixture(REPOSITORY)),
}


def file_an_artifacts_record(state: Path, *, on: str, **cells: Any) -> CollectionPruneRow:
    """One record holding a row of the artifacts task, its line thirty days before `on`."""
    line = (date.fromisoformat(on) - timedelta(days=30)).isoformat()
    return file_a_record(state, on=on, task="workflow-artifacts", until=line, **cells)


def the_oldest(count: int) -> tuple[str, ...]:
    """The ids of the oldest artifacts GitHub listed, in the order they were created."""
    return tuple(str(raw["id"]) for raw in oldest_first(4)[:count])


def test_both_collections_ship_as_tasks_the_one_module_serves() -> None:
    """Each collection is a declaration named for it, and neither has a module of its own."""
    tasks = declared()
    shipped = named_task_modules()
    for name in ("workflow-artifacts", "workflow-runs"):
        policy = tasks[name]
        assert isinstance(policy, CollectionTaskPolicy)
        assert policy.collection.value == name
        assert (policy.dry_run, policy.owns) == (True, [])
        assert registry.bind(name, policy.kind, shipped).stem == "collection"


@pytest.mark.parametrize("word", list(PrunableCollection), ids=lambda word: word.value)
def test_every_collection_in_the_vocabulary_is_served_by_the_task(
    word: PrunableCollection, tmp_path: Path
) -> None:
    """A word the task served with nothing would report success and do nothing."""
    api = SERVED[word]()

    outcome = collection.run(context_for(word.value, tmp_path, today=WAKE), api=api)

    assert outcome.collection == word.value
    assert api.read_paths, "the task asked GitHub nothing for its collection"


def test_a_first_walk_asks_the_repository_then_reads_the_last_page_and_one_more(
    tmp_path: Path,
) -> None:
    """With no mark in reach, the walk starts after 2026-08-19, the day before the repository.

    It reads page 1 for the count, page 4 and then page 3 to check it by, and
    takes the ten artifacts the thirty-day line holds, oldest first. The walk
    ran out at its line, so the mark moves to the line.
    """
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), repository=fixture(REPOSITORY))

    outcome = collection.run(
        context_for("workflow-artifacts", tmp_path, today=ARTIFACT_WAKE), api=api
    )

    assert api.read_paths == ["", artifact_page(1), artifact_page(4), artifact_page(3)]
    assert api.removed == [], "a dry run called a delete"
    assert (outcome.collection, outcome.dry_run, outcome.until) == (
        "workflow-artifacts",
        True,
        RECORDED_LINE,
    )
    assert outcome.taken == the_oldest(10)
    assert outcome.written == (), "a collection task writes nothing into the repository"
    assert (outcome.seen, outcome.stopped_because, outcome.handled_through) == (
        10,
        StopReason.EXHAUSTED,
        RECORDED_LINE,
    )


def test_a_walk_from_a_mark_passes_over_the_artifacts_its_mark_handled(tmp_path: Path) -> None:
    """A dry pass handled through 2026-08-22, so the next takes only 2026-08-23 and 2026-08-24."""
    file_an_artifacts_record(tmp_path / "state", on="2026-10-04", handled_through="2026-08-22")
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))

    outcome = collection.run(
        context_for("workflow-artifacts", tmp_path, today=ARTIFACT_WAKE), api=api
    )

    assert api.read_paths == [artifact_page(1), artifact_page(4), artifact_page(3)]
    assert outcome.taken == the_oldest(10)[6:]
    assert outcome.handled_through == RECORDED_LINE


def test_a_live_pass_its_ceiling_stops_inside_a_day_of_artifacts_keeps_the_day_before(
    tmp_path: Path,
) -> None:
    """Seven go: six from 2026-08-22 and the first of 2026-08-23, so only 2026-08-22 is whole."""
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), repository=fixture(REPOSITORY))
    context = context_for(
        "workflow-artifacts", tmp_path, today=ARTIFACT_WAKE, dry_run=False, max_deletes_per_run=7
    )

    outcome = collection.run(context, api=api)

    assert api.removed == [f"actions/artifacts/{member}" for member in the_oldest(7)]
    assert (outcome.stopped_because, outcome.resume_from) == (
        StopReason.CEILING,
        the_oldest(8)[-1],
    )
    assert outcome.handled_through == "2026-08-22"


def a_row_of(outcome: Pass, context: TaskContext) -> CollectionPruneRow:
    """The row the runner would file for this pass."""
    assert isinstance(context.policy, CollectionTaskPolicy)
    return report.row(
        outcome,
        task=context.policy.collection.value,
        context=context,
        duration_ms=0,
        work_ended_at=f"{context.today.isoformat()}T00:41:00Z",
        cone_bytes=None,
        downloaded_bytes=None,
    )


def test_a_member_github_will_not_delete_is_on_the_record_and_its_neighbours_are_gone(
    tmp_path: Path,
) -> None:
    """THE ORACLE for a refused delete, on the record: member 2 of 3 answers 422.

    Members 1 and 3 are deleted, and the row holds one `not-deletable` note
    naming member 2, which counted against the ceiling of three.
    """
    one, two, three = the_oldest(3)
    api = RecordedAnswers(
        fixture(ARTIFACT_PAGES),
        repository=fixture(REPOSITORY),
        refusing={f"actions/artifacts/{two}": HTTPStatus.UNPROCESSABLE_ENTITY},
    )
    context = context_for(
        "workflow-artifacts", tmp_path, today=ARTIFACT_WAKE, dry_run=False, max_deletes_per_run=3
    )

    row = a_row_of(collection.run(context, api=api), context)

    assert api.removed == [f"actions/artifacts/{one}", f"actions/artifacts/{three}"]
    assert row.recovered == [Recovery(note=RecoveryNote.NOT_DELETABLE, subject=two)]
    assert (row.deleted, row.selected, row.stopped_because, row.fault) == (
        2,
        4,
        StopReason.CEILING,
        None,
    )


def test_a_page_out_of_order_sends_the_pass_through_every_page_and_keeps_its_mark(
    tmp_path: Path,
) -> None:
    """Page 4's newest artifact moved past midnight, after artifacts page 3 holds.

    The pass still takes the ten artifacts the line holds - the window keeps
    every delete safe - but it cannot say which days are whole, so the next
    pass starts from the same mark.
    """
    file_an_artifacts_record(tmp_path / "state", on="2026-10-04", handled_through="2026-08-21")
    last = recorded(ARTIFACT_PAGES, artifact_page(4))
    moved = next(raw for raw in last["artifacts"] if raw["id"] == 10336260332)
    moved["created_at"] = "2026-09-15T00:05:00Z"
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), answering={artifact_page(4): last})

    outcome = collection.run(
        context_for("workflow-artifacts", tmp_path, today=ARTIFACT_WAKE), api=api
    )

    assert api.read_paths == [artifact_page(page) for page in (1, 4, 3, 2)]
    assert (outcome.seen, outcome.taken) == (313, the_oldest(10))
    assert outcome.handled_through == "2026-08-21"


def test_a_count_that_grows_between_two_reads_keeps_the_mark(tmp_path: Path) -> None:
    """Page 3 is read after one artifact was made, so one may have slipped onto page 4."""
    file_an_artifacts_record(tmp_path / "state", on="2026-10-04", handled_through="2026-08-21")
    second = recorded(ARTIFACT_PAGES, artifact_page(2))["artifacts"]
    third = recorded(ARTIFACT_PAGES, artifact_page(3))["artifacts"]
    pushed = {"total_count": 314, "artifacts": [second[-1], *third[:-1]]}
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), answering={artifact_page(3): pushed})

    outcome = collection.run(
        context_for("workflow-artifacts", tmp_path, today=ARTIFACT_WAKE), api=api
    )

    assert outcome.taken == the_oldest(10), "the pass handled what it read"
    assert outcome.handled_through == "2026-08-21"


# --- The runs, walked a UTC day at a time from the task's own mark ---------------


def test_a_pass_from_a_mark_searches_the_day_after_it_first(tmp_path: Path) -> None:
    """A mark of 2026-06-30 and a ninety-day line on 2026-10-04: 2026-07-01 is asked first.

    Every day after the mark is asked once, up to the line's own day, and the
    mark moves to the line because the walk ran out.
    """
    file_a_record(tmp_path / "state", on="2026-10-03", handled_through="2026-06-30")
    api = RecordedAnswers(fixture(RUNS_BY_DAY))

    outcome = collection.run(context_for("workflow-runs", tmp_path, today=ORACLE_WAKE), api=api)

    assert api.read_paths[0] == (
        "actions/runs?created=2026-07-01T00:00:00Z..2026-07-01T23:59:59Z&per_page=100&page=1"
    )
    assert api.read_paths == [day_search(f"2026-07-0{day}") for day in range(1, 7)]
    assert (outcome.stopped_because, outcome.handled_through) == (
        StopReason.EXHAUSTED,
        "2026-07-06",
    )


def test_with_github_answering_503_the_pass_is_deferred_and_its_mark_does_not_move(
    tmp_path: Path,
) -> None:
    """THE ORACLE for an outage, on the record: the first search after the mark answers 503.

    Nothing inside the wake asks again. The row says `deferred` and why, and it
    carries forward the mark the pass started from, so the next wake searches
    2026-07-01 first again.
    """
    file_a_record(tmp_path / "state", on="2026-10-03", handled_through="2026-06-30")
    api = RecordedAnswers(
        fixture(RUNS_BY_DAY), refusing={day_search("2026-07-01"): HTTPStatus.SERVICE_UNAVAILABLE}
    )
    context = context_for("workflow-runs", tmp_path, today=ORACLE_WAKE)

    with pytest.raises(PruneInterruptedError) as stop:
        collection.run(context, api=api)
    row = a_row_of(stop.value.so_far, context)

    assert api.read_paths == [day_search("2026-07-01")], "nothing inside the wake asked again"
    assert (row.stopped_because, row.fault) == (StopReason.DEFERRED, GardenerFault.API_UNAVAILABLE)
    assert (row.handled_through, row.resume_from, row.deleted) == ("2026-06-30", None, 0)


def test_a_day_counted_over_a_thousand_is_searched_by_the_hour_and_passed_after_the_last(
    tmp_path: Path,
) -> None:
    """The recorded day's count is raised to 1,001, so its 43 runs are read in 24 searches."""
    file_a_record(tmp_path / "state", on="2026-11-19", handled_through="2026-08-21")
    api = RecordedAnswers(fixture(OVER_A_THOUSAND))

    outcome = collection.run(
        context_for("workflow-runs", tmp_path, today=OLDEST_RUN_WAKE), api=api
    )

    assert api.read_paths == [
        day_search("2026-08-22"),
        *(day_search("2026-08-22", hour=hour) for hour in range(24)),
    ]
    assert len(outcome.taken) == 43
    assert outcome.handled_through == "2026-08-22"


def test_a_live_pass_stopped_inside_a_day_searched_by_the_hour_keeps_the_day_before(
    tmp_path: Path,
) -> None:
    """Its ceiling of 5 stops it in the hour from 08:00, so the mark does not pass the day."""
    file_a_record(
        tmp_path / "state", on="2026-11-19", handled_through="2026-08-21", dry_run=False
    )
    api = RecordedAnswers(fixture(OVER_A_THOUSAND))
    context = context_for(
        "workflow-runs", tmp_path, today=OLDEST_RUN_WAKE, dry_run=False, max_deletes_per_run=5
    )

    outcome = collection.run(context, api=api)

    assert len(api.removed) == 5
    assert outcome.stopped_because is StopReason.CEILING
    assert outcome.handled_through == "2026-08-21"
    assert api.read_paths[-1] == day_search("2026-08-22", hour=8), "it read past where it stopped"


def test_a_live_pass_its_ceiling_stops_inside_a_day_leaves_the_mark_on_the_day_before(
    tmp_path: Path,
) -> None:
    """Two of the day's 43 runs go, and the next pass reads 2026-08-22 again for the rest."""
    file_a_record(
        tmp_path / "state", on="2026-11-19", handled_through="2026-08-21", dry_run=False
    )
    api = RecordedAnswers(fixture(RUNS_BY_DAY))
    context = context_for(
        "workflow-runs", tmp_path, today=OLDEST_RUN_WAKE, dry_run=False, max_deletes_per_run=2
    )

    outcome = collection.run(context, api=api)

    first_two = recorded(RUNS_BY_DAY, day_search("2026-08-22"))["workflow_runs"][:2]
    assert api.removed == [f"actions/runs/{run['id']}" for run in first_two]
    assert (outcome.stopped_because, outcome.handled_through) == (
        StopReason.CEILING,
        "2026-08-21",
    )


def test_a_dry_pass_counts_the_rest_of_its_day_so_the_next_wake_moves_on(tmp_path: Path) -> None:
    """It names two, counts the other 41, and its mark moves to the day: no wake repeats it."""
    file_a_record(tmp_path / "state", on="2026-11-19", handled_through="2026-08-21")
    api = RecordedAnswers(fixture(RUNS_BY_DAY))
    context = context_for(
        "workflow-runs", tmp_path, today=OLDEST_RUN_WAKE, max_deletes_per_run=2
    )

    outcome = collection.run(context, api=api)

    assert api.removed == [], "a dry run called a delete"
    assert (len(outcome.taken), outcome.selected) == (2, 43)
    assert (outcome.stopped_because, outcome.handled_through) == (
        StopReason.CEILING,
        "2026-08-22",
    )


def test_a_live_pass_ignores_a_mark_a_dry_run_wrote(tmp_path: Path) -> None:
    """A day a dry run reported is a day nothing deleted, so a live pass starts without it.

    Started from 2026-06-30 it would search 2026-07-01 first. With no live mark
    it asks the repository instead, which was created after the line.
    """
    file_a_record(tmp_path / "state", on="2026-10-03", handled_through="2026-06-30")
    api = RecordedAnswers(fixture(RUNS_BY_DAY), repository=fixture(REPOSITORY))
    context = context_for("workflow-runs", tmp_path, today=ORACLE_WAKE, dry_run=False)

    outcome = collection.run(context, api=api)

    assert api.read_paths == [""], "a live pass walked from a day only a dry run reported"
    assert outcome.handled_through == "2026-07-06"


def test_with_no_mark_and_a_repository_newer_than_the_line_no_page_of_runs_is_read(
    tmp_path: Path,
) -> None:
    """On 2026-10-04 the line, 2026-07-06, is before the repository was created on 2026-08-20."""
    api = RecordedAnswers(repository=fixture(REPOSITORY))

    outcome = collection.run(context_for("workflow-runs", tmp_path, today=ORACLE_WAKE), api=api)

    assert api.read_paths == [""]
    assert (outcome.stopped_because, outcome.seen, outcome.handled_through) == (
        StopReason.EXHAUSTED,
        0,
        "2026-07-06",
    )


def test_with_no_mark_the_first_walk_starts_on_the_oldest_day_the_halving_finds(
    tmp_path: Path,
) -> None:
    """Recorded counts: none on or before 2026-08-21, 43 on or before 2026-08-22."""
    api = RecordedAnswers(fixture(RUNS_BY_DAY), repository=fixture(REPOSITORY))

    outcome = collection.run(
        context_for("workflow-runs", tmp_path, today=OLDEST_RUN_WAKE), api=api
    )

    assert api.read_paths == [
        "",
        counted_through("2026-08-21"),
        counted_through("2026-08-22"),
        day_search("2026-08-22"),
    ]
    assert (len(outcome.taken), outcome.handled_through) == (43, "2026-08-22")
    assert outcome.bytes_freed == 0, "a run's logs have no size the API publishes"


def test_a_run_newer_than_the_line_in_a_recorded_page_is_still_refused(tmp_path: Path) -> None:
    """GitHub answering the search for 2026-08-21 with the runs it made on 2026-08-22.

    Every run is still held to the line before it is taken, so GitHub's own
    filter is never what keeps a delete safe.
    """
    file_a_record(tmp_path / "state", on="2026-11-18", handled_through="2026-08-20")
    newer = recorded(RUNS_BY_DAY, day_search("2026-08-22"))
    api = RecordedAnswers(answering={day_search("2026-08-21"): newer})

    outcome = collection.run(
        context_for("workflow-runs", tmp_path, today=date(2026, 11, 19)), api=api
    )

    assert (outcome.seen, outcome.selected, outcome.taken) == (43, 0, ())
    assert outcome.handled_through == "2026-08-21"


def test_each_wake_starts_the_day_after_the_one_its_last_pass_handled(tmp_path: Path) -> None:
    """The mark goes round the record: one wake's row carries it, and the next wake reads it."""
    state = tmp_path / "state"
    first = collection.run(
        context_for("workflow-runs", tmp_path, today=ORACLE_WAKE),
        api=RecordedAnswers(repository=fixture(REPOSITORY)),
    )
    context = context_for("workflow-runs", tmp_path, today=ORACLE_WAKE)
    row = report.row(
        first,
        task="workflow-runs",
        context=context,
        duration_ms=1,
        work_ended_at="2026-10-04T00:46:31Z",
        cone_bytes=None,
        downloaded_bytes=None,
    )
    ledger.persist(
        state,
        [row],
        ledger=LedgerName.GARDENER,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=row.attempt,
            job=ServerJob.RUN_TASKS,
            shard=row.shard,
            producer="gardener.runner",
            git_sha="b" * 40,
        ),
    )
    api = RecordedAnswers(fixture(RUNS_BY_DAY))

    second = collection.run(
        context_for("workflow-runs", tmp_path, today=date(2026, 10, 5)), api=api
    )

    assert row.handled_through == "2026-07-06"
    assert api.read_paths == [day_search("2026-07-07")]
    assert second.handled_through == "2026-07-07"


def test_without_a_named_repository_the_task_fails_and_says_which_variable_to_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner turns this into the task's `failed` row, and its siblings still run."""
    monkeypatch.delenv(github_collections.REPO_ENV, raising=False)

    with pytest.raises(ValueError, match=github_collections.REPO_ENV):
        collection.run(context_for("workflow-artifacts", tmp_path, today=WAKE))
