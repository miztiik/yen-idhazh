"""Is every ledger a console panel asks the browser's query door for one the site publishes?

A panel names a ledger when it calls `slice()` or `ledgerReach()` from
`frontend/src/lib/data/ledger.ts`, and the browser then fetches that ledger's
indexes from the published site. The site holds only the ledgers
`ledger.published` in `config/idhazh.json` names, so a panel naming any other
ledger fetches an address that answers 404. This test reads every caller of the
door under `frontend/src/` and holds each ledger it names to that list.

It reads the calls as text, so a call it cannot read is refused by name rather
than skipped: a ledger passed through a variable, a door loaded with `import()`,
or the door re-exported from another module would each hide a ledger from it.
The door's own modules under `frontend/src/lib/data/` pass a ledger through, and
are not callers. The written-question page may name unpublished ledgers and then
answer `missing`, so only panel calls are held to the published list.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
from _source_files import source_files
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.app_config import AppConfig

pytestmark = pytest.mark.contract

SOURCE: Final[Path] = REPO_ROOT / "frontend" / "src"
DOOR: Final[Path] = SOURCE / "lib" / "data" / "ledger.ts"
#: The door's own modules. They pass a ledger through rather than name one.
DOOR_DIRECTORY: Final[Path] = SOURCE / "lib" / "data"

#: The two calls a panel names a ledger in.
DOOR_CALLS: Final = ("slice", "ledgerReach")
#: What a specifier that reaches the door ends in, through `$lib` or a relative path.
DOOR_SPECIFIER: Final = re.compile(r"(?:^|/)data/ledger(?:\.ts|\.js)?$")

NAMED_IMPORT: Final = re.compile(r"\bimport\s+(type\s+)?\{([^}]*)\}\s*from\s*['\"]([^'\"]+)['\"]")
NAMESPACE_IMPORT: Final = re.compile(r"\bimport\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from\s*['\"]([^'\"]+)['\"]")
DYNAMIC_IMPORT: Final = re.compile(r"\bimport\(\s*['\"]([^'\"]+)['\"]\s*\)")
RE_EXPORT: Final = re.compile(r"\bexport\s+(?:type\s+)?(?:\*|\{[^}]*\})\s*from\s*['\"]([^'\"]+)['\"]")
#: A block or JSDoc comment, an HTML comment, or a line that is only a comment.
COMMENT: Final = re.compile(r"/\*.*?\*/|<!--.*?-->|^\s*//[^\n]*", re.DOTALL | re.MULTILINE)
#: The first argument of a call, when it is a string literal and nothing else.
LITERAL_LEDGER: Final = re.compile(r"\s*(?:'([^'\\\n]*)'|\"([^\"\\\n]*)\"|`([^`$\\]*)`)\s*[,)]")


def door_calls(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Every `(call, ledger)` one source names through the door, and what it could not read."""
    text = COMMENT.sub("", text)
    callers: dict[str, str] = {}
    problems: list[str] = []
    for match in NAMED_IMPORT.finditer(text):
        if match[1] or not DOOR_SPECIFIER.search(match[3]):
            continue
        for binding in match[2].split(","):
            words = binding.split()
            if not words or words[0] == "type":
                continue
            if words[0] in DOOR_CALLS:
                callers[words[-1]] = words[0]
    patterns = [(re.compile(rf"(?<![\w$.]){re.escape(local)}\s*\("), call) for local, call in callers.items()]
    for match in NAMESPACE_IMPORT.finditer(text):
        if DOOR_SPECIFIER.search(match[2]):
            for call in DOOR_CALLS:
                member = rf"(?<![\w$.]){re.escape(match[1])}\s*\.\s*{call}\s*\("
                patterns.append((re.compile(member), call))
    for match in DYNAMIC_IMPORT.finditer(text):
        if DOOR_SPECIFIER.search(match[1]):
            problems.append("loads the door with import(); import it statically, so its calls can be read")
    for match in RE_EXPORT.finditer(text):
        if DOOR_SPECIFIER.search(match[1]):
            problems.append("re-exports the door; a caller imports ledger.ts itself, so its calls can be read")
    calls: list[tuple[str, str]] = []
    for pattern, call in patterns:
        for found in pattern.finditer(text):
            named = LITERAL_LEDGER.match(text, found.end())
            if named is None:
                problems.append(f"names the ledger of a {call}() call through an expression; name it as a literal")
                continue
            calls.append((call, next(group for group in named.groups() if group is not None)))
    return calls, problems


