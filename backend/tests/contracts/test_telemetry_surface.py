"""Did every public name survive `telemetry.py` becoming `telemetry/`?

The split moved 1,267 lines into six modules and one re-exporting `__init__.py`.
Nothing outside the package was meant to change, and 40 modules reach these
names through `from idhazh import telemetry`, so the question worth a test is
narrow: is every name that was reachable before reachable now, and is it the
same object rather than a copy?

**What this cannot settle: whether the seam is in the right place.** It would
pass just as green with all 37 names left in one file, and it would pass with
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


def test_every_public_name_survives_the_split() -> None:
    """The one oracle this row turns on: no caller outside the package broke."""
    missing = sorted(name for name in BEFORE_THE_SPLIT if not hasattr(telemetry, name))
    assert missing == [], f"the package no longer exports {missing}"

    exported = list(telemetry.__all__)
    assert len(exported) == len(set(exported)), "__all__ names something twice"
    assert set(exported) == BEFORE_THE_SPLIT, (
        "__all__ and the pre-split surface disagree; a name added here is a new "
        "public name and a name dropped is a break"
    )

    for name in sorted(BEFORE_THE_SPLIT):
        exposed = getattr(telemetry, name)
        assert any(getattr(module, name, None) is exposed for module in MODULES), (
            f"telemetry.{name} is a copy: no module in the package holds that object"
        )


def test_the_flat_module_left_no_shim_behind() -> None:
    """A module beside the package that replaced it is dead code Python never loads.

    Plan 32 section 1a: the row that moves a thing deletes it in the same
    commit. `telemetry.py` sitting next to `telemetry/` would import as nothing,
    read as a fallback, and drift from the package for as long as it survived.
    """
    assert not (REPO_ROOT / "backend" / "idhazh" / "telemetry.py").exists()
