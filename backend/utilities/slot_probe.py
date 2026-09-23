"""Does the pinned llama-server answer for the three slot columns, and with which fields?

`slot_id`, `kv_tokens_at_start` and `prefix_shared_with_previous` are declared
on `ItemHealthRow` and no module writes them. Nobody had asked the server
whether it could supply them, so a column declared against an unchecked source
sat in the contract for weeks. This asks, and prints the build it asked plus
the exact field names that came back, so a later reader retakes the answer
rather than trusts it (Guardrail #10).

**Not a test.** It needs a server on the other end of a socket, and no test
touches the network (`CLAUDE.md` Guardrail #7, section 13). The parsing half is
pure and `backend/tests/test_slot_probe.py` drives it from built payloads.

Run it beside a server a run already started, from the repository root:

    LLAMA_PORT=8080 python backend/utilities/slot_probe.py --repeats 3

**It prints field names and whole numbers, never field values.** `/slots`
carries the slot's own prompt back when `LLAMA_SERVER_SLOTS_DEBUG` is set, and
that prompt is an article somebody else wrote, so nothing here reads a value
out of a slot (Guardrail #11).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

from idhazh import config
from idhazh.llm.server import resolve_endpoint

#: The route that lists what each prefix-cache slot is holding.
SLOTS_PATH: Final = "/slots"

#: The route the summarizer itself posts to. Its answer is the one that matters:
#: a field only `/slots` carries costs an extra request per item, and a field
#: the completion already returns costs nothing at all.
COMPLETION_PATH: Final = "/completions"

#: What the server says about itself, including whether `/slots` is switched on.
PROPS_PATH: Final = "/props"

#: The three columns `ItemHealthRow` declares and nothing writes.
SLOT_COLUMNS: Final = ("slot_id", "kv_tokens_at_start", "prefix_shared_with_previous")

#: Which field would fill each column, cheapest first. Every name here is
#: llama.cpp's own, so it is pinned by `LLAMA_CPP_BUILD` and by nothing in
#: `config/` - no value an operator can set moves it, and a build that renames
#: one is exactly what this script exists to catch (Guardrail #6).
FILLED_BY: Final[dict[str, tuple[str, ...]]] = {
    "slot_id": ("completion:id_slot", "slots:id"),
    "kv_tokens_at_start": ("completion:tokens_cached", "slots:n_prompt_tokens"),
    "prefix_shared_with_previous": (
        "completion:timings.cache_n",
        "slots:n_prompt_tokens_cache",
    ),
}

#: Two prompts that share a prefix, so the second call can only be answered
#: from the slot. Our own bytes, written here - a probe that read a prompt from
#: anywhere else would be sending fetched text (Guardrail #11).
FIRST_PROMPT: Final = "Count slowly: one, two, three,"
SECOND_PROMPT: Final = FIRST_PROMPT + " four, five, six,"


def route(endpoint: str, path: str) -> str:
    """Another route on the server an endpoint names.

    Derived rather than configured, so a probe pointed at one port cannot ask
    one server about its slots and another for a completion.
    """
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def slot_fields(payload: object) -> list[str]:
    """Every field name `/slots` returned, across all slots, sorted.

    The union rather than the first slot's keys. A slot that has never held a
    task answers with four fields and a slot that has held one answers with
    ten, so reading only the first slot would report the short shape on a
    server that has the long one.
    """
    if not isinstance(payload, list):
        raise ValueError("/slots must answer with a list of slots")
    names: set[str] = set()
    for slot in payload:
        if not isinstance(slot, dict):
            raise ValueError("/slots must answer with a list of slots")
        names.update(str(name) for name in slot)
    return sorted(names)


def completion_fields(payload: object) -> list[str]:
    """Every field name a completion returned, with `timings` flattened one level.

    `timings.cache_n` is the field that says how much of this prompt the slot
    already held, so it has to be reachable by name rather than hidden inside
    an object the caller would have to know to open.
    """
    if not isinstance(payload, dict):
        raise ValueError("a completion must answer with an object")
    names: set[str] = set()
    for name, value in payload.items():
        names.add(str(name))
        if name == "timings" and isinstance(value, dict):
            names.update(f"timings.{inner}" for inner in value)
    return sorted(names)


def answered_by(*, slots: Sequence[str], completion: Sequence[str]) -> dict[str, str | None]:
    """For each of the three columns, the field that would fill it, or `None`.

    `None` is the answer that retires a column: a column nothing can fill is a
    guess with a schema around it.
    """
    seen = {f"slots:{name}" for name in slots} | {f"completion:{name}" for name in completion}
    return {
        column: next((name for name in FILLED_BY[column] if name in seen), None)
        for column in SLOT_COLUMNS
    }


def readings(payload: object) -> dict[str, int]:
    """The numbers a completion carries about its slot, by the name it used.

    Only whole numbers, and only the three fields the columns need. A field the
    build does not send is absent rather than zero: zero is a real cache count
    and would read as a slot that reused nothing.
    """
    if not isinstance(payload, dict):
        raise ValueError("a completion must answer with an object")
    timings = payload.get("timings")
    found = {
        "id_slot": payload.get("id_slot"),
        "tokens_cached": payload.get("tokens_cached"),
        "timings.cache_n": timings.get("cache_n") if isinstance(timings, dict) else None,
    }
    return {name: value for name, value in found.items() if isinstance(value, int)}


def spread(values: Sequence[int]) -> str:
    """One reading's spread, in the form Guardrail #10 asks a number to carry."""
    if not values:
        return "not read"
    if min(values) == max(values):
        return f"{min(values)} on every call, n={len(values)}"
    return f"min {min(values)}, max {max(values)}, n={len(values)}"


