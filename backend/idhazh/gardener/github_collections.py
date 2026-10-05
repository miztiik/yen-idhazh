"""Which GitHub collections can a pass delete from, and how does it list, describe and delete one?

Two collections, both held by GitHub on our behalf and neither represented by
any file in this repository - so no other retention rule in this project can
reach them. Measured 2026-09-17 on `miztiik/yen-idhazh`: 612 live workflow
artifacts holding 1,063.2 MB, and 3,551 workflow runs each holding its own logs.

This module is the adapter and nothing else. It turns a page of REST JSON into
`one_at_a_time.Member`, a member id into one DELETE, a span of UTC days into
the searches that list the runs created in it, and the artifacts' pages into a
walk from the oldest end that checks each page it reads. The window, the
ceiling and the resume point are all the core's: a caller names the days, and
nothing here decides which ones. Where a first walk of either collection starts
is read from GitHub too - from the day the repository was created and, for the
runs, from counts of the runs created on or before a day - never from a count of
the whole collection.

**The transport is an injection point, so a test needs no network**
(Guardrail #7). `Api` is the whole surface the two builders below use, and the
default is `RestApi`. A test hands in a reader over a recorded page instead, the
way `idhazh.fetch` takes its connection class.

**Standard library HTTP, deliberately** (Guardrail #8). `idhazh.fetch` already
reads the open web with `urllib.request`, so the house pattern exists and this
adds no dependency for the two gardener tasks that call it once a wake. The
beneficiary `httpx` or `requests` would have is connection pooling across a few
dozen requests, which is worth nothing here: a pass does at most `ceiling`
deletes and each one is a round trip to a rate-limited API.

**The token and the repository come from the environment, and the token never
reaches a log record** (section 1b). Actions sets both for the step that runs the
gardener's collection tasks, and the token acts on that one repository alone, so
the two cannot disagree. The token is read once, put in one header, and never
returned, printed or put in an error message.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any, Final, Protocol
from urllib.parse import quote

from idhazh.contracts.knobs.gardener import PrunableCollection
from idhazh.gardener.one_at_a_time import Collection, Member

logger = logging.getLogger(__name__)

#: The environment variable the token arrives in. Actions sets it on the step
#: that runs the collection tasks; an operator running one by hand exports it.
#: Named as a constant so the failure message can say which variable without
#: the value ever being near it.
TOKEN_ENV: Final = "GITHUB_TOKEN"

#: The variable Actions sets to `owner/name` for every run.
REPO_ENV: Final = "GITHUB_REPOSITORY"

API_ROOT: Final = "https://api.github.com"

#: The largest page the Actions API serves. One request a hundred members is the
#: difference between six requests and 612 for the artifact collection.
PAGE_SIZE: Final = 100

#: The most runs one search by creation instant returns, however many pages are
#: asked for. GitHub's number, not a knob: a span holding more is read in parts.
SEARCH_LIMIT: Final = 1000

#: The hours a UTC day is split into when it holds more runs than one search
#: returns. UTC keeps no daylight saving, so every day has exactly this many.
HOURS_A_DAY: Final = 24

#: `owner/name`, and nothing that could steer a URL somewhere else. A repository
#: slug reaches this module from the environment, and it is
#: interpolated into a URL - so it is validated as an identity rather than
#: trusted as text (Guardrail #11).
_REPO_PATTERN: Final = re.compile(r"^[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}$")

#: Where each collection's members are listed, what key holds them, and how to
#: address one. The single place a route is spelled, so a collection cannot be
#: listed from one path and deleted through another.
_ROUTES: Final[dict[PrunableCollection, tuple[str, str]]] = {
    PrunableCollection.WORKFLOW_ARTIFACTS: ("actions/artifacts", "artifacts"),
    PrunableCollection.WORKFLOW_RUNS: ("actions/runs", "workflow_runs"),
}


class Api(Protocol):
    """The two things a collection driver asks of a transport."""

    def read(self, path: str) -> dict[str, Any]:
        """One GET, decoded. `path` is repository-relative, such as `actions/artifacts`.

        An empty path is the repository itself.
        """

    def remove(self, path: str) -> None:
        """One DELETE. Returns when the member is gone."""


class RestApi:
    """`api.github.com`, over the standard library, with the token from the environment."""

    def __init__(self, repo: str, *, token: str | None = None) -> None:
        if not _REPO_PATTERN.fullmatch(repo):
            raise ValueError(
                f"a repository is named owner/name, not {repo!r}. It is interpolated into "
                "an API address, so it is checked as an identity rather than trusted"
            )
        secret = token if token is not None else os.environ.get(TOKEN_ENV)
        if not secret:
            raise ValueError(
                f"{TOKEN_ENV} is not set, so nothing can be listed or deleted. Export a "
                "token with the actions:write scope for this repository"
            )
        self._repo = repo
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {secret}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "yen-idhazh-prune",
        }

    def _url(self, path: str) -> str:
        root = f"{API_ROOT}/repos/{self._repo}"
        return f"{root}/{path}" if path else root

    def read(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(self._url(path), headers=self._headers, method="GET")
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return payload

    def remove(self, path: str) -> None:
        request = urllib.request.Request(self._url(path), headers=self._headers, method="DELETE")
        try:
            with urllib.request.urlopen(request, timeout=30):
                return
        except urllib.error.HTTPError as refusal:
            # 404 is success arriving late: somebody else deleted it, or a
            # previous pass did and its record was lost. Anything else is a
            # failure the core has to stop on.
            if refusal.code == 404:
                return
            raise


def api_of_this_repository() -> RestApi:
    """The API for the repository this run belongs to, as Actions names it.

    A missing repository is refused the way a missing token is, by the name of
    the variable to set: the task that asked fails, and its siblings still run.
    """
    repo = os.environ.get(REPO_ENV, "")
    if not repo:
        raise ValueError(
            f"{REPO_ENV} is not set, so no repository is named. Actions sets it for every "
            "run; a person running a collection task by hand exports it as owner/name"
        )
    return RestApi(repo)


def _page(route: str, page: int, *, created: str | None = None) -> str:
    """The address of one page of a route, of members created inside `created` when named.

    `created` is a span of instants in GitHub's search syntax. Its colons stay
    as they are and nothing else in it needs escaping, so the address a test
    reads is the span a person would type.
    """
    query = "" if created is None else f"created={quote(created, safe=':')}&"
    return f"{route}?{query}per_page={PAGE_SIZE}&page={page}"


def _count(answer: dict[str, Any]) -> int:
    """How many members a search holds, as GitHub counted them when it answered."""
    return int(answer["total_count"])


def _last_page(answer: dict[str, Any]) -> int:
    """The number of the last page a first page's count names: 0 when the count is 0."""
    return -(-_count(answer) // PAGE_SIZE)


def _from_the_last_page(api: Api, span: str, first: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every run one search holds, its last page first and its first page last.

    A run deleted from a page moves every later run up one place, so a walk
    front to back that deletes as it goes would start each next page past runs
    nobody read - and a walk from a mark would then pass them for good. Read
    from the last page back, a delete moves only runs already read. The first
    page, read first for its count, is handed on last: it holds the newest runs
    of the span, and deleting older ones moves none of them. Nothing new is
    created in a span that has passed, so the count does not grow underneath.
    """
    route, key = _ROUTES[PrunableCollection.WORKFLOW_RUNS]
    for page in range(_last_page(first), 1, -1):
        yield from api.read(_page(route, page, created=span)).get(key, [])
    yield from first.get(key, [])


def _runs_on(api: Api, day: str) -> Iterator[dict[str, Any]]:
    """Every run created on one UTC day: one search, or one an hour when the day holds more.

    Both ends of every span carry `Z`, so which day is meant is never left to
    GitHub. A day over `SEARCH_LIMIT` is searched again an hour at a time, and
    its first answer is dropped, because one search would miss runs past the
    limit. An hour over it is refused by name rather than read in part: the
    pass then fails, and its mark stays on the last day it read whole.
    """
    route, _ = _ROUTES[PrunableCollection.WORKFLOW_RUNS]
    whole = f"{day}T00:00:00Z..{day}T23:59:59Z"
    first = api.read(_page(route, 1, created=whole))
    if _count(first) <= SEARCH_LIMIT:
        yield from _from_the_last_page(api, whole, first)
        return
    for hour in range(HOURS_A_DAY):
        span = f"{day}T{hour:02d}:00:00Z..{day}T{hour:02d}:59:59Z"
        answer = api.read(_page(route, 1, created=span))
        if _count(answer) > SEARCH_LIMIT:
            raise ValueError(
                f"{_count(answer)} runs were created in the hour from {day}T{hour:02d}:00:00Z, "
                f"over the {SEARCH_LIMIT} one search returns, so the hour cannot be read whole. "
                "The mark stays on the day before until _runs_on in github_collections.py "
                "searches spans shorter than an hour"
            )
        yield from _from_the_last_page(api, span, answer)


def _runs_created(api: Api, after: str, through: str) -> Iterator[dict[str, Any]]:
    """Every run created after one UTC day and up to another, a day at a time, oldest first."""
    day = date.fromisoformat(after) + timedelta(days=1)
    last = date.fromisoformat(through)
    while day <= last:
        yield from _runs_on(api, day.isoformat())
        day += timedelta(days=1)


def _runs_on_or_before(api: Api, day: str) -> int:
    """How many runs were created on or before the end of one UTC day: one search of one run."""
    route, _ = _ROUTES[PrunableCollection.WORKFLOW_RUNS]
    created = quote(f"<={day}T23:59:59Z", safe=":")
    return _count(api.read(f"{route}?created={created}&per_page=1"))


def _created_on(api: Api) -> date:
    """The UTC day the repository was created, read from its own answer: no member is older."""
    return date.fromisoformat(_day_of(str(api.read("")["created_at"])))


def first_runs_mark(api: Api, *, line: str) -> str:
    """The UTC day a first walk of the runs starts after, read from GitHub and never from a count.

    No run is older than the repository, so a line before the day it was created
    leaves nothing to walk: the mark is the line itself, and no page of runs is
    read. Otherwise the oldest day with a run is found by halving the days from
    that one to the line, one count of the runs created on or before a day a
    step - about 9 for a year of days - and the mark is the day before it. With
    no run on or before the line, the mark is the line.

    A count of the whole collection could not do this: it says how many runs
    there are, and nothing of the day the oldest one was made.
    """
    created = _created_on(api)
    last = date.fromisoformat(line)
    if last < created:
        return line
    low, high = created, last + timedelta(days=1)
    while low < high:
        middle = low + timedelta(days=(high - low).days // 2)
        if _runs_on_or_before(api, middle.isoformat()) > 0:
            high = middle
        else:
            low = middle + timedelta(days=1)
    return (low - timedelta(days=1)).isoformat()


def first_artifacts_mark(api: Api, *, line: str) -> str:
    """The UTC day a first walk of the artifacts starts after, read from the repository's own day.

    No artifact is older than the repository, so every one was created after
    the day before it was made, and a walk from the last page reaches the oldest
    by itself - no halving is needed. A line before that day leaves nothing to
    walk: the mark is the line, and no page is read.
    """
    return min((_created_on(api) - timedelta(days=1)).isoformat(), line)


def _day_of(created_at: str) -> str:
    """The `YYYY-MM-DD` an API timestamp falls on, read off its own text.

    `2026-09-17T06:23:11Z` is sliced rather than parsed: the window compares
    days as text, so turning this into a `datetime` and back would only add a
    way for the two to disagree about a boundary.
    """
    return created_at[:10]


def _created_at(raw: dict[str, Any]) -> str:
    """The instant GitHub says a member was created, as its own `Z` text, which sorts as time."""
    return str(raw["created_at"])


class _ArtifactWalk:
    """GitHub's artifacts from the oldest end, one page at a time, each page checked before use.

    GitHub lists the artifacts by id, newest first, and a delete moves every
    later artifact up one place. So the first page is read only for its count,
    which names the last page, and the walk reads from the last page back: a
    delete then moves only artifacts already read. The first page is handed on
    last, as it was read.

    **The order it checks is by UTC day, the order the walk relies on.** An
    artifact's id and the instant it was created disagree by up to an hour - 76
    minutes among the 1,613 listed on 2026-10-05 - so each page is sorted by that
    instant, and the oldest day on each page must be at or after the newest day
    on every page read before it. The next page is read and checked before any
    member of the page in hand reaches the pass, so a pass that ends inside a
    page never ends past a boundary nobody checked.

    **A failed check costs completeness, never safety**, because the pass still
    holds every member to the window. When the order breaks, the walk hands on
    every page, still from the last back, and no longer stops at the line. When
    a page's count is not the first page's less what this walk deleted, an
    artifact may have moved onto a page already read. Either way the walk is no
    longer intact, and the pass keeps its mark. One walk serves one pass.
    """

    def __init__(self, api: Api, *, through: str) -> None:
        self._api = api
        self._through = through
        self._deleted = 0
        self._in_order = True
        self._counted = True

    def intact(self) -> bool:
        """Whether every page read so far kept day order and the count the first page set."""
        return self._in_order and self._counted

    def members(self) -> Iterator[dict[str, Any]]:
        """Every artifact the walk reaches, oldest first, up to the first created after the line."""
        pages = self._checked_pages()
        held = next(pages, [])
        while True:
            after = next(pages, None)
            for raw in held:
                if self._in_order and _day_of(_created_at(raw)) > self._through:
                    return
                yield raw
            if after is None:
                return
            held = after

    def delete(self, raw: dict[str, Any]) -> None:
        """One DELETE, counted, so a page read after it is held to the count it left."""
        self._api.remove(f"actions/artifacts/{raw['id']}")
        self._deleted += 1

    def _checked_pages(self) -> Iterator[list[dict[str, Any]]]:
        """Each page from the last to the first, oldest member first, checked as it is read."""
        route, key = _ROUTES[PrunableCollection.WORKFLOW_ARTIFACTS]
        first = self._api.read(_page(route, 1))
        newest: str | None = None
        for page in range(_last_page(first), 0, -1):
            answer = first if page == 1 else self._api.read(_page(route, page))
            if page > 1:
                self._check_count(page, counted=_count(answer), first=_count(first))
            members = sorted(answer.get(key, []), key=_created_at)
            if members:
                self._check_order(page, oldest=_day_of(_created_at(members[0])), before=newest)
                latest = _day_of(_created_at(members[-1]))
                newest = latest if newest is None else max(newest, latest)
            yield members

    def _check_count(self, page: int, *, counted: int, first: int) -> None:
        """A page counted other than the first page less this walk's deletes is not intact."""
        expected = first - self._deleted
        if counted == expected or not self._counted:
            return
        self._counted = False
        logger.warning(
            "%s: page %d counted %d artifacts where the first page less %d deleted leaves %d, "
            "so one may have moved onto a page already read, and the mark stays where it was",
            PrunableCollection.WORKFLOW_ARTIFACTS.value,
            page,
            counted,
            self._deleted,
            expected,
        )

    def _check_order(self, page: int, *, oldest: str, before: str | None) -> None:
        """A page whose oldest day comes before a day on a page read before it breaks the order."""
        if before is None or oldest >= before or not self._in_order:
            return
        self._in_order = False
        logger.warning(
            "%s: page %d holds an artifact from a day before one on a page read before it, so "
            "the order check failed: every page is read, and the mark stays where it was",
            PrunableCollection.WORKFLOW_ARTIFACTS.value,
            page,
        )


def artifacts(api: Api, *, through: str) -> Collection[dict[str, Any]]:
    """The files jobs uploaded, oldest first, up to the first one created after `through`.

    94 percent of our bytes sit here. Read from the oldest end and checked page
    by page, as `_ArtifactWalk` says. An expired artifact is listed with its
    real day like any other, so an age window takes it: GitHub has reclaimed
    its bytes, but its record still fills a place on a page.
    """
    walk = _ArtifactWalk(api, through=through)
    return Collection(
        name=PrunableCollection.WORKFLOW_ARTIFACTS.value,
        listing=walk.members,
        describe=lambda raw: Member(
            id=str(raw["id"]),
            day=_day_of(raw["created_at"]),
            size_bytes=int(raw.get("size_in_bytes", 0)),
            label=str(raw.get("name", "")),
        ),
        delete=walk.delete,
        listing_intact=walk.intact,
    )


def runs(api: Api, *, after: str, through: str) -> Collection[dict[str, Any]]:
    """Whole workflow runs and their logs, created after one UTC day and up to another.

    Listed one UTC day at a time, oldest day first, which is the order a walk
    from a mark needs: every run of a day is listed before any run of the next.
    Each search is read from its last page back, so deleting a run never moves
    one the pass has not read yet.

    `size_bytes` is 0 for every one of them, and that is the honest number: the
    API publishes no size for a run's logs, and the only way to learn one is to
    download the log archive - which costs more bandwidth than the deletion
    saves. A pass over this collection reports what it deleted and says nothing
    about bytes, rather than inventing a figure (Guardrail #10).
    """
    return Collection(
        name=PrunableCollection.WORKFLOW_RUNS.value,
        listing=lambda: _runs_created(api, after, through),
        describe=lambda raw: Member(
            id=str(raw["id"]),
            day=_day_of(raw["created_at"]),
            size_bytes=0,
            label=str(raw.get("name", "")),
        ),
        delete=lambda raw: api.remove(f"actions/runs/{raw['id']}"),
    )