def callers_under(root: Path) -> dict[str, tuple[list[tuple[str, str]], list[str]]]:
    """Every source file under `root` that names a ledger through the door, or tried to."""
    found: dict[str, tuple[list[tuple[str, str]], list[str]]] = {}
    for path in source_files(
        roots=(root,),
        suffixes=(".ts", ".js", ".mjs", ".svelte"),
    ):
        if DOOR_DIRECTORY in path.parents:
            continue
        calls, problems = door_calls(read_text(path))
        if calls or problems:
            found[path.relative_to(REPO_ROOT).as_posix()] = (calls, problems)
    return found


def unpublished(calls: list[tuple[str, str]], published: set[str]) -> list[str]:
    """Each call that names a ledger the site does not publish."""
    return [f"{call}('{ledger}')" for call, ledger in calls if ledger not in published]


def published_ledgers() -> set[str]:
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    return {ledger.value for ledger in committed.ledger.published}


def test_every_ledger_a_panel_asks_the_door_for_is_published() -> None:
    published = published_ledgers()
    faults = [
        f"{where}: {fault}"
        for where, (calls, problems) in callers_under(SOURCE).items()
        for fault in [*problems, *unpublished(calls, published)]
    ]
    assert faults == [], (
        "a console panel asks the query door for a ledger the site does not publish, or "
        "names it where this test cannot read it. Add the ledger to ledger.published in "
        f"config/idhazh.json (published now: {sorted(published)}), or change the call:\n"
        + "\n".join(faults)
    )


def test_the_door_still_exports_the_two_calls_this_test_reads() -> None:
    """A renamed call would leave the walk above reading nothing and passing."""
    door = read_text(DOOR)
    for call in DOOR_CALLS:
        assert re.search(rf"export (?:async )?function {call}\(", door), (
            f"{DOOR.name} no longer exports {call}(); rename DOOR_CALLS here with it"
        )


def test_a_call_naming_a_ledger_the_site_does_not_publish_is_found() -> None:
    """The walk above finds no call today, so this is the case that proves it can fail."""
    panel = """
<script lang="ts">
    import { ledgerReach as reachOf, slice, type LedgerName } from '$lib/data/ledger';
    const reach = reachOf("summary-quality-evals");
    const rows = slice('feed-health', { columns: ['date'], from: '2026-09-01', to: '2026-09-30' });
    const cut = [1, 2, 3].slice(0, 2);
</script>
{#await slice(`item-health`, { columns: ['date'], from, to }) then result}{/await}
"""
    calls, problems = door_calls(panel)
    assert problems == []
    assert sorted(calls) == [
        ("ledgerReach", "summary-quality-evals"),
        ("slice", "feed-health"),
        ("slice", "item-health"),
    ]
    assert unpublished(calls, published_ledgers()) == ["slice('feed-health')"]


def test_a_call_this_test_cannot_read_is_refused_by_name() -> None:
    reader = """
import * as door from '../../lib/data/ledger';
import { slice } from '$lib/data/ledger.ts';
export { ledgerReach } from '$lib/data/ledger';
const ledger = 'summary-quality-evals';
door.slice('host-fingerprint', { columns: ['date'], from, to });
slice(ledger, { columns: ['date'], from, to });
const later = await import('$lib/data/ledger');
"""
    calls, problems = door_calls(reader)
    assert calls == [("slice", "host-fingerprint")]
    assert sorted(problems) == [
        "loads the door with import(); import it statically, so its calls can be read",
        "names the ledger of a slice() call through an expression; name it as a literal",
        "re-exports the door; a caller imports ledger.ts itself, so its calls can be read",
    ]
