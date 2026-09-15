"""Read one item's two model calls: what was sent, what came back, in order.

The census row says a reply was 4,735 tokens where it used to be 279. It cannot
say what the model was asked. `idhazh.capture` writes that text to a run
artifact, one file per call per item, and this prints it in the order the run
made the calls - label prompt, label reply, summary prompt, summary reply - so a
person can read a stall instead of inferring one.

An operator surface, not a test: pytest does not collect `backend/utilities/`,
so walking a directory here is not a growing read (`CLAUDE.md` section 13).

    python backend/utilities/read_captures.py <captures-dir>
    python backend/utilities/read_captures.py <captures-dir> --item india-5tnmq7gb
    python backend/utilities/read_captures.py <captures-dir> --item india --full --out pair.md

Get the directory from a finished run with:

    gh run download <run-id> --repo miztiik/yen-idhazh --name captures-<shard>
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

#: The order the run makes them in. A viewer that sorted these alphabetically
#: would print the reply before the question on every item.
CALL_ORDER = ("label", "summary")


@dataclass(frozen=True, slots=True)
class Capture:
    """One call's capture file, as it was written."""

    item_id: str
    call: str
    prompt: str | None
    reply: str | None
    prompt_chars: int
    reply_chars: int
    prompt_sha256: str

    @property
    def missing(self) -> str | None:
        """Which half the run's flags left out, if either."""
        if self.prompt is None and self.reply is None:
            return "both halves"
        if self.prompt is None:
            return "the prompt"
        if self.reply is None:
            return "the reply"
        return None


def load(path: Path) -> Capture:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Capture(
        item_id=str(payload.get("item_id", path.stem)),
        call=str(payload.get("call", "?")),
        prompt=payload.get("prompt"),
        reply=payload.get("reply"),
        prompt_chars=int(payload.get("prompt_chars", 0)),
        reply_chars=int(payload.get("reply_chars", 0)),
        prompt_sha256=str(payload.get("prompt_sha256", "")),
    )


def shared_prefix_chars(first: str, second: str) -> int:
    """How much of the second prompt is the first prompt, character for character.

    This is the cache question in one number. The summarize call is built on the
    label call's prompt, so everything up to here is what `llama-server` can
    answer from the slot it already holds, and everything after it is prefill it
    has to pay for.
    """
    limit = min(len(first), len(second))
    for index in range(limit):
        if first[index] != second[index]:
            return index
    return limit


def elide(text: str, *, head: int, tail: int) -> str:
    """The front and the back of a long text, with the middle counted not shown.

    The middle of a prompt is the article body, which is the part a reader
    already knows the shape of. The front carries the instructions and the back
    carries the question, and a runaway decode is always visible in the back.
    """
    if head <= 0 or len(text) <= head + tail:
        return text
    cut = len(text) - head - tail
    return (
        f"{text[:head]}\n\n"
        f"... {cut:,} characters elided, --full prints them ...\n\n"
        f"{text[-tail:]}"
    )


def _longest_run(text: str) -> tuple[int, str]:
    """The longest stretch of lowercase letters, and where it starts.

    The 2026-09-14 stall was one 15,472-character lowercase run inside a field
    bounded at 22, so this is the cheapest thing that names it on sight.
    """
    best_length = 0
    best_at = 0
    length = 0
    for index, char in enumerate(text):
        if char.isalpha() and char.islower():
            length += 1
            if length > best_length:
                best_length = length
                best_at = index - length + 1
        else:
            length = 0
    return best_length, text[best_at : best_at + 60]


