"""Does the collection task prune the collection its declaration names, by its window, as it ships?

Driven through the task's own module and the committed declarations, found the
way the runner finds them, against pages the Actions API really returned - the
transport is the declared injection point, so nothing here touches the network
(Guardrail #7). What a page becomes and how one member is deleted is tested
beside the adapter; this holds the task to its declaration.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.knobs.gardener import CollectionTaskPolicy
from idhazh.gardener import github_collections, registry
from idhazh.gardener.tasks import collection

from .._garden import named_task_modules
from ..test_github_collections import RecordedApi
from ._task import context_for, declared

pytestmark = pytest.mark.contract

#: A wake the recorded pages were read against: the newest member is two days old.
WAKE = date(2026, 9, 18)

PAGES = FIXTURES_DIR / "github-collections"


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


def test_the_runs_task_reads_the_runs_collection_by_its_own_window(tmp_path: Path) -> None:
    """Ninety days back from 2026-09-18 is 2026-06-20, so only the June run qualifies."""
    api = RecordedApi(PAGES / "runs-page-1.json")

    outcome = collection.run(context_for("workflow-runs", tmp_path, today=WAKE), api=api)

    assert api.read_paths == ["actions/runs?per_page=100&page=1"]
    assert outcome.until == "2026-06-20"
    assert len(outcome.taken) == 1
    assert outcome.bytes_freed == 0, "a run's logs have no size the API publishes"


def test_without_a_named_repository_the_task_fails_and_says_which_variable_to_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner turns this into the task's `failed` row, and its siblings still run."""
    monkeypatch.delenv(github_collections.REPO_ENV, raising=False)

    with pytest.raises(ValueError, match=github_collections.REPO_ENV):
        collection.run(context_for("workflow-artifacts", tmp_path, today=WAKE))
