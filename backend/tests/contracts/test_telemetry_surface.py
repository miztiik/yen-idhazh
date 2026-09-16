"""Which public names does `idhazh.telemetry` still re-export, and are they the same objects?

The split moved 1,267 lines into six modules and one re-exporting `__init__.py`.
Nothing outside the package was meant to change, and 40 modules reach these
names through `from idhazh import telemetry`, so the question worth a test is
narrow: is every name a caller outside the package still reaches reachable, and
is it the same object rather than a copy?

Six of the original 37 are gone, and that is the other half of the question.
Five of them nobody outside the package ever reached, so plan 32 row 10 cut
them. The sixth is `record`, which a submodule of the same name now takes (plan
32 row 4). This file is where both are recorded.

**What this cannot settle: whether the seam is in the right place.** It would
pass just as green with all 31 names left in one file, and it would pass with
them scattered across thirty. Where each name belongs is a reading of
`docs/concepts/telemetry.md`, and a reviewer decides it.
"""

from __future__ import annotations

from types import ModuleType
from typing import Final

import pytest
from conftest import REPO_ROOT

from idhazh import telemetry
from idhazh.telemetry import census, events, rollup, sinks, spans, traces

pytestmark = pytest.mark.contract

#: Every public name `backend/idhazh/telemetry.py` defined on the commit before
#: the split, read off that file's top-level classes, functions and assignments
#: with `ast` (`origin/main` at 6b46f1ed, 2026-09-15). It is frozen as a literal
#: because the thing it describes no longer exists: a list derived from today's
#: source would only ever agree with itself.
#:
#: The pre-split module also leaked 41 further names through `dir()` - `json`,
#: `re`, `Path`, `ItemHealthRow` and the rest of its import block. They are not
#: here because no caller ever reached one: an attribute scan of every `.py`
#: under `backend/` found `telemetry.<name>` used for these 37 and for nothing
#: else, so a flat module's import leakage was never a public surface.
BEFORE_THE_SPLIT: Final[frozenset[str]] = frozenset(
    {
        "AttrKey",
        "AttrValue",
        "CENSUS_CELLS",
        "CollectingSink",
        "DEGRADED_BUT_DONE",
        "ENVELOPE_VERSION",
        "EventLevel",
        "EventName",
        "FLAT_RECORDS",
        "FanOut",
        "FileSink",
        "INSTRUMENT_CELLS",
        "MAX_ATTRIBUTE_CHARS",
        "NullSink",
        "OpenSpan",
        "RECORD_CELLS",
        "Span",
        "SpanKind",
        "SpanName",
        "SpanSink",
        "TRACES_DIRNAME",
        "Tracer",
        "article_attributes",
        "attribute",
        "classify_item",
        "committed_trace_path",
        "committed_trace_relpath",
        "detail_cell",
        "event",
        "is_final",
        "item_attributes",
        "langfuse_sink",
        "record",
        "refuse_text",
        "roll_up_spans",
        "summary_attributes",
        "trace_date",
    }
)

MODULES: Final[tuple[ModuleType, ...]] = (census, events, rollup, sinks, spans, traces)

#: The one pre-split name the package cannot re-export, and why it cannot.
#: `telemetry/record.py` owns one item's row (plan 32 row 4), and Python binds a
#: submodule onto its package as an attribute - so a function re-exported under
#: the same name means `telemetry.record` is the function until something
#: imports the module and the module afterwards. That is not a name, it is an
#: import-order bug waiting for a caller. The attribute scan behind
#: `BEFORE_THE_SPLIT` found no caller outside the package using it, and the
#: function is still `telemetry.events.record` where it has always been defined.
TAKEN_BY_A_MODULE: Final[frozenset[str]] = frozenset({"record"})

#: The five names plan 32 row 10 stopped re-exporting. An attribute scan of
#: every `.py` under `backend/` found no `telemetry.<name>` and no
#: `from idhazh.telemetry import <name>` for any of them outside the package, so
#: each alias named a thing only the package's own modules use (Guardrail #6).
#: Every one of them still lives in the module that owns it, which is what the
#: second half of the oracle below holds.
CUT_BY_THE_DISPATCHER_ROW: Final[frozenset[str]] = frozenset(
    {
        "AttrValue",
        "DEGRADED_BUT_DONE",
        "FLAT_RECORDS",
        "INSTRUMENT_CELLS",
        "refuse_text",
    }
)

#: What the package re-exports today: the pre-split surface, less the five the
#: dispatcher row cut and the one a submodule took.
RE_EXPORTED: Final[frozenset[str]] = (
    BEFORE_THE_SPLIT - CUT_BY_THE_DISPATCHER_ROW - TAKEN_BY_A_MODULE
)


def test_every_public_name_with_a_caller_outside_the_package_survives() -> None:
    """The one oracle this row turns on: no caller outside the package broke."""
    missing = sorted(name for name in RE_EXPORTED if not hasattr(telemetry, name))
    assert missing == [], f"the package no longer exports {missing}"

    exported = list(telemetry.__all__)
    assert len(exported) == len(set(exported)), "__all__ names something twice"
    assert set(exported) == RE_EXPORTED, (
        "__all__ and the re-exported surface disagree; a name added here is a new "
        "public name and a name dropped is a break"
    )

    for name in sorted(RE_EXPORTED):
        exposed = getattr(telemetry, name)
        assert any(getattr(module, name, None) is exposed for module in MODULES), (
            f"telemetry.{name} is a copy: no module in the package holds that object"
        )


def test_the_name_a_module_took_is_the_module_and_the_function_is_one_import_away() -> None:
    """`telemetry.record` is the module. Two names for one word is what this refuses.

    The serializer keeps the name it was always defined under, so a caller that
    wants it names the module that owns it rather than the package.
    """
    from idhazh.telemetry import record

    assert isinstance(record, ModuleType)
    assert record.__name__ == "idhazh.telemetry.record"
    assert events.record.__module__ == "idhazh.telemetry.events"
    assert "record" not in telemetry.__all__


def test_a_cut_re_export_is_gone_from_the_package_and_not_from_its_module() -> None:
    """A removal that deleted the thing rather than the alias would be a break.

    Each of the five is still defined, still imported by the modules that use it,
    and simply no longer reachable as `telemetry.<name>`.
    """
    for name in sorted(CUT_BY_THE_DISPATCHER_ROW):
        assert not hasattr(telemetry, name), (
            f"telemetry.{name} is still re-exported; the cut did not happen"
        )
        assert any(hasattr(module, name) for module in MODULES), (
            f"{name} was deleted rather than un-exported"
        )


def test_the_flat_module_left_no_shim_behind() -> None:
    """A module beside the package that replaced it is dead code Python never loads.

    Plan 32 section 1a: the row that moves a thing deletes it in the same
    commit. `telemetry.py` sitting next to `telemetry/` would import as nothing,
    read as a fallback, and drift from the package for as long as it survived.
    The recorder and the ten publisher modules owe the same, and an
    `itemrecord.py` or a `publish_*.py` left at the top of `idhazh/` would read
    as the live one.
    """
    package = REPO_ROOT / "backend" / "idhazh"
    assert not (package / "telemetry.py").exists()
    assert not (package / "itemrecord.py").exists()
    assert sorted(path.name for path in package.glob("publish_*.py")) == []
    assert not (package / "source_health.py").exists()