def render(pair: dict[str, Capture], *, head: int, tail: int) -> str:
    """One item's two calls as a markdown document, in call order."""
    item_id = next(iter(pair.values())).item_id
    out: list[str] = [f"# {item_id}", ""]

    label, summary = pair.get("label"), pair.get("summary")
    if label and summary and label.prompt and summary.prompt:
        shared = shared_prefix_chars(label.prompt, summary.prompt)
        share = 100 * shared / len(summary.prompt)
        out += [
            f"The summarize-and-plan prompt is {len(summary.prompt):,} characters and its "
            f"first {shared:,} ({share:.1f} percent) are the label prompt unchanged, so that "
            "much can come from the slot the server already holds.",
            "",
        ]

    for call in CALL_ORDER:
        capture = pair.get(call)
        if capture is None:
            out += [f"## {call}", "", "No capture file for this call.", ""]
            continue
        out += [
            f"## {call}",
            "",
            f"- prompt: {capture.prompt_chars:,} characters, "
            f"sha256 {capture.prompt_sha256[:12]}",
            f"- reply: {capture.reply_chars:,} characters",
        ]
        if capture.missing:
            out += [f"- {capture.missing} was not captured on this run", ""]
        else:
            out += [""]
        if capture.prompt is not None:
            out += [
                f"### {call}: sent",
                "",
                "```text",
                elide(capture.prompt, head=head, tail=tail),
                "```",
                "",
            ]
        if capture.reply is not None:
            run_length, sample = _longest_run(capture.reply)
            if run_length > 200:
                out += [
                    f"**The reply holds a {run_length:,}-character unbroken lowercase run** "
                    f"starting `{sample}`. That is a decoder that could not leave a state, "
                    "not an article that was long.",
                    "",
                ]
            out += [
                f"### {call}: came back",
                "",
                "```text",
                elide(capture.reply, head=head, tail=tail),
                "```",
                "",
            ]
    return "\n".join(out)


def pairs(directory: Path) -> dict[str, dict[str, Capture]]:
    """Every capture in the directory, grouped by item and keyed by call."""
    found: dict[str, dict[str, Capture]] = {}
    for path in sorted(directory.rglob("*.json")):
        capture = load(path)
        found.setdefault(capture.item_id, {})[capture.call] = capture
    return found


def summarise(found: dict[str, dict[str, Capture]]) -> str:
    """One line an item, so a reader can pick the one worth opening."""
    rows = ["item_id                        label sent  label back  summ sent  summ back"]
    for item_id, pair in found.items():
        label, summary = pair.get("label"), pair.get("summary")
        rows.append(
            f"{item_id:<30} "
            f"{label.prompt_chars if label else 0:>10,} "
            f"{label.reply_chars if label else 0:>11,} "
            f"{summary.prompt_chars if summary else 0:>10,} "
            f"{summary.reply_chars if summary else 0:>10,}"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", type=Path, help="a captures directory from a run artifact")
    parser.add_argument("--item", help="an item id, or any part of one. Omit to list every item")
    parser.add_argument("--full", action="store_true", help="print every character, eliding none")
    parser.add_argument(
        "--head", type=int, default=2500, help="characters kept from the front of each text"
    )
    parser.add_argument(
        "--tail", type=int, default=2500, help="characters kept from the back of each text"
    )
    parser.add_argument("--out", type=Path, help="write markdown here instead of to the terminal")
    args = parser.parse_args(argv)

    if not args.directory.is_dir():
        parser.error(f"{args.directory} is not a directory")
    found = pairs(args.directory)
    if not found:
        parser.error(
            f"{args.directory} holds no capture files. Both logging.capture_prompts and "
            "logging.capture_replies default on; a run with both off writes nothing here"
        )

    if not args.item:
        print(summarise(found))
        print(f"\n{len(found)} item(s). Add --item <id> to read one.")
        return 0

    wanted = [item_id for item_id in found if args.item in item_id]
    if not wanted:
        parser.error(f"no item id contains {args.item!r}. Run without --item to list them")

    head = 0 if args.full else args.head
    text = "\n\n".join(render(found[item_id], head=head, tail=args.tail) for item_id in wanted)
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"{args.out} written, {len(text):,} characters")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
