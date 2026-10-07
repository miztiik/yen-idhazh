"""Does the GitHub driver read a real API answer into members, and delete exactly one at a time?

The adapter's whole job is a translation: a page of REST JSON in, a `Member`
out, a member id into one DELETE, a span of UTC days into the searches that
list the runs created in it, and the artifacts' pages into a walk from the
oldest end. So the test drives it with recorded answers - what
`GET /repos/{owner}/{repo}`, `.../actions/artifacts` and `.../actions/runs`
really returned - and never the network (Guardrail #7).

The transport is the declared injection point, the way `idhazh.fetch` takes its
connection class. Nothing here is a stand-in for the adapter: the adapter runs,
against bytes an API really produced. The runs and the repository were recorded
from this repository on 2026-10-04, each run trimmed to the fields that say
which run it is; the artifacts on 2026-10-05, each trimmed to the four fields
`describe` reads.
"""

from __future__ import annotations

import copy
import email.message
import io
import json
import urllib.error
from collections.abc import Mapping
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import FIXTURES_DIR

from idhazh.contracts.collection_prune import Recovery, StopReason
from idhazh.contracts.gardener_events import ListEndMissing, PageCountChanged, PageOutOfOrder
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.gardener import event_log, github_collections, one_at_a_time
from idhazh.gardener.one_at_a_time import Member, Window

from ._events import events, the_event

pytestmark = pytest.mark.contract

#: GitHub's answers to searches of the runs by the day they were created, and to
#: the counts of runs created on or before a day, keyed by the request.
RUNS_BY_DAY: Final = "runs-by-day.json"
#: The answers for 2026-08-22, the oldest day with a run, with the day's own
#: count raised to 1,001 - the one field changed - and its 24 hourly answers.
OVER_A_THOUSAND: Final = "runs-a-day-over-a-thousand.json"
#: The repository's own answer, which says the day it was created.
REPOSITORY: Final = "repository.json"
#: GitHub's last four pages of the 1,613 artifacts it listed on 2026-10-05 -
#: the oldest 313, by id and newest first, as GitHub orders them - served as
#: pages 1 to 4 of a collection of 313. The boundaries fall where GitHub's did,
#: because the 1,300 artifacts left out fill 13 whole pages.
ARTIFACT_PAGES: Final = "artifacts-oldest-pages.json"
#: The thirty-day line on the day the artifacts were recorded.
RECORDED_LINE: Final = "2026-09-05"


class RecordedAnswers:
    """GitHub's recorded answers, each served for the one request it answered.

    A recording maps each request path to the answer it got, so a test reads
    what was asked off the same strings the adapter sends. `answering` adds or
    replaces an answer for a test's own case. A request with no answer raises,
    naming it, as a request GitHub could not answer would.

    `removed` is the ordered list of the paths this was asked to DELETE, which is
    how a test says "one call a member, in this order" rather than "the member is
    gone". A DELETE whose path ends in `fails_at` is refused, as the API can
    refuse one. A request named in `refusing` is answered with that status code,
    raised as the `HTTPError` `urlopen` raises for GitHub's refusal.
    """

    def __init__(
        self,
        *recordings: Path,
        repository: Path | None = None,
        answering: Mapping[str, dict[str, Any]] | None = None,
        fails_at: str | None = None,
        refusing: Mapping[str, int] | None = None,
    ) -> None:
        self._answers: dict[str, dict[str, Any]] = {}
        for recording in recordings:
            self._answers.update(json.loads(recording.read_bytes().decode("utf-8")))
        if repository is not None:
            self._answers[""] = json.loads(repository.read_bytes().decode("utf-8"))
        self._answers.update(answering or {})
        self._fails_at = fails_at
        self._refusing = dict(refusing or {})
        self.read_paths: list[str] = []
        self.removed: list[str] = []

    def _refuse(self, path: str) -> None:
        """GitHub's refusal of this request, when the case names one."""
        status = self._refusing.get(path)
        if status is not None:
            raise urllib.error.HTTPError(
                f"{github_collections.API_ROOT}/repos/miztiik/yen-idhazh/{path}",
                status,
                HTTPStatus(status).phrase,
                email.message.Message(),
                io.BytesIO(b"{}"),
            )

    def read(self, path: str) -> dict[str, Any]:
        self.read_paths.append(path)
        self._refuse(path)
        if path not in self._answers:
            raise LookupError(f"no answer was recorded for {path!r}")
        return copy.deepcopy(self._answers[path])

    def remove(self, path: str) -> None:
        self._refuse(path)
        if self._fails_at is not None and path.endswith(self._fails_at):
            raise OSError("the API said no")
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


