"""Hold every page against the documentation standard, and print what it says.

The standard has two halves and they need opposite treatment. Its three tests -
split, merge, delete - are judgement, so this tool hands them numbers and no
verdict: no column here is a threshold, and the standard deliberately gives no
page a maximum length, because a line limit is met by starting a second file.
Its required elements have one correct answer each, so those are reported as
faults rather than as measurements.

**Nothing here fails a build.** The standard has no doc gate, for the same
reason it has no length limit, and a fault printed beside the page that carries
it is what the rule was ever going to get.

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

#: A link that names a section. The fragment is half the link: a file that still
#: exists proves nothing about the heading somebody meant to land on.
ANCHORED = re.compile(r"\]\(([^)\s#]+\.md)#([^)\s]+)\)")

#: What GitHub does to a heading to make its anchor: lowercase it, drop anything
#: that is not a word character, a space or a hyphen, then hyphenate the spaces.
NOT_IN_ANCHOR = re.compile(r"[^\w\s-]")

#: The stamp a reader prices staleness from, so its shape is checked too - a
#: date nobody can compare is the same as no date.
STAMP = re.compile(r"^\*\*Last Updated\*\*:\s*\d{4}-\d{2}-\d{2}\s*$")

#: How far under the title the stamp may sit before a reader stops finding it.
STAMP_WITHIN = 5


def tokens(text: str) -> int:
    """About four characters a token. A declared estimate, not a measurement."""
    return len(text) // 4


def prose(text: str) -> list[str]:
    """The lines that are Markdown. A `# ` inside a shell block is a comment."""
    out: list[str] = []
    fence = False
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
        elif not fence:
            out.append(line)
    return out


def anchors(text: str) -> set[str]:
    """Every heading on a page, as the fragment a link would have to name."""
    out = set()
    for line in prose(text):
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                out.add(re.sub(r"\s+", "-", NOT_IN_ANCHOR.sub("", heading.lower()).strip()))
    return out


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

    **The root is resolved first, and that is load-bearing.** A link target is
    resolved to compare it, so a relative root makes every comparison fail and
    every page read as one nobody links to - a wrong answer that looks like a
    finding rather than like a fault.
    """
    root = root.resolve()
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


def faults(root: Path) -> dict[str, list[str]]:
    """Every page under `docs/` that is missing something the standard requires.

    Only `docs/` is held to this. `CLAUDE.md` and `README.md` are the contract
    and the front door rather than pages the placement rules route to, and the
    standard's required-elements list is written for the tree it organises.

    A fault here is not an opinion about the page. Each one names a thing the
    standard says every page carries, so a reader who does not find it is left
    with no date to price staleness from, no way out of the page, or a heading
    the anchor links cannot reach.
    """
    root = root.resolve()
    pages = sorted(root.glob("docs/**/*.md"))
    text = {p: p.read_text(encoding="utf-8") for p in pages}
    here = {p.resolve(): anchors(body) for p, body in text.items()}

    out: dict[str, list[str]] = {}
    for page in pages:
        rel = page.relative_to(root).as_posix()
        body = text[page]
        lines = body.split("\n")
        found: list[str] = []

        titles = sum(1 for line in prose(body) if line.startswith("# "))
        if titles != 1:
            found.append(f"{titles} H1 titles, and the standard asks for exactly one")
        if not any(STAMP.match(line) for line in lines[:STAMP_WITHIN]):
            found.append(f"no **Last Updated**: YYYY-MM-DD in the first {STAMP_WITHIN} lines")
        if not any(line.lower().startswith("## see also") for line in prose(body)):
            found.append('no "## See also", so the page is a dead end')
        if rel.count("/") > 3:
            found.append("nested past docs/<tier>/<topic>/<file>.md, so it is two topics")
        odd = sorted({ch for ch in body if ord(ch) > 127})
        if odd:
            shown = " ".join(f"U+{ord(ch):04X}" for ch in odd[:4])
            found.append(f"{len(odd)} non-ASCII characters, first: {shown}")
        for href in sorted(set(LINK.findall(body))):
            if "<" in href:
                continue  # a placeholder in a worked example names no page
            if not (page.parent / href).exists():
                found.append(f"links to a page that is not there: {href}")
        for href, fragment in sorted(set(ANCHORED.findall(body))):
            if "<" in href:
                continue
            target = (page.parent / href).resolve()
            if target in here and fragment not in here[target]:
                found.append(f"links to a section that is not there: {href}#{fragment}")

        if found:
            out[rel] = found
    return out


def report_faults(flagged: dict[str, list[str]], scope: str) -> None:
    """Print the faults, or say the pages carry what the standard asks for."""
    print("\nREQUIRED ELEMENTS - one correct answer each, so these are faults not numbers")
    if not flagged:
        print(f"  {scope} carries all of them.")
        return
    for name, found in sorted(flagged.items()):
        print(f"  {name}")
        for fault in found:
            print(f"      {fault}")
    print("\n  Nothing here fails a build. The standard has no doc gate, for the same")
    print("  reason it sets no page length: a count is met by starting a second file.")


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
    report_faults({k: v for k, v in faults(root).items() if k in wanted}, "Every page you touched")
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
    report_faults(faults(root), "Every page under docs/")


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
