"""What a host prints on page after page, counted so a template is caught early.

`extract.boilerplate_ratio` has always been able to say "most of this page is
lines the host prints elsewhere". Nothing ever told it what those lines were, so
it divided by an empty set and answered 0.0 on every page ever fetched. This
module is the missing half: the fold that counts a host's repeated lines, and
the set the extractor is handed on the next run.

**Only hashes leave this module.** A line is fetched text. It is reduced, hashed
and counted; the text itself never reaches a file, a log line or a name
(Guardrail #11), and a sha256 cannot carry an instruction.

**Assemble folds and `extract` reads.** Only assemble sees a whole day's items
at once, so only assemble can count how many DISTINCT pages a host served. A
work shard sees `index % shards` of the day, so eight shards each incrementing
one host's count would be eight partial answers racing into one file.

`docs/architecture/extraction/chrome.md` owns the rule; this is its arithmetic.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from idhazh.contracts.chrome_line import CHROME_LINE_RULE, ChromeLineRow

#: More than one space, after the reduction has left some behind.
_RUN_OF_SPACES = re.compile(r"\s+")
#: The subdomain a host uses for its public site and nothing else. Dropping it
#: is what makes `www.example.test` and `example.test` one template.
_WWW = re.compile(r"^www\.")


def host_of(url: str) -> str:
    """The host that served a page, lowercased, with no `www.`.

    Chrome belongs to the server, so this is the key. It is deliberately the
    whole host rather than the registrable domain: two newsrooms on one
    publisher's platform run two templates, and folding them would let one
    paper's furniture mark the other paper's articles as chrome.
    """
    return _WWW.sub("", (urlsplit(url).hostname or "").lower())


def reduce_line(line: str) -> str:
    """One line, reduced to what two printings of it have to share.

    Compatibility-normalised, whitespace collapsed, case-folded. The same three
    steps `assemble.story_key` applies to a headline, and for the same reason: a
    template that renders one non-breaking space differently on two pages is one
    template. `CHROME_LINE_RULE` names this, and a row carries that name so a
    later change ages its rows out instead of matching nothing.
    """
    folded = unicodedata.normalize("NFKC", line).casefold()
    return _RUN_OF_SPACES.sub(" ", folded).strip()


def hash_line(line: str) -> str:
    """The reduced line as a sha256, which is the only form that is ever stored."""
    return hashlib.sha256(reduce_line(line).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PageLines:
    """One page the day published, and the lines it printed."""

    host: str
    #: Hashes, already reduced. A page that printed a line twice counts once:
    #: the question is how many PAGES carried it.
    line_hashes: frozenset[str]


def page_lines(url: str, lines: Iterable[str]) -> PageLines:
    """One page's contribution, from its address and its body lines."""
    return PageLines(
        host=host_of(url),
        line_hashes=frozenset(hash_line(line) for line in lines if line.strip()),
    )


def fold(
    pages: Iterable[PageLines],
    *,
    known: Sequence[ChromeLineRow] = (),
    date: str,
    lines_per_host_max: int,
) -> list[ChromeLineRow]:
    """Today's pages added to what the store already holds, bounded per host.

    **The eviction order is load-bearing and it is not recency.** A host over
    its cap gives up the line seen on the FEWEST pages first, and the oldest
    `last_seen` breaks the tie. Recency alone would evict the chrome that the
    very articles being compared against it are printing - the store would run
    hottest exactly where it is least useful.

    A row whose `line_rule` is not the current one is dropped rather than
    counted on. Its hash means something else, so adding to it would be adding
    two different measurements together.
    """
    counts: dict[tuple[str, str], ChromeLineRow] = {
        (row.host, row.line_hash): row for row in known if row.line_rule == CHROME_LINE_RULE
    }
    for page in pages:
        if not page.host:
            continue
        for line_hash in page.line_hashes:
            held = counts.get((page.host, line_hash))
            counts[page.host, line_hash] = (
                ChromeLineRow(
                    version=ChromeLineRow.schema_version(),
                    host=page.host,
                    line_rule=CHROME_LINE_RULE,
                    line_hash=line_hash,
                    pages_seen=1,
                    first_seen=date,
                    last_seen=date,
                )
                if held is None
                else held.model_copy(
                    update={
                        "pages_seen": held.pages_seen + 1,
                        "last_seen": max(held.last_seen, date),
                    }
                )
            )

    by_host: dict[str, list[ChromeLineRow]] = {}
    for row in counts.values():
        by_host.setdefault(row.host, []).append(row)
    kept: list[ChromeLineRow] = []
    for host in sorted(by_host):
        # Most pages first, then most recently seen. The slice below keeps the
        # head, so what falls off the end is the line on the fewest pages and,
        # among those, the one nothing has printed for longest.
        rows = sorted(
            by_host[host], key=lambda row: (-row.pages_seen, _newest_first(row.last_seen))
        )
        kept.extend(rows[:lines_per_host_max])
    return kept


def _newest_first(date: str) -> str:
    """A date key that sorts newest first, so one `sorted` call carries both terms.

    A `YYYY-MM-DD` stamp sorts oldest first as a string, and the eviction order
    wants the opposite on this term while wanting ascending on the one beside
    it. Complementing each digit inverts the order without turning the key into
    a second sort or a number a reader has to decode.
    """
    return "".join(str(9 - int(char)) if char.isdigit() else char for char in date)


def chrome_for(rows: Iterable[ChromeLineRow], *, host: str, pages_min: int) -> set[str]:
    """The line hashes this host prints often enough to call chrome.

    Under `pages_min` a line is kept in the store and withheld from here: the
    count has to climb somehow, and two pages sharing a sentence is a wire story
    rather than a template. A row written under an older reduction is not this
    host's chrome either - its hash answers a different question.
    """
    return {
        row.line_hash
        for row in rows
        if row.host == host
        and row.line_rule == CHROME_LINE_RULE
        and row.pages_seen >= pages_min
    }


def by_host(rows: Iterable[ChromeLineRow], *, pages_min: int) -> Mapping[str, set[str]]:
    """Every host's chrome at once, for a stage that fetches many hosts in a loop."""
    found: dict[str, set[str]] = {}
    for row in rows:
        if row.line_rule != CHROME_LINE_RULE or row.pages_seen < pages_min:
            continue
        found.setdefault(row.host, set()).add(row.line_hash)
    return found