def artifact_page(page: int) -> str:
    """The request for one page of the artifacts, as the walk sends it."""
    return f"actions/artifacts?per_page=100&page={page}"


def oldest_first(page: int) -> list[dict[str, Any]]:
    """One recorded page's artifacts in the order they were created, oldest first."""
    artifacts: list[dict[str, Any]] = recorded(ARTIFACT_PAGES, artifact_page(page))["artifacts"]
    return sorted(artifacts, key=lambda artifact: str(artifact["created_at"]))


def test_an_artifact_becomes_a_member_with_its_id_day_size_and_name() -> None:
    """Read off the fields the API really sends, for the oldest artifact GitHub listed."""
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))
    collection = github_collections.artifacts(api, through=RECORDED_LINE)

    members = [collection.describe(raw) for raw in collection.listing()]

    assert members[0] == Member(
        id="9472586501", day="2026-08-22", size_bytes=1557, label="bench-corpus"
    )
    assert len(members) == 10


def test_a_run_reports_no_size_rather_than_a_made_up_one() -> None:
    """The API publishes no size for a run's logs, so the honest figure is 0."""
    api = RecordedAnswers(fixture(RUNS_BY_DAY))
    collection = github_collections.runs(api, after="2026-08-21", through="2026-08-22")

    members = [collection.describe(raw) for raw in collection.listing()]

    assert len(members) == 43
    assert {m.size_bytes for m in members} == {0}
    assert {m.day for m in members} == {"2026-08-22"}


# --- The artifacts, from the oldest end -----------------------------------------


def test_a_walk_reads_the_last_page_and_one_more_and_hands_on_the_oldest_first() -> None:
    """GitHub's own order: page 1 for the count, then page 4, then page 3 to check it by.

    The line falls inside page 4, so nothing older waits on a later page: page 3
    is read only to check that its oldest day is not before page 4's newest.
    """
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))
    walk = github_collections.artifacts(api, through=RECORDED_LINE)

    members = list(walk.listing())

    assert api.read_paths == [artifact_page(1), artifact_page(4), artifact_page(3)]
    assert [raw["id"] for raw in members] == [raw["id"] for raw in oldest_first(4)[:10]]
    assert walk.listing_intact()
    assert walk.pages_read() == 3, "the pass's record counts every page the walk read"


def test_times_that_cross_inside_one_utc_day_do_not_send_the_walk_through_every_page() -> None:
    """GitHub's page 3 holds an artifact made at 22:14 on 2026-09-17, page 2 one at 22:02.

    GitHub orders by id, and the instants disagree with it by up to an hour, so
    a check by instant would fail here. The days agree, and the day is what the
    mark and the line count, so the walk stays intact and stops at its line.
    """
    third = recorded(ARTIFACT_PAGES, artifact_page(3))["artifacts"]
    second = recorded(ARTIFACT_PAGES, artifact_page(2))["artifacts"]
    latest, earliest = max(a["created_at"] for a in third), min(a["created_at"] for a in second)
    assert latest > earliest, "the recorded boundary no longer crosses"
    assert latest[:10] == earliest[:10] == "2026-09-17"
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))
    walk = github_collections.artifacts(api, through="2026-09-15")

    members = list(walk.listing())

    assert api.read_paths == [artifact_page(page) for page in (1, 4, 3, 2)]
    assert walk.listing_intact()
    assert len(members) == 13 + 44, "page 4 whole, then page 3 up to 2026-09-15"


