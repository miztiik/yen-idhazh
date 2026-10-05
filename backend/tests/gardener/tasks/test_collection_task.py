"""Does the collection task prune the collection its declaration names, by its window, as it ships?

Driven through the task's own module and the committed declarations, found the
way the runner finds them, against answers GitHub really gave - the transport
is the declared injection point, so nothing here touches the network
(Guardrail #7). What a page becomes and how one member is deleted is tested
beside the adapter; this holds the task to its declaration, and the runs task
to the mark on its own record, filed through the ledger door under `tmp_path`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.gardener import CollectionTaskPolicy, PrunableCollection
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import github_collections, registry, report
from idhazh.gardener.tasks import collection

from .._garden import named_task_modules
from .._records import file_a_record
from ..test_github_collections import (
    OVER_A_THOUSAND,
    REPOSITORY,
    RUNS_BY_DAY,
    RecordedAnswers,
    RecordedApi,
    counted_through,
    day_search,
    fixture,
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

PAGES = FIXTURES_DIR / "github-collections"

#: A recorded transport for each collection, so the task can be run over every word.
SERVED: Final[dict[PrunableCollection, Callable[[], RecordedApi | RecordedAnswers]]] = {
    PrunableCollection.WORKFLOW_ARTIFACTS: lambda: RecordedApi(PAGES / "artifacts-page-1.json"),
    PrunableCollection.WORKFLOW_RUNS: lambda: RecordedAnswers(repository=fixture(REPOSITORY)),
}


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


def test_a_dry_run_names_what_the_window_holds_and_deletes_nothing(tmp_path: Path) -> None:
    """Thirty days back from 2026-09-18 is 2026-08-19, which the third artifact was made on."""
    api = RecordedApi(PAGES / "artifacts-page-1.json")

    outcome = collection.run(context_for("workflow-artifacts", tmp_path, today=WAKE), api=api)

    assert api.removed == [], "a dry run called a delete"
    assert (outcome.collection, outcome.dry_run, outcome.until) == (
        "workflow-artifacts",
        True,
        "2026-08-19",
    )
    assert outcome.taken == ("4529182634", "4529182700", "4529182755")
    assert outcome.written == (), "a collection task writes nothing into the repository"
    assert (outcome.seen, outcome.stopped_because) == (4, StopReason.EXHAUSTED)


def test_a_live_pass_deletes_one_member_a_call_and_stops_at_the_ceiling(tmp_path: Path) -> None:
    """The ceiling is the declaration's, and the next pass resumes at the member it stopped at."""
    api = RecordedApi(PAGES / "artifacts-page-1.json")
    context = context_for(
        "workflow-artifacts", tmp_path, today=WAKE, dry_run=False, max_deletes_per_run=2
    )

    outcome = collection.run(context, api=api)

    assert api.removed == ["actions/artifacts/4529182634", "actions/artifacts/4529182700"]
    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.CEILING, "4529182755")


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