def _get(url: str, *, timeout: float) -> Any:
    with request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(url: str, body: Mapping[str, Any], *, timeout: float) -> Any:
    outbound = request.Request(
        url,
        data=json.dumps(dict(body)).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(outbound, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _completion_body(prompt: str) -> dict[str, Any]:
    """The smallest request that still fills a slot and reports its timings."""
    return {
        "prompt": prompt,
        "n_predict": 4,
        "temperature": 0.0,
        "cache_prompt": True,
        "stream": False,
    }


def _describe_host() -> str:
    """The box, named without naming the person or the machine it belongs to."""
    return f"{platform.system()} {platform.machine()}, {os.cpu_count()} logical CPUs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        raise SystemExit("--repeats must be 1 or more")
    endpoint: str = args.endpoint or resolve_endpoint(
        config.load(args.config_root).app.model_server.base_url
    )

    print(f"taken {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} on {_describe_host()}")
    print(f"endpoint {endpoint}")

    try:
        props = _get(route(endpoint, PROPS_PATH), timeout=args.timeout)
    except (OSError, ValueError) as failure:
        print(f"no server answered /props: {failure}", file=sys.stderr)
        return 1
    if not isinstance(props, dict):
        print("/props did not answer with an object", file=sys.stderr)
        return 1
    print(f"build {props.get('build_info', 'unnamed')}")
    print(f"total_slots {props.get('total_slots', 'unnamed')}")
    print(f"endpoint_slots {props.get('endpoint_slots', 'unnamed')}")

    completion: list[str] = []
    taken: dict[str, list[int]] = {}
    url = route(args.endpoint, COMPLETION_PATH)
    for _ in range(args.repeats):
        _post(url, _completion_body(FIRST_PROMPT), timeout=args.timeout)
        answer = _post(url, _completion_body(SECOND_PROMPT), timeout=args.timeout)
        completion = completion_fields(answer)
        for name, value in readings(answer).items():
            taken.setdefault(name, []).append(value)
    print(f"{COMPLETION_PATH} fields: {', '.join(completion) or 'none'}")
    for name in ("id_slot", "tokens_cached", "timings.cache_n"):
        print(f"{name} on the second call: {spread(taken.get(name, []))}")

    # After the calls, never before. A slot that has held no task answers with
    # four fields and a slot that has held one answers with ten, so asking a
    # fresh server reports a shape that is only true until the first item.
    slots: list[str] = []
    try:
        slots = slot_fields(_get(route(args.endpoint, SLOTS_PATH), timeout=args.timeout))
    except error.HTTPError as refusal:
        print(f"/slots refused: HTTP {refusal.code}")
    except (OSError, ValueError) as failure:
        print(f"/slots unreadable: {failure}")
    print(f"/slots fields after one completion: {', '.join(slots) or 'none'}")

    for column, field in answered_by(slots=slots, completion=completion).items():
        print(f"{column}: {field or 'NOTHING ANSWERS IT'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
