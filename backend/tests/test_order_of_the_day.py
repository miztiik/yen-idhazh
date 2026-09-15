"""The page that says why one story is above another, checked against the code.

`docs/concepts/placement.md` prints a worked example and a table of every term
of the selection score with the config address its number comes from. A page
that only asserts its own prose proves nothing: the first time a default moves
or a term is added, the page is wrong and nothing says so.

So this module reads the page and drives the real code over
`tests/fixtures/rank/worked-example.json`. If `rank.score` returns anything but
the totals the page prints, or `config/` holds anything but the values it
quotes, this fails and names the disagreement.

The fixture is BUILT rather than sampled from a committed day. It has to fire
every term of the score at once, which no real day guarantees, and reading the
archive would make this test cost more every week (`CLAUDE.md` Guardrail #12).
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from conftest import FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import rank
from idhazh.config import load
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.item_health import TimeSource
from idhazh.contracts.sources import FeedDef, SourceForm
from idhazh.contracts.taxonomy import LensDef, SourceTier
from idhazh.discover import Candidate

PAGE: Final = REPO_ROOT / "docs" / "concepts" / "placement.md"
WORKED_EXAMPLE: Final = FIXTURES_DIR / "rank" / "worked-example.json"

#: A whole table cell that is nothing but a dotted lowercase identifier. It is
#: deliberately narrow: `CLAUDE.md`, `config/idhazh.json`, `FeedDef.weight` and
#: `idhazh.config.load()` all appear on the page and none of them is a config
#: address a run reads a value out of.
ADDRESS: Final = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


def _tables(text: str) -> list[list[list[str]]]:
    """Every markdown table on the page, as rows of stripped cells.

    Fenced blocks are skipped so the mermaid diagram cannot be read as data.
    """
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(set(cell) <= set("-: ") for cell in cells):
                current.append(cells)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _number(cell: str) -> float | None:
    try:
        return float(cell.strip().strip("*`"))
    except ValueError:
        return None


def _resolve(app: AppConfig, address: str) -> tuple[bool, Any]:
    """Walk a dotted address from `AppConfig`. Says whether it is one at all."""
    head, *rest = address.split(".")
    if head not in type(app).model_fields:
        return False, None
    node: Any = app
    for part in (head, *rest):
        assert hasattr(node, part), (
            f"{PAGE.name} prints the address `{address}`, and `{part}` is not a field of "
            f"{type(node).__name__}. Either the page is stale or the key was renamed."
        )
        node = getattr(node, part)
    return True, node


def _stories() -> list[dict[str, Any]]:
    spec = json.loads(read_text(WORKED_EXAMPLE))
    return list(spec["stories"])


def _now() -> str:
    return str(json.loads(read_text(WORKED_EXAMPLE))["now"])


def _carriers(story: dict[str, Any]) -> list[Candidate]:
    return [
        Candidate(
            canonical_url=carrier["canonical_url"],
            source_url=carrier["canonical_url"],
            url_key=derive_url_key(carrier["canonical_url"]),
            source_id=carrier["source_id"],
            vertical=story["vertical"],
            tier=SourceTier[str(carrier["tier"]).upper()],
            source_form=SourceForm.ARTICLE,
            title=story["name"],
            published_at=story["appeared"],
            weight=carrier["weight"],
        )
        for carrier in story["carriers"]
    ]


def scored() -> list[tuple[str, rank.Ranked]]:
    """Every story in the fixture, named, and scored by the code the pipeline runs."""
    collect = load().app.collect
    now = _now()
    out: list[tuple[str, rank.Ranked]] = []
    for story in _stories():
        carried = _carriers(story)
        reliability = story["reliability"] or None
        terms = rank.score_terms(
            carried,
            config=collect,
            watchlist_hit=story["watchlist_hit"],
            lens_bonus=story["lens_bonus"],
            appeared=story["appeared"],
            now=now,
            reliability=reliability,
        )
        out.append(
            (
                str(story["name"]),
                rank.Ranked(
                    score=terms.total,
                    terms=terms,
                    candidate=carried[0],
                    appeared_at=story["appeared"],
                    time_source=TimeSource.FEED,
                    carried_by=len(carried),
                    watchlist_hit=story["watchlist_hit"],
                    on_front_page=False,
                    lens_bonus=story["lens_bonus"],
                ),
            )
        )
    return out


def printed_example() -> list[tuple[str, float]]:
    """The worked example the page prints, in the order it prints it."""
    for table in _tables(read_text(PAGE)):
        header = [cell.lower() for cell in table[0]]
        if header[0] == "story" and header[-1] == "score":
            rows = []
            for row in table[1:]:
                total = _number(row[-1])
                assert total is not None, f"the worked example's last cell is not a number: {row}"
                rows.append((row[0], total))
            return rows
    raise AssertionError(
        f"{PAGE.name} carries no worked-example table. It is the only thing on that page "
        "that can disagree with the code, so its absence is the failure."
    )


def test_every_config_address_the_page_prints_resolves_and_still_holds_that_value() -> None:
    """A knob quoted on the page is a knob a reader will act on."""
    app = load().app
    checked = 0
    for table in _tables(read_text(PAGE)):
        for row in table[1:]:
            addresses = [
                (index, cell.strip("`"))
                for index, cell in enumerate(row)
                if ADDRESS.match(cell.strip("`"))
            ]
            for index, address in addresses:
                is_config, value = _resolve(app, address)
                if not is_config:
                    continue
                printed = next(
                    (
                        number
                        for position, cell in enumerate(row)
                        if position != index and (number := _number(cell)) is not None
                    ),
                    None,
                )
                if printed is None:
                    continue
                assert printed == value, (
                    f"{PAGE.name} says `{address}` is {printed}; config/ says {value}. "
                    "Correct the page, or the knob."
                )
                checked += 1
    assert checked >= 12, (
        f"only {checked} config addresses were checked against config/. The page's term table "
        "was renamed, reformatted or removed, so this test stopped reading it and passed anyway."
    )


def test_the_terms_that_are_not_one_number_still_exist_where_the_page_says() -> None:
    """`FeedDef.weight` and `LensDef.weight` are per-feed and per-lens, so they
    carry no single value the test above could compare. A rename would still
    make the page wrong."""
    assert "weight" in FeedDef.model_fields, "config/sources.json no longer weights a feed"
    assert "weight" in LensDef.model_fields, "config/taxonomy.json no longer weights a lens"
    heaviest = max(lens.weight for lens in load().taxonomy.lenses)
    assert heaviest == 0.3, (
        f"the page says the heaviest lens weight is 0.3; config/taxonomy.json says {heaviest}"
    )


def test_the_worked_example_reproduces_what_rank_scores() -> None:
    """The check the page exists to survive: prose against arithmetic."""
    by_name = {name: ranked.score for name, ranked in scored()}
    printed = printed_example()
    assert sorted(name for name, _ in printed) == sorted(by_name), (
        "the page and the fixture disagree about which stories the example holds"
    )
    for name, total in printed:
        assert total == by_name[name], (
            f"{PAGE.name} prints {total} for '{name}'; rank.score returns {by_name[name]}."
        )


def test_the_worked_example_prints_the_order_the_code_produces() -> None:
    """The page's claim is an ORDER, not a set of numbers."""
    pairs = scored()
    named = {ranked.candidate.canonical_url: name for name, ranked in pairs}
    assert len(named) == len(pairs), "two stories in the fixture share one address"
    expected = [named[ranked.candidate.canonical_url] for ranked in rank._ordered([r for _, r in pairs])]
    assert [name for name, _ in printed_example()] == expected
