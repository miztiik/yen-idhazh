"""Which GitHub collections can a pass delete from, and how does it list, describe and delete one?

Two collections, both held by GitHub on our behalf and neither represented by
any file in this repository - so no other retention rule in this project can
reach them. Measured 2026-09-17 on `miztiik/yen-idhazh`: 612 live workflow
artifacts holding 1,063.2 MB, and 3,551 workflow runs each holding its own logs.

This module is the adapter and nothing else. It turns a page of REST JSON into
`one_at_a_time.Member` and a member id into one DELETE. The window, the ceiling,
the ordering and the resume point are all the core's, and none of them is
mentioned here.

**The transport is an injection point, so a test needs no network**
(Guardrail #7). `Api` is the whole surface the two builders below use, and the
default is `RestApi`. A test hands in a reader over a recorded page instead, the
way `idhazh.fetch` takes its connection class.

**Standard library HTTP, deliberately** (Guardrail #8). `idhazh.fetch` already
reads the open web with `urllib.request`, so the house pattern exists and this
adds no dependency for a utility an operator runs on demand. The beneficiary
`httpx` or `requests` would have is connection pooling across a few dozen
requests, which is worth nothing here: a pass does at most `ceiling` deletes and
each one is a round trip to a rate-limited API.

**The token comes from the environment and never reaches a log record**
(section 1b). It is read once, put in one header, and never returned, printed or
put in an error message.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any, Final, Protocol

from idhazh.contracts.knobs.prune import PrunableCollection
from idhazh.prune.one_at_a_time import Collection, Member

#: The environment variable the token arrives in. Actions sets it; an operator
#: running this by hand exports it. Named as a constant so the failure message
#: can say which variable without the value ever being near it.
TOKEN_ENV: Final = "GITHUB_TOKEN"

#: The variable Actions sets to `owner/name`. A run inside CI needs no `--repo`.
REPO_ENV: Final = "GITHUB_REPOSITORY"

API_ROOT: Final = "https://api.github.com"

#: The largest page the Actions API serves. One request a hundred members is the
#: difference between six requests and 612 for the artifact collection.
PAGE_SIZE: Final = 100

#: `owner/name`, and nothing that could steer a URL somewhere else. A repository
#: slug reaches this module from a command line or from CI, and it is
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
        """One GET, decoded. `path` is repository-relative, such as `actions/artifacts`."""

    def remove(self, path: str) -> None:
        """One DELETE. Returns when the member is gone."""


class RestApi:
    """`api.github.com`, over the standard library, with the token from the environment."""

    def __init__(self, repo: str, *, token: str | None = None) -> None:
        if not _REPO_PATTERN.fullmatch(repo):
            raise ValueError(
                f"--repo takes owner/name, not {repo!r}. It is interpolated into an "
                "API address, so it is checked as an identity rather than trusted"
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
        return f"{API_ROOT}/repos/{self._repo}/{path}"

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


def _pages(api: Api, route: str, key: str) -> Iterator[dict[str, Any]]:
    """Every member, one page at a time, holding one page at a time.

    Stops on a short page rather than on `total_count`, because the count is a
    fact about the moment the first page was read and a pass that is deleting is
    changing it. A short page is a fact about the page in hand.
    """
    page = 1
    while True:
        payload = api.read(f"{route}?per_page={PAGE_SIZE}&page={page}")
        members = payload.get(key, [])
        yield from members
        if len(members) < PAGE_SIZE:
            return
        page += 1


def _day_of(created_at: str) -> str:
    """The `YYYY-MM-DD` an API timestamp falls on, read off its own text.

    `2026-09-17T06:23:11Z` is sliced rather than parsed: the window compares
    days as text, so turning this into a `datetime` and back would only add a
    way for the two to disagree about a boundary.
    """
    return created_at[:10]


def artifacts(api: Api) -> Collection[dict[str, Any]]:
    """The files jobs uploaded, largest concern first: 94 percent of our bytes sit here.

    An expired artifact is skipped in `describe`'s day rather than filtered out
    of the listing, because GitHub has already reclaimed its bytes and deleting
    the record buys nothing - but it still occupies a row somebody pages through.
    It is listed with its real day, so an age window takes it like any other.
    """
    return Collection(
        name=PrunableCollection.WORKFLOW_ARTIFACTS.value,
        listing=lambda: _pages(api, *_ROUTES[PrunableCollection.WORKFLOW_ARTIFACTS]),
        describe=lambda raw: Member(
            id=str(raw["id"]),
            day=_day_of(raw["created_at"]),
            size_bytes=int(raw.get("size_in_bytes", 0)),
            label=str(raw.get("name", "")),
        ),
        delete=lambda raw: api.remove(f"actions/artifacts/{raw['id']}"),
    )


def runs(api: Api) -> Collection[dict[str, Any]]:
    """Whole workflow runs and the logs they hold.

    `size_bytes` is 0 for every one of them, and that is the honest number: the
    API publishes no size for a run's logs, and the only way to learn one is to
    download the log archive - which costs more bandwidth than the deletion
    saves. A pass over this collection reports what it deleted and says nothing
    about bytes, rather than inventing a figure (Guardrail #10).
    """
    return Collection(
        name=PrunableCollection.WORKFLOW_RUNS.value,
        listing=lambda: _pages(api, *_ROUTES[PrunableCollection.WORKFLOW_RUNS]),
        describe=lambda raw: Member(
            id=str(raw["id"]),
            day=_day_of(raw["created_at"]),
            size_bytes=0,
            label=str(raw.get("name", "")),
        ),
        delete=lambda raw: api.remove(f"actions/runs/{raw['id']}"),
    )


#: Which builder answers for which word. The one place the mapping is made, so
#: adding a collection is a route, a builder and a row here.
BUILDERS: Final = {
    PrunableCollection.WORKFLOW_ARTIFACTS: artifacts,
    PrunableCollection.WORKFLOW_RUNS: runs,
}


def collection_named(name: str, api: Api) -> Collection[dict[str, Any]]:
    """The collection this word names, already wired to a transport."""
    return BUILDERS[PrunableCollection(name)](api)
