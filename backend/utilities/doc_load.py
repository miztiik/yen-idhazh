"""Measure what the docs cost a reader, and hand the numbers to the three tests.

This tool decides nothing. Every column it prints is an input to a test written
in `docs/reference/documentation-structure.md`, and no number here is a
threshold - the standard deliberately gives no page a maximum length, because a
line limit is met by starting a second file.

Run it with no arguments from the repository root:

    python backend/utilities/doc_load.py
"""

from __future__ import annotations

import re
from pathlib import Path

STANDARD = "docs/reference/documentation-structure.md"

#: Loaded on every task before a line of code is read (docs/agents/bootstrap.md).
ALWAYS_LOADED = ("CLAUDE.md", "AGENTS.md", "docs/agents/bootstrap.md")

#: The bootstrap also pulls one of each of these. The worst case is the heaviest.
PICKED_ONE_OF = {
    "a subsystem doc": "docs/architecture",
    "a concept doc": "docs/concepts",
    "a plan-doc": "TODO",
}

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


def main() -> None:
    root = Path.cwd()
    pages = sorted(p for p in root.glob("docs/**/*.md")) + [
        root / f for f in ("CLAUDE.md", "AGENTS.md", "README.md") if (root / f).exists()
    ]
    text = {p: p.read_text(encoding="utf-8") for p in pages}

    # Who links to whom, so a page reachable from one place only can be seen.
    inbound: dict[Path, set[Path]] = {p: set() for p in pages}
    for src, body in text.items():
        for href in LINK.findall(body):
            target = (src.parent / href).resolve()
            if target in inbound and target != src:
                inbound[target].add(src)

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
    for label, folder in PICKED_ONE_OF.items():
        found = sorted((root / folder).glob("**/*.md")) if (root / folder).exists() else []
        if not found:
            continue
        worst = max(found, key=lambda p: len(p.read_text(encoding="utf-8")))
        n = tokens(worst.read_text(encoding="utf-8"))
        total += n
        print(f"  {label + ', heaviest: ' + worst.relative_to(root).as_posix():<52} ~{n:>6,}")
    print(f"  {'worst-case total':<52} ~{total:>6,}\n")
    print("  The test: does that leave room for the working set - the files you came")
    print("  to change, plus what you must read to change them?\n")

    print("PAGES, heaviest first")
    print(f"  {'page':<52} {'~tok':>6} {'h2':>4} {'top h2':>7} {'from':>5} {'super':>6}")
    rows = []
    for p in pages:
        body = text[p]
        secs = sections(body)
        biggest = max((len(b) for _, b in secs), default=0)
        share = round(100 * biggest / max(len(body), 1))
        rows.append(
            (
                tokens(body),
                p.relative_to(root).as_posix(),
                len(secs),
                share,
                len(inbound[p]),
                sum(1 for _, b in secs if SUPERSEDED.search(b)),
            )
        )
    for tok, name, h2, share, from_n, sup in sorted(rows, reverse=True)[:20]:
        print(f"  {name:<52} {tok:>6,} {h2:>4} {str(share) + '%':>7} {from_n:>5} {sup:>6}")

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


if __name__ == "__main__":
    main()