def test_a_page_from_a_day_before_one_already_read_sends_the_walk_through_every_page(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Page 4's newest artifact moved to 00:05 on 2026-09-15 - the one field changed.

    Page 3 holds artifacts from 23:24 the day before, so the two pages cross
    midnight and which days are whole can no longer be said. The walk reads
    every page, each once and still from the last back, hands on every artifact,
    and is no longer intact.
    """
    last = recorded(ARTIFACT_PAGES, artifact_page(4))
    moved = next(raw for raw in last["artifacts"] if raw["id"] == 10336260332)
    moved["created_at"] = "2026-09-15T00:05:00Z"
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), answering={artifact_page(4): last})
    walk = github_collections.artifacts(api, through=RECORDED_LINE)

    with caplog.at_level("WARNING", logger=event_log.__name__):
        members = list(walk.listing())

    assert api.read_paths == [artifact_page(page) for page in (1, 4, 3, 2)]
    assert len(members) == len({raw["id"] for raw in members}) == 313
    assert not walk.listing_intact()
    assert the_event(caplog.records, PageOutOfOrder) == PageOutOfOrder(
        collection="workflow-artifacts", page=3
    )


def test_a_count_that_grows_between_two_reads_leaves_the_walk_not_intact(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Page 3 read after one artifact was made: every artifact moved one place on.

    So page 2's last artifact is now page 3's first, page 3's last moved onto
    page 4, which was already read, and GitHub counts 314. The order still
    holds, so only the count can say an artifact slipped past the walk.
    """
    second = recorded(ARTIFACT_PAGES, artifact_page(2))["artifacts"]
    third = recorded(ARTIFACT_PAGES, artifact_page(3))["artifacts"]
    pushed = {"total_count": 314, "artifacts": [second[-1], *third[:-1]]}
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), answering={artifact_page(3): pushed})
    walk = github_collections.artifacts(api, through=RECORDED_LINE)

    with caplog.at_level("WARNING", logger=event_log.__name__):
        members = list(walk.listing())

    assert api.read_paths == [artifact_page(1), artifact_page(4), artifact_page(3)]
    assert len(members) == 10, "the walk handled what it read"
    assert not walk.listing_intact()
    assert the_event(caplog.records, PageCountChanged) == PageCountChanged(
        collection="workflow-artifacts", page=3, counted=314, expected=313
    )


@pytest.mark.parametrize(
    ("counted", "after_the_last", "reads", "intact"),
    [
        pytest.param(300, None, (1, 3, 4, 2), False, id="a-full-last-page-with-artifacts-after-it"),
        pytest.param(250, None, (1, 3, 2), False, id="a-last-page-holding-more-than-is-left"),
        pytest.param(300, [], (1, 3, 4, 2), True, id="a-full-last-page-with-nothing-after-it"),
    ],
)
def test_the_list_must_end_where_the_first_page_count_says(
    counted: int,
    after_the_last: list[Any] | None,
    reads: tuple[int, ...],
    intact: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every page counted as `counted`: the count names page 3 as the last of the 313.

    A count that stopped short of the list would start the walk in its middle,
    and the mark would pass the older pages unread. So the last page must hold
    what is left of the count, and when it is full the page after it is read,
    never handed on, and must be empty.
    """
    answers = {
        artifact_page(page): recorded(ARTIFACT_PAGES, artifact_page(page)) | {"total_count": counted}
        for page in range(1, 5)
    }
    if after_the_last is not None:
        answers[artifact_page(4)] = {"total_count": counted, "artifacts": after_the_last}
    api = RecordedAnswers(answering=answers)
    walk = github_collections.artifacts(api, through=RECORDED_LINE)

    with caplog.at_level("WARNING", logger=event_log.__name__):
        members = list(walk.listing())

    assert api.read_paths == [artifact_page(page) for page in reads]
    assert members == [], "the oldest artifact on page 3 is newer than the line"
    assert walk.listing_intact() is intact
    assert events(caplog.records, ListEndMissing) == (
        [] if intact else [ListEndMissing(collection="workflow-artifacts", page=3, first_count=counted)]
    )


def test_a_page_read_after_deletes_is_held_to_the_count_they_left() -> None:
    """Page 2 is read after page 4's 13 artifacts went, so GitHub counts 313 less 13.

    A walk that held every page to the first page's count would call its own
    deletes a gap, and no live pass that reached a second page would move its
    mark.
    """
    second = recorded(ARTIFACT_PAGES, artifact_page(2)) | {"total_count": 300}
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), answering={artifact_page(2): second})

    outcome = one_at_a_time.take(
        github_collections.artifacts(api, through="2026-09-15"),
        window=Window(until="2026-09-15"),
        ceiling=None,
        dry_run=False,
        mark="2026-08-19",
    )

    assert api.read_paths == [artifact_page(page) for page in (1, 4, 3, 2)]
    assert len(api.removed) == 13 + 44
    assert (outcome.stopped_because, outcome.handled_through) == (
        StopReason.EXHAUSTED,
        "2026-09-15",
    )


def test_a_pass_deletes_one_artifact_a_call_oldest_first() -> None:
    """Five DELETEs for a ceiling of five, each naming the artifact it listed."""
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))

    taken = one_at_a_time.take(
        github_collections.artifacts(api, through=RECORDED_LINE),
        window=Window.older_than(today="2026-10-05", days=30),
        ceiling=5,
        dry_run=False,
    )

    oldest = oldest_first(4)[:5]
    assert api.removed == [f"actions/artifacts/{raw['id']}" for raw in oldest], (
        "one call a member, and the member deleted is the member listed"
    )
    assert taken.taken == tuple(str(raw["id"]) for raw in oldest)
    assert taken.bytes_freed == sum(raw["size_in_bytes"] for raw in oldest)
    assert taken.stopped_because is StopReason.CEILING


def test_the_upper_end_of_an_age_window_is_inclusive() -> None:
    """Thirty days before 2026-09-22 is 2026-08-23: its three artifacts go, 2026-08-24's does not."""
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))

    taken = one_at_a_time.take(
        github_collections.artifacts(api, through="2026-08-23"),
        window=Window.older_than(today="2026-09-22", days=30),
        ceiling=None,
    )

    assert taken.until == "2026-08-23"
    assert taken.taken == tuple(str(raw["id"]) for raw in oldest_first(4)[:9])


