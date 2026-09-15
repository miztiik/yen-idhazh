"""Measure what the docs cost a reader, and hand the numbers to the three tests.

This tool decides nothing. Every column it prints is an input to a test written
in `docs/reference/documentation-structure.md`, and no number here is a
threshold - the standard deliberately gives no page a maximum length, because a
line limit is met by starting a second file.

Run it with no arguments from the repository root:

    python backend/utilities/doc_load.py

Or name the pages a change touched, which is what CI does, so the numbers reach
the person reviewing the change rather than only the person who went looking:

    python backend/utilities/doc_load.py --changed docs/concepts/config.md
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

STANDARD = "docs/reference/documentation-structure.md"

#: Held before a line of code is read, because the harness injects them.
ALWAYS_LOADED = ("CLAUDE.md", "AGENTS.md")

#: The routing table sends you to one page, not one of each. The worst case is
#: the heaviest page it can send you to. A plan-doc is not on it: `TODO/` is
#: read when a task names a plan, never because an agent started work.
ROUTED_TO = ("docs/architecture", "docs/concepts", "docs/how-to")

#: A section a later one corrects reads like one of these. A hit is a candidate.
SUPERSEDED = re.compile(
    r"\b(superseded|retracted|withdrawn|corrected 20|was wrong"
    r"|until 20\d\d-\d\d|no longer (?:true|holds|applies))",
    re.I,
)

LINK = re.compile(r"\]\(([^)\s]+\.md)[)#]")


def tokens(text: str) -> int:
    """About four characters a token. A declared estimate, not a measurement."""
    return len(text) // 4


def sections(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    title: str | None = None
    body: list[str] = []
    fence = False
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            if title is not None:
                out.append((title, "\n".join(body)))
            title, body = line[3:].strip(), []
        elif title is not None:
            body.append(line)
    if title is not None:
        out.append((title, "\n".join(body)))
    return out


#: One page's row, in the order the table prints it. Tokens lead so that
#: sorting a list of these sorts heaviest first.
Row = tuple[int, str, int, int, int, int]

HEADINGS = f"  {'page':<52} {'~tok':>6} {'h2':>4} {'top h2':>7} {'from':>5} {'super':>6}"


def pages_under(root: Path) -> list[Path]:
    """Every page the standard governs, docs tree first and the roots after."""
    return sorted(root.glob("docs/**/*.md")) + [
        root / f for f in ("CLAUDE.md", "AGENTS.md", "README.md") if (root / f).exists()
    ]


def measure(root: Path) -> list[Row]:
    """Every page with the five numbers the three tests read, heaviest first.

    The whole tree every time, including in the changed-paths mode: `from`
    counts inbound links, and a page cannot know who links to it by reading
    itself. 87 pages is a few megabytes and the walk is the cheap half of this
    tool.
    """
    pages = pages_under(root)
    text = {p: p.read_text(encoding="utf-8") for p in pages}

    # Who links to whom, so a page reachable from one place only can be seen.
    inbound: dict[Path, set[Path]] = {p: set() for p in pages}
    for src, body in text.items():
        for href in LINK.findall(body):
            target = (src.parent / href).resolve()
            if target in inbound and target != src:
                inbound[target].add(src)

    rows: list[Row] = []
    for p in pages:
        body = text[p]
        secs = sections(body)
        biggest = max((len(b) for _, b in secs), default=0)
        rows.append(
            (
                tokens(body),
                p.relative_to(root).as_posix(),
                len(secs),
                round(100 * biggest / max(len(body), 1)),
                len(inbound[p]),
                sum(1 for _, b in secs if SUPERSEDED.search(b)),
            )
        )
    return sorted(rows, reverse=True)


def legend() -> None:
    print("\n  top h2  the largest section as a share of the page. A section holding most")
    print("          of a page usually holds several answers - open it and apply the")
    print("          SPLIT TEST: can you act on one section without another?")
    print("  from    how many other pages link here. 1 means one page is the only way")
    print("          in, so the MERGE TEST asks whether that page owns this as a")
    print("          section. 0 on a page nobody links is the same question, louder.")
    print("  super   sections saying a later one corrects them. Each is a DELETE TEST")
    print("          candidate, never a verdict: keep the correction whose trap a")
    print("          reader can still walk into, cut the one the correction closed.")
    print(f"\nRead the three tests in full at {STANDARD}.")


def changed(root: Path, named: list[str]) -> None:
    """The rows for the pages one change touched, and nothing else.

    A path this tool does not govern is skipped in silence rather than refused:
    the caller is a CI step handing over whatever the diff listed, and a change
    that touched no page has nothing to answer for.

    `rank` is the row's place among every page by weight. It is the one number
    here the whole-tree table cannot give you about your own page, and it is the
    one that says whether the section you just added made a heavy page heavier.
    """
    rows = measure(root)
    place = {name: index for index, (_, name, *_) in enumerate(rows, 1)}
    wanted = {Path(name).as_posix() for name in named}
    mine = [row for row in rows if row[1] in wanted]
    if not mine:
        return

    print(f"The standard is {STANDARD}.")
    print("This tool measures. It decides nothing, and no number below is a threshold.\n")
    print("PAGES THIS CHANGE TOUCHED")
    print(f"{HEADINGS} {'rank':>7}")
    for tok, name, h2, share, from_n, sup in mine:
        rank = f"{place[name]}/{len(rows)}"
        print(
            f"  {name:<52} {tok:>6,} {h2:>4} {str(share) + '%':>7} {from_n:>5} {sup:>6} {rank:>7}"
        )
    legend()
    print("\nThe page you add to pays first. Apply the SPLIT TEST to any page above")
    print("that already answers two questions; one addition buys at most one cut.")


def whole(root: Path) -> None:
    """Every page, heaviest first, with the bootstrap load above it."""
    rows = measure(root)

    print(f"The standard is {STANDARD}.")
    print("This tool measures. It decides nothing, and no number below is a threshold.")
    print("A token count is about four characters a token - an estimate, not a measurement.\n")

    print("BOOTSTRAP LOAD - held before a line of code is read")
    total = 0
    for name in ALWAYS_LOADED:
        path = root / name
        if path.exists():
            n = tokens(path.read_text(encoding="utf-8"))
            total += n
            print(f"  {name:<52} ~{n:>6,}")
    routed = [
        p
        for folder in ROUTED_TO
        if (root / folder).exists()
        for p in (root / folder).glob("**/*.md")
    ]
    if routed:
        worst = max(routed, key=lambda p: len(p.read_text(encoding="utf-8")))
        n = tokens(worst.read_text(encoding="utf-8"))
        total += n
        label = "the routed page, heaviest: " + worst.relative_to(root).as_posix()
        print(f"  {label:<52} ~{n:>6,}")
    print(f"  {'worst-case total':<52} ~{total:>6,}\n")
    print("  The test: does that leave room for the working set - the files you came")
    print("  to change, plus what you must read to change them?\n")

    print("PAGES, heaviest first")
    print(HEADINGS)
    for tok, name, h2, share, from_n, sup in rows[:20]:
        print(f"  {name:<52} {tok:>6,} {h2:>4} {str(share) + '%':>7} {from_n:>5} {sup:>6}")
    legend()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--changed",
        nargs="*",
        metavar="PATH",
        help="print only the rows for these pages, and their rank among all of them",
    )
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.changed is None:
        whole(root)
    else:
        changed(root, args.changed)


if __name__ == "__main__":
    main()
