"""Which public names does `idhazh.telemetry` still re-export, and are they the same objects?

The split moved 1,267 lines into six modules and one re-exporting `__init__.py`.
Nothing outside the package was meant to change, and 40 modules reach these
names through `from idhazh import telemetry`, so the question worth a test is
narrow: is every name a caller outside the package still reaches reachable, and
is it the same object rather than a copy?

Seven of the original 37 are gone, and that is the other half of the question.
Four of them nobody outside the package ever reached, so the split cut them. One
is `record`, which a submodule of the same name now takes. Two went with the
hosted span sink on 2026-09-22 and are deleted rather than cut. This file is
where all three kinds are recorded.

**What this cannot settle: whether the seam is in the right place.** It would
pass just as green with all 31 names left in one file, and it would pass with
them scattered across thirty. Where each name belongs is a reading of
`docs/concepts/telemetry.md`, and a reviewer decides it.
"""

from __future__ import annotations

from pathlib import Path
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
#: `telemetry/record.py` owns one item's row, and Python binds a submodule onto
#: its package as an attribute - so a function re-exported under
#: the same name means `telemetry.record` is the function until something
#: imports the module and the module afterwards. That is not a name, it is an
#: import-order bug waiting for a caller. The attribute scan behind
#: `BEFORE_THE_SPLIT` found no caller outside the package using it, and the
#: function is still `telemetry.events.record` where it has always been defined.
TAKEN_BY_A_MODULE: Final[frozenset[str]] = frozenset({"record"})

#: The four names the split stopped re-exporting. An attribute scan of
#: every `.py` under `backend/` found no `telemetry.<name>` and no
#: `from idhazh.telemetry import <name>` for any of them outside the package, so
#: each alias named a thing only the package's own modules use (Guardrail #6).
#: Every one of them still lives in the module that owns it, which is what the
#: second half of the oracle below holds. A fifth, `refuse_text`, was here until
#: the hosted sink went and is now in `DELETED_WITH_THE_HOSTED_SINK`.
CUT_AS_UNREACHED_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "AttrValue",
        "DEGRADED_BUT_DONE",
        "FLAT_RECORDS",
        "INSTRUMENT_CELLS",
    }
)

#: The two names the hosted span sink took with it on 2026-09-22. `langfuse_sink`
#: built it and `refuse_text` was the client's own mask hook wired shut; neither
#: had any other caller, so both are DELETED rather than un-exported. That is the
#: difference this set records: a cut alias must still exist in its module, and
#: one of these must exist nowhere (Guardrail #1 - a build-time producer makes no
#: runtime call to a third party, `docs/concepts/telemetry.md`).
DELETED_WITH_THE_HOSTED_SINK: Final[frozenset[str]] = frozenset({"langfuse_sink", "refuse_text"})

#: Names added since the split, each with the row that added it and the caller
#: that needs it. A public name is a promise, so one arrives here deliberately
#: rather than by being noticed failing this test.
#:
#: `census_row` arrived with the persisted census row. `stages.record` and
#: `stages.assemble` both
#: build the day's census row, and both reach it as `telemetry.census_row` -
#: which is how they already reached `classify_item`, the function it now wraps.
ADDED_AFTER_THE_SPLIT: Final[frozenset[str]] = frozenset({"census_row"})

#: What the package re-exports today: the pre-split surface, less the four the
#: split cut as unreached, the one a submodule took and the two the hosted sink
#: took, plus what later rows added.
RE_EXPORTED: Final[frozenset[str]] = (
    BEFORE_THE_SPLIT
    - CUT_AS_UNREACHED_ALIASES
    - TAKEN_BY_A_MODULE
    - DELETED_WITH_THE_HOSTED_SINK
    | ADDED_AFTER_THE_SPLIT
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

    Each of the four is still defined, still imported by the modules that use it,
    and simply no longer reachable as `telemetry.<name>`.
    """
    for name in sorted(CUT_AS_UNREACHED_ALIASES):
        assert not hasattr(telemetry, name), (
            f"telemetry.{name} is still re-exported; the cut did not happen"
        )
        assert any(hasattr(module, name) for module in MODULES), (
            f"{name} was deleted rather than un-exported"
        )


def test_the_hosted_sink_left_nothing_of_itself_behind() -> None:
    """The counterpart: these two had to be deleted, not merely un-exported.

    An un-exported `langfuse_sink` still sitting in `sinks.py` would still import
    the client the day somebody called it, which is the runtime call to a third
    party Guardrail #1 refuses. So the absence is asserted in the module as well
    as on the package, and the module source is read so a name reintroduced under
    a different binding is still caught.
    """
    for name in sorted(DELETED_WITH_THE_HOSTED_SINK):
        assert not hasattr(telemetry, name), f"telemetry.{name} is back"
        for module in MODULES:
            assert not hasattr(module, name), f"{module.__name__}.{name} is back"
    source = Path(sinks.__file__).read_text(encoding="utf-8")
    assert "langfuse" not in source.lower(), "the hosted sink is back in sinks.py"


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
