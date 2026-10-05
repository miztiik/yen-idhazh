"""Does the GitHub driver read a real API answer into members, and delete exactly one at a time?

The adapter's whole job is a translation: a page of REST JSON in, a `Member`
out, a member id into one DELETE, and a span of UTC days into the searches that
list the runs created in it. So the test drives it with recorded answers - what
`GET /repos/{owner}/{repo}`, `.../actions/artifacts` and `.../actions/runs`
really returned - and never the network (Guardrail #7).

The transport is the declared injection point, the way `idhazh.fetch` takes its
connection class. Nothing here is a stand-in for the adapter: the adapter runs,
against bytes an API really produced. The runs and the repository were recorded
from this repository on 2026-10-04, each run trimmed to the fields that say
which run it is.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import FIXTURES_DIR

from idhazh.contracts.collection_prune import StopReason
from idhazh.gardener import github_collections, one_at_a_time
from idhazh.gardener.one_at_a_time import Window

pytestmark = pytest.mark.contract

#: GitHub's answers to searches of the runs by the day they were created, and to
#: the counts of runs created on or before a day, keyed by the request.
RUNS_BY_DAY: Final = "runs-by-day.json"
#: The answers for 2026-08-22, the oldest day with a run, with the day's own
#: count raised to 1,001 - the one field changed - and its 24 hourly answers.
OVER_A_THOUSAND: Final = "runs-a-day-over-a-thousand.json"
#: The repository's own answer, which says the day it was created.
REPOSITORY: Final = "repository.json"


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


class RecordedAnswers:
    """GitHub's recorded answers, each served for the one request it answered.

    A recording maps each request path to the answer it got, so a test reads
    what was asked off the same strings the adapter sends. `answering` adds or
    replaces an answer for a test's own case. A request with no answer raises,
    naming it, as a request GitHub could not answer would.
    """

    def __init__(
        self,
        *recordings: Path,
        repository: Path | None = None,
        answering: Mapping[str, dict[str, Any]] | None = None,
    ) -> None:
        self._answers: dict[str, dict[str, Any]] = {}
        for recording in recordings:
            self._answers.update(json.loads(recording.read_bytes().decode("utf-8")))
        if repository is not None:
            self._answers[""] = json.loads(repository.read_bytes().decode("utf-8"))
        self._answers.update(answering or {})
        self.read_paths: list[str] = []
        self.removed: list[str] = []

    def read(self, path: str) -> dict[str, Any]:
        self.read_paths.append(path)
        if path not in self._answers:
            raise LookupError(f"no answer was recorded for {path!r}")
        return copy.deepcopy(self._answers[path])

    def remove(self, path: str) -> None:
        self.removed.append(path)


class ShrinkingDay:
    """One recorded day of runs, paged the way GitHub pages it while a pass deletes from it.

    Each page is cut from the runs still there, newest first, so deleting a run
    moves every later run up one place. That shift is what makes a walk that
    reads front to back while it deletes step over runs it never read.
    """

    def __init__(self, recording: Path, day: str, *, pages: int) -> None:
        answers = json.loads(recording.read_bytes().decode("utf-8"))
        self._day = day
        self._runs: list[dict[str, Any]] = [
            run
            for page in range(1, pages + 1)
            for run in answers[day_search(day, page=page)]["workflow_runs"]
        ]
        self.read_paths: list[str] = []
        self.removed: list[str] = []

    @property
    def remaining(self) -> int:
        return len(self._runs)

    def read(self, path: str) -> dict[str, Any]:
        self.read_paths.append(path)
        searched = range(1, github_collections.SEARCH_LIMIT // github_collections.PAGE_SIZE + 1)
        page = next((n for n in searched if path == day_search(self._day, page=n)), None)
        if page is None:
            raise LookupError(f"no answer was recorded for {path!r}")
        start = (page - 1) * github_collections.PAGE_SIZE
        held = self._runs[start : start + github_collections.PAGE_SIZE]
        return {"total_count": len(self._runs), "workflow_runs": copy.deepcopy(held)}

    def remove(self, path: str) -> None:
        self.removed.append(path)
        gone = path.removeprefix("actions/runs/")
        self._runs = [run for run in self._runs if str(run["id"]) != gone]


def fixture(name: str) -> Path:
    """Read inside the test that wants it, never at module scope (CLAUDE.md section 13)."""
    return FIXTURES_DIR / "github-collections" / name


def recorded(name: str, path: str) -> dict[str, Any]:
    """One recorded answer, to build a test's own case from."""
    answer: dict[str, Any] = json.loads(fixture(name).read_bytes().decode("utf-8"))[path]
    return answer