def test_a_failed_delete_stops_the_pass_and_keeps_what_went_before() -> None:
    """The interruption property, through the real driver rather than a file tree."""
    first, second = (str(raw["id"]) for raw in oldest_first(4)[:2])
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), fails_at=second)

    with pytest.raises(one_at_a_time.PruneInterruptedError) as stop:
        one_at_a_time.take(
            github_collections.artifacts(api, through=RECORDED_LINE),
            window=Window.older_than(today="2026-10-05", days=30),
            ceiling=5,
            dry_run=False,
        )

    assert api.removed == [f"actions/artifacts/{first}"], "a later member was still deleted"
    assert stop.value.so_far.taken == (first,)
    assert stop.value.so_far.resume_from == second
    assert (stop.value.so_far.stopped_because, stop.value.so_far.fault) == (
        StopReason.FAILED,
        GardenerFault.RAISED,
    )


def test_a_member_github_will_not_delete_is_recorded_and_the_members_either_side_go() -> None:
    """THE ORACLE for a refused delete: member 2 of 3 answers 422, and 1 and 3 are deleted.

    The refused member counts against the ceiling of three, so the pass stops at
    the fourth, and its record names the one it could not delete.
    """
    one, two, three, four = (str(raw["id"]) for raw in oldest_first(4)[:4])
    api = RecordedAnswers(
        fixture(ARTIFACT_PAGES), refusing={f"actions/artifacts/{two}": HTTPStatus.UNPROCESSABLE_ENTITY}
    )

    outcome = one_at_a_time.take(
        github_collections.artifacts(api, through=RECORDED_LINE),
        window=Window.older_than(today="2026-10-05", days=30),
        ceiling=3,
        dry_run=False,
    )

    assert api.removed == [f"actions/artifacts/{one}", f"actions/artifacts/{three}"]
    assert outcome.taken == (one, three)
    assert outcome.recovered == (Recovery(note=RecoveryNote.NOT_DELETABLE, subject=two),)
    assert (outcome.stopped_because, outcome.resume_from, outcome.fault) == (
        StopReason.CEILING,
        four,
        None,
    )


@pytest.mark.parametrize("status", [HTTPStatus.NOT_FOUND, HTTPStatus.GONE], ids=["404", "410"])
def test_a_member_already_gone_counts_as_deleted(status: HTTPStatus) -> None:
    """Somebody else deleted it, or an earlier pass did and its record was lost."""
    one, two, three = (str(raw["id"]) for raw in oldest_first(4)[:3])
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), refusing={f"actions/artifacts/{two}": status})

    outcome = one_at_a_time.take(
        github_collections.artifacts(api, through=RECORDED_LINE),
        window=Window.older_than(today="2026-10-05", days=30),
        ceiling=3,
        dry_run=False,
    )

    assert api.removed == [f"actions/artifacts/{one}", f"actions/artifacts/{three}"]
    assert (outcome.taken, outcome.recovered) == ((one, two, three), ())


