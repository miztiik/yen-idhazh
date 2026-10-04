"""Hold named pages against the documentation standard, and print what they say.

The standard has two halves and they need opposite treatment. Its three tests -
split, merge, delete - are judgement, so this tool hands them numbers and no
verdict: no column here is a threshold, and the standard deliberately gives no
page a maximum length, because a line limit is met by starting a second file.
Its required elements have one correct answer each, so those are reported as
faults rather than as measurements, and only for pages under `docs/`.

**Nothing here fails a build.** The standard has no doc gate, for the same
reason it has no length limit, and a fault printed beside the page that carries
it is what the rule was ever going to get.

Name every Markdown page a change touched, a plan included. No CI job runs this
tool, so run it before and after the change:

    python backend/utilities/doc_load.py docs/concepts/config.md
"""

from __future__ import annotations

import argparse
import os
import re
from collections.abc import Sequence
from pathlib import Path

STANDARD = "docs/reference/documentation-structure.md"

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

#: A target that opens with a scheme, such as `https:`, is an address on another
#: site. The tool never reads the network, so it does not judge one. A scheme is
#: two characters at least, so a drive such as `C:` is still judged as a path.
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")

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


def names_a_page_here(href: str) -> bool:
    """Does this link target name a page in this repository?

    A placeholder in a worked example, such as `<slug>.md`, names no page. An
    address on another site names a page this tool cannot see.
    """
    return "<" not in href and not SCHEME.match(href)


def is_there(target: Path) -> bool:
    """Does this path exist, spelled exactly like this?

    Resolve this one address, not a listing of its parent. On Windows realpath
    obtains the stored spelling from the file handle.
    """
    try:
        actual = Path(os.path.realpath(target, strict=True))
        return actual.name == target.name
    except OSError:
        return False


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


def pages_under(root: Path, named: Sequence[str]) -> list[Path]:
    """Existing named Markdown pages inside the repository.

    A deleted path, a code input and a path outside the repository are skipped.
    """
    root = root.resolve()
    paths: list[Path] = []
    for name in sorted(set(named)):
        path = (root / name).resolve()
        if path.suffix == ".md" and path.is_file() and path.is_relative_to(root):
            paths.append(path)
    return paths


def measure(root: Path, named: Sequence[str]) -> list[Row]:
    """Named pages and links between those pages, heaviest first."""
    root = root.resolve()
    pages = pages_under(root, named)
    text = {p: p.read_text(encoding="utf-8") for p in pages}

    # Who links to whom, so a page reachable from one place only can be seen.
    inbound: dict[Path, set[Path]] = {p: set() for p in pages}
    for src, body in text.items():
        for href in LINK.findall(body):
            if not names_a_page_here(href):
                continue
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
    print("  from    links from other named pages only, not from the whole repository.")
    print("          This count cannot prove that a page has no other inbound links.")
    print("  super   sections saying a later one corrects them. Each is a DELETE TEST")
    print("          candidate, never a verdict: keep the correction whose trap a")
    print("          reader can still walk into, cut the one the correction closed.")
    print(f"\nRead the three tests in full at {STANDARD}.")


def faults(root: Path, named: Sequence[str]) -> dict[str, list[str]]:
    """Named pages under `docs/` that lack something the standard requires.

    Only `docs/` is held to this, because the standard's required-elements list
    is written for the tree it organises. `CLAUDE.md` and `README.md` are the
    contract and the front door, and a plan under `TODO/` answers to the
    plan-doc rule instead.

    A fault here is not an opinion about the page. Each one names a thing the
    standard says every page carries, so a reader who does not find it is left
    with no date to price staleness from, no way out of the page, or a heading
    the anchor links cannot reach.
    """
    root = root.resolve()
    pages = [
        p for p in pages_under(root, named) if p.relative_to(root).as_posix().startswith("docs/")
    ]
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
        see_also = [line.lower().startswith("## see also") for line in prose(body)]
        if not any(see_also):
            found.append('no "## See also", so the page is a dead end')
        elif not LINK.search(body.split("## See also", 1)[-1]):
            found.append('"## See also" carries no link, which is the same dead end')
        if rel.count("/") > 3:
            found.append("nested past docs/<tier>/<topic>/<file>.md, so it is two topics")
        odd = sorted({ch for ch in body if ord(ch) > 127})
        if odd:
            shown = " ".join(f"U+{ord(ch):04X}" for ch in odd[:4])
            found.append(f"{len(odd)} non-ASCII characters, first: {shown}")
        for href in sorted(set(LINK.findall(body))):
            if not names_a_page_here(href):
                continue
            if not is_there(page.parent / href):
                found.append(f"links to a page that is not there: {href}")
        for href, fragment in sorted(set(ANCHORED.findall(body))):
            if not names_a_page_here(href):
                continue
            target = (page.parent / href).resolve()
            if target not in here and is_there(page.parent / href):
                here[target] = anchors(target.read_text(encoding="utf-8"))
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
    """Report only named pages, plus direct link targets needed to check anchors."""
    mine = measure(root, named)
    if not mine:
        return

    print(f"The standard is {STANDARD}.")
    print("This tool measures. It decides nothing, and no number below is a threshold.\n")
    print("PAGES THIS CHANGE TOUCHED")
    print(HEADINGS)
    for tok, name, h2, share, from_n, sup in mine:
        print(f"  {name:<52} {tok:>6,} {h2:>4} {str(share) + '%':>7} {from_n:>5} {sup:>6}")
    legend()
    report_faults(faults(root, named), "Every page you touched under docs/")
    print("\nThe page you add to pays first. Apply the SPLIT TEST to any page above")
    print("that already answers two questions; one addition buys at most one cut.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="print only these pages; inbound counts cover this named set",
    )
    args = parser.parse_args(argv)
    root = Path.cwd()
    changed(root, args.paths)


if __name__ == "__main__":
    main()