def day_search(day: str, *, page: int = 1, hour: int | None = None) -> str:
    """The search the adapter sends for one UTC day, or one hour of it, as a person types it."""
    start, end = ("00:00:00", "23:59:59") if hour is None else (f"{hour:02d}:00:00", f"{hour:02d}:59:59")
    return f"actions/runs?created={day}T{start}Z..{day}T{end}Z&per_page=100&page={page}"


def counted_through(day: str) -> str:
    """The one-run search the halving sends to count the runs created on or before a day."""
    return f"actions/runs?created=%3C%3D{day}T23:59:59Z&per_page=1"


def artifacts_page() -> Path:
    return fixture("artifacts-page-1.json")


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
    api = RecordedAnswers(fixture(RUNS_BY_DAY))
    collection = github_collections.runs(api, after="2026-08-21", through="2026-08-22")

    members = [collection.describe(raw) for raw in collection.listing()]

    assert len(members) == 43
    assert {m.size_bytes for m in members} == {0}
    assert {m.day for m in members} == {"2026-08-22"}


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


# --- The runs, a UTC day at a time ---------------------------------------------


def test_the_runs_are_searched_one_utc_day_at_a_time_oldest_first() -> None:
    """Each search spans one UTC day, 00:00:00Z to 23:59:59Z, so GitHub chooses no time zone."""
    api = RecordedAnswers(fixture(RUNS_BY_DAY))

    list(github_collections.runs(api, after="2026-06-30", through="2026-07-06").listing())

    assert api.read_paths[0] == (
        "actions/runs?created=2026-07-01T00:00:00Z..2026-07-01T23:59:59Z&per_page=100&page=1"
    )
    assert api.read_paths == [day_search(f"2026-07-0{day}") for day in range(1, 7)]


def test_a_day_over_a_thousand_is_searched_an_hour_at_a_time() -> None:
    """One search returns at most 1,000 runs, so a day counted at 1,001 is asked by the hour.

    The day's own answer is dropped rather than read beside the hours, so each
    of its 43 runs is listed once.
    """
    api = RecordedAnswers(fixture(OVER_A_THOUSAND))

    members = list(github_collections.runs(api, after="2026-08-21", through="2026-08-22").listing())

    assert api.read_paths == [
        day_search("2026-08-22"),
        *(day_search("2026-08-22", hour=hour) for hour in range(24)),
    ]
    assert len(members) == len({run["id"] for run in members}) == 43


def test_an_hour_over_a_thousand_is_refused_by_name_and_no_later_hour_is_read() -> None:
    """Nothing smaller than an hour is searched, so an hour one search cannot hold stops the walk."""
    nine = day_search("2026-08-22", hour=9)
    crowded = recorded(OVER_A_THOUSAND, nine) | {"total_count": 1001}
    api = RecordedAnswers(fixture(OVER_A_THOUSAND), answering={nine: crowded})

    with pytest.raises(ValueError, match="in the hour from 2026-08-22T09:00:00Z"):
        list(github_collections.runs(api, after="2026-08-21", through="2026-08-22").listing())

    assert api.read_paths[-1] == nine