def test_an_answer_that_says_the_request_was_wrong_stops_the_pass_as_a_defect() -> None:
    """A 403 is not GitHub being down: the token or the code is wrong, and a person looks."""
    first, second = (str(raw["id"]) for raw in oldest_first(4)[:2])
    api = RecordedAnswers(
        fixture(ARTIFACT_PAGES), refusing={f"actions/artifacts/{second}": HTTPStatus.FORBIDDEN}
    )

    with pytest.raises(one_at_a_time.PruneInterruptedError) as stop:
        one_at_a_time.take(
            github_collections.artifacts(api, through=RECORDED_LINE),
            window=Window.older_than(today="2026-10-05", days=30),
            ceiling=5,
            dry_run=False,
        )

    so_far = stop.value.so_far
    assert (so_far.taken, so_far.resume_from) == ((first,), second)
    assert (so_far.stopped_because, so_far.fault) == (StopReason.FAILED, GardenerFault.RAISED)


@pytest.mark.parametrize(
    "status",
    [HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.TOO_MANY_REQUESTS],
    ids=["503", "429"],
)
def test_a_page_github_could_not_serve_defers_the_pass_and_its_mark_does_not_move(
    status: HTTPStatus,
) -> None:
    """THE ORACLE for an outage: the first page answers 503, so nothing past the mark was read."""
    api = RecordedAnswers(fixture(ARTIFACT_PAGES), refusing={artifact_page(1): status})

    with pytest.raises(one_at_a_time.PruneInterruptedError) as stop:
        one_at_a_time.take(
            github_collections.artifacts(api, through=RECORDED_LINE),
            window=Window(until=RECORDED_LINE),
            ceiling=50,
            dry_run=False,
            mark="2026-08-19",
        )

    so_far = stop.value.so_far
    assert (so_far.stopped_because, so_far.fault) == (
        StopReason.DEFERRED,
        GardenerFault.API_UNAVAILABLE,
    )
    assert (so_far.taken, so_far.resume_from, so_far.handled_through) == ((), None, "2026-08-19")
    assert api.removed == []
    assert "was deferred (api-unavailable)" in str(stop.value)


def test_a_dry_run_reads_the_collection_and_calls_no_delete() -> None:
    """The default. It pages the API and touches nothing."""
    api = RecordedAnswers(fixture(ARTIFACT_PAGES))

    taken = one_at_a_time.take(
        github_collections.artifacts(api, through=RECORDED_LINE),
        window=Window.older_than(today="2026-10-05", days=30),
        ceiling=50,
    )

    assert api.removed == []
    assert len(taken.taken) == 10, "a dry run names what a live pass would take"


def test_a_first_walk_of_the_artifacts_starts_after_the_day_before_the_repository() -> None:
    """The repository was created on 2026-08-20, so no artifact is older than that day.

    A line before it leaves nothing to walk, so the mark is the line itself.
    """
    api = RecordedAnswers(repository=fixture(REPOSITORY))

    assert github_collections.first_artifacts_mark(api, line=RECORDED_LINE) == "2026-08-19"
    assert github_collections.first_artifacts_mark(api, line="2026-08-16") == "2026-08-16"
    assert api.read_paths == ["", ""]


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

    assert github_collections.first_runs_mark(api, line="2026-07-06") == "2026-07-06"
    assert api.read_paths == [""]


def test_the_halving_finds_the_oldest_day_with_a_run_from_recorded_counts() -> None:
    """No run was made on or before 2026-08-21 and 43 on or before 2026-08-22.

    The days from 2026-08-20 to the line are halved, one count a step, so the
    walk starts on the oldest day with a run and the mark is the day before it.
    """
    api = RecordedAnswers(fixture(RUNS_BY_DAY), repository=fixture(REPOSITORY))

    assert github_collections.first_runs_mark(api, line="2026-08-22") == "2026-08-21"
    assert api.read_paths == ["", counted_through("2026-08-21"), counted_through("2026-08-22")]


def test_with_no_run_on_or_before_the_line_the_first_mark_is_the_line() -> None:
    api = RecordedAnswers(fixture(RUNS_BY_DAY), repository=fixture(REPOSITORY))

    assert github_collections.first_runs_mark(api, line="2026-08-21") == "2026-08-21"
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
