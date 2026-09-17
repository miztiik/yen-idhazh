"""Does the GitHub driver read a real API page into members, and delete exactly one at a time?

The adapter's whole job is a translation: a page of REST JSON in, a `Member`
out, and a member id into one DELETE. So the test drives it with recorded
pages - the shapes `GET /repos/{owner}/{repo}/actions/artifacts` and
`.../actions/runs` really return - and never the network (Guardrail #7).

The transport is the declared injection point, the way `idhazh.fetch` takes its
connection class. Nothing here is a stand-in for the adapter: the adapter runs,
against bytes an API really produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FIXTURES_DIR

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.knobs.prune import PrunableCollection
from idhazh.prune import github_collections, one_at_a_time
from idhazh.prune.one_at_a_time import Window

pytestmark = pytest.mark.contract


class RecordedApi:
    """The two calls the driver makes, answered from a recorded page.

    `removed` is the whole point of the class: it is the ordered list of the
    paths this was asked to DELETE, which is how a test says "one call a member,
    in this order" rather than "the member is gone".
    """

    def __init__(self, page: Path, *, fails_at: str | None = None) -> None:
        self._page = page
        self._fails_at = fails_at
        self.removed: list[str] = []
        self.read_paths: list[str] = []

    def read(self, path: str) -> dict[str, Any]:
        self.read_paths.append(path)
        payload: dict[str, Any] = json.loads(self._page.read_bytes().decode("utf-8"))
        return payload

    def remove(self, path: str) -> None:
        if self._fails_at is not None and path.endswith(self._fails_at):
            raise OSError("the API said no")
        self.removed.append(path)


def artifacts_page() -> Path:
    """Read inside the test that wants it, never at module scope (CLAUDE.md section 13)."""
    return FIXTURES_DIR / "github-collections" / "artifacts-page-1.json"


def runs_page() -> Path:
    return FIXTURES_DIR / "github-collections" / "runs-page-1.json"


def test_an_artifact_page_becomes_members_with_a_day_and_a_size() -> None:
    """Id, created day and bytes, read off the fields the API really sends."""
    api = RecordedApi(artifacts_page())
    collection = github_collections.artifacts(api)

    members = [collection.describe(raw) for raw in collection.listing()]

    assert [m.id for m in members] == [
        "4529182634",
        "4529182700",
        "4529182755",
        "4529182810",
    ]
    assert [m.day for m in members] == [
        "2026-07-04",
        "2026-08-18",
        "2026-08-19",
        "2026-09-16",
    ]
    assert members[0].size_bytes == 35123456
    assert members[0].label == "github-pages"


def test_a_run_reports_no_size_rather_than_a_made_up_one() -> None:
    """The API publishes no size for a run's logs, so the honest figure is 0."""
    api = RecordedApi(runs_page())
    collection = github_collections.runs(api)

    members = [collection.describe(raw) for raw in collection.listing()]

    assert [m.size_bytes for m in members] == [0, 0, 0]
    assert [m.day for m in members] == ["2026-06-02", "2026-08-18", "2026-09-16"]


def test_a_pass_deletes_one_member_a_call_in_listing_order() -> None:
    """Three members in the window, three DELETEs, each naming exactly one artifact.

    Twenty-nine days before 2026-09-17 is 2026-08-19, which is the third
    artifact's own day - so the window holds three of the four and the boundary
    is a real one rather than a gap.
    """
    api = RecordedApi(artifacts_page())

    taken = one_at_a_time.take(
        github_collections.artifacts(api),
        window=Window.older_than(today="2026-09-17", days=29),
        ceiling=5,
        dry_run=False,
    )

    assert api.removed == [
        "actions/artifacts/4529182634",
        "actions/artifacts/4529182700",
        "actions/artifacts/4529182755",
    ], "one call a member, and the member deleted is the member listed"
    assert taken.taken == ("4529182634", "4529182700", "4529182755")
    assert taken.bytes_freed == 35123456 + 204811 + 1048576
    assert taken.stopped_because is StopReason.EXHAUSTED


def test_the_upper_end_of_an_age_window_is_inclusive() -> None:
    """A member created on the line itself qualifies, and the day after it does not."""
    api = RecordedApi(artifacts_page())

    taken = one_at_a_time.take(
        github_collections.artifacts(api),
        window=Window.older_than(today="2026-09-17", days=30),
        ceiling=5,
    )

    assert taken.until == "2026-08-18"
    assert taken.taken == ("4529182634", "4529182700"), (
        "the artifact created on 2026-08-19 is one day inside the window and was taken"
    )


def test_a_failed_delete_stops_the_pass_and_keeps_what_went_before() -> None:
    """The interruption property, through the real driver rather than a file tree."""
    api = RecordedApi(artifacts_page(), fails_at="4529182700")

    with pytest.raises(one_at_a_time.PruneInterruptedError) as stop:
        one_at_a_time.take(
            github_collections.artifacts(api),
            window=Window.older_than(today="2026-09-17", days=29),
            ceiling=5,
            dry_run=False,
        )

    assert api.removed == ["actions/artifacts/4529182634"], "a later member was still deleted"
    assert stop.value.so_far.taken == ("4529182634",)
    assert stop.value.so_far.resume_from == "4529182700"


def test_a_dry_run_reads_the_collection_and_calls_no_delete() -> None:
    """The default. It pages the API and touches nothing."""
    api = RecordedApi(artifacts_page())

    taken = one_at_a_time.take(
        github_collections.artifacts(api),
        window=Window.older_than(today="2026-09-17", days=29),
        ceiling=5,
    )

    assert api.removed == []
    assert len(taken.taken) == 3, "a dry run names what a live pass would take"


def test_a_short_page_ends_the_walk() -> None:
    """One request, because a page under 100 members is the last page.

    Stopping on a short page rather than on `total_count` is what makes this
    safe while it is deleting: the count is a fact about the moment the first
    page was read, and a pass that is deleting is changing it.
    """
    api = RecordedApi(artifacts_page())

    list(github_collections.artifacts(api).listing())

    assert api.read_paths == ["actions/artifacts?per_page=100&page=1"]


def test_every_collection_in_the_vocabulary_has_a_driver() -> None:
    """A word with no builder would be a command that reports success and does nothing."""
    assert set(github_collections.BUILDERS) == set(PrunableCollection)


@pytest.mark.parametrize("repo", ["not-a-slug", "owner/name/extra", "../../etc", "owner/"])
def test_a_repository_that_is_not_owner_slash_name_is_refused(repo: str) -> None:
    """The slug is interpolated into an API address, so it is checked as an identity."""
    with pytest.raises(ValueError, match="owner/name"):
        github_collections.RestApi(repo, token="not-a-real-token")


def test_a_missing_token_is_named_without_its_value_ever_existing() -> None:
    """The failure says which variable to set and never prints a secret (section 1b)."""
    with pytest.raises(ValueError, match=github_collections.TOKEN_ENV):
        github_collections.RestApi("miztiik/yen-idhazh", token="")