def test_a_search_is_read_from_its_last_page_back() -> None:
    """The first page is read for its count and handed on last; the last page goes first."""
    api = RecordedAnswers(fixture(RUNS_BY_DAY))

    members = list(github_collections.runs(api, after="2026-08-24", through="2026-08-25").listing())

    newest = recorded(RUNS_BY_DAY, day_search("2026-08-25"))["workflow_runs"]
    oldest = recorded(RUNS_BY_DAY, day_search("2026-08-25", page=2))["workflow_runs"]
    assert api.read_paths == [day_search("2026-08-25"), day_search("2026-08-25", page=2)]
    assert [run["id"] for run in members] == [run["id"] for run in (*oldest, *newest)]


def test_a_live_walk_that_deletes_as_it_reads_misses_no_run_of_a_two_page_day() -> None:
    """A delete moves every later run up one place, so reading from the last page back skips none.

    Read front to back, deleting page one's 100 runs would move the day's other
    21 onto page one, page two would come back empty, and the walk would pass
    the day with those 21 never read.
    """
    api = ShrinkingDay(fixture(RUNS_BY_DAY), "2026-08-25", pages=2)

    outcome = one_at_a_time.take(
        github_collections.runs(api, after="2026-08-24", through="2026-08-25"),
        window=Window(until="2026-08-25"),
        ceiling=200,
        dry_run=False,
        mark="2026-08-24",
    )

    assert len(api.removed) == len(set(api.removed)) == 121
    assert api.remaining == 0, "a run of the day was never read, so never deleted"
    assert (outcome.stopped_because, outcome.handled_through) == (
        StopReason.EXHAUSTED,
        "2026-08-25",
    )


# --- Where a first walk of the runs starts --------------------------------------


def test_a_line_before_the_repository_was_made_is_the_first_mark_and_no_run_is_read() -> None:
    """The repository was created on 2026-08-20, so no run is older than a line before it."""
    api = RecordedAnswers(repository=fixture(REPOSITORY))

    assert github_collections.first_mark(api, line="2026-07-06") == "2026-07-06"
    assert api.read_paths == [""]


def test_the_halving_finds_the_oldest_day_with_a_run_from_recorded_counts() -> None:
    """No run was made on or before 2026-08-21 and 43 on or before 2026-08-22.

    The days from 2026-08-20 to the line are halved, one count a step, so the
    walk starts on the oldest day with a run and the mark is the day before it.
    """
    api = RecordedAnswers(fixture(RUNS_BY_DAY), repository=fixture(REPOSITORY))

    assert github_collections.first_mark(api, line="2026-08-22") == "2026-08-21"
    assert api.read_paths == ["", counted_through("2026-08-21"), counted_through("2026-08-22")]


def test_with_no_run_on_or_before_the_line_the_first_mark_is_the_line() -> None:
    api = RecordedAnswers(fixture(RUNS_BY_DAY), repository=fixture(REPOSITORY))

    assert github_collections.first_mark(api, line="2026-08-21") == "2026-08-21"
    assert api.read_paths == ["", counted_through("2026-08-21")]


def test_an_empty_path_addresses_the_repository_itself() -> None:
    """The repository's own answer sits at its address with nothing after it."""
    api = github_collections.RestApi("miztiik/yen-idhazh", token="not-a-real-token")

    assert api._url("") == "https://api.github.com/repos/miztiik/yen-idhazh"
    assert api._url("actions/runs") == "https://api.github.com/repos/miztiik/yen-idhazh/actions/runs"


@pytest.mark.parametrize("repo", ["not-a-slug", "owner/name/extra", "../../etc", "owner/"])
def test_a_repository_that_is_not_owner_slash_name_is_refused(repo: str) -> None:
    """The slug is interpolated into an API address, so it is checked as an identity."""
    with pytest.raises(ValueError, match="owner/name"):
        github_collections.RestApi(repo, token="not-a-real-token")


def test_a_missing_token_is_named_without_its_value_ever_existing() -> None:
    """The failure says which variable to set and never prints a secret (section 1b)."""
    with pytest.raises(ValueError, match=github_collections.TOKEN_ENV):
        github_collections.RestApi("miztiik/yen-idhazh", token="")
