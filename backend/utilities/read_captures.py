"""Read one item's model calls as a report: what they cost, and what came back.

The census row says a reply was 4,735 tokens where it used to be 279. It cannot
say what the model was asked. `idhazh.capture` writes that text to a run
artifact, one file per call per item, and this turns the pair into a document
read top to bottom: what looks wrong, what the calls cost, what each reply
actually says, and the raw text last.

**The raw text is kept whole and is never the first thing on the page.** A
15,000-character prompt above the numbers is a wall, and the numbers are what a
reader came for - so every prompt and every reply sits in a folded block at the
end, linked from the section that summarises it. Nothing is dropped and nothing
is elided unless `--head` asks for it.

An operator surface, not a test: pytest does not collect `backend/utilities/`,
so walking a directory here is not a growing read (`CLAUDE.md` section 13).

    python backend/utilities/read_captures.py <captures-dir>
    python backend/utilities/read_captures.py <captures-dir> --item india-5tnmq7gb
    python backend/utilities/read_captures.py <captures-dir> --item india --out pair.md

Get the directory from a finished run with:

    gh run download <run-id> --repo miztiik/yen-idhazh --name captures-<shard>

A capture written before 2026-09-15 carries no cost numbers, because the run
that wrote it did not record them here. Point `--health` at the day's ledger and
the cost section fills from the row that run did write:

    ... --health state/item-health/2026/09/14.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import count
from pathlib import Path
from typing import Any

#: The order the run makes them in. A viewer that sorted these alphabetically
#: would print the reply before the question on every item.
CALL_ORDER = ("label", "summary")

#: What each slot is called in a sentence. The slot says which call ran first
#: and only this says what it was - the distinction `CallKind` exists to keep -
#: so a document that names a slot names this beside it.
CALL_TITLE = {
    "label": "the label call",
    "summary": "the summarize-and-plan call",
}

#: A reasoning channel some builds leave inline. Stripped before the JSON is
#: looked for, and counted, because its size is itself a finding.
THINK = re.compile(r"<think>.*?</think>", re.DOTALL)

#: Longer than this and a value gets its own quoted block instead of a table
#: cell. A summary body inside a cell is a table nobody can read.
CELL_MAX = 120

#: An unbroken lowercase run longer than this is a decoder that could not leave
#: a state. The 2026-09-14 stall was 15,472 characters inside a field bounded at
#: 22 characters.
RUN_ALARM = 200


@dataclass(frozen=True, slots=True)
class Cost:
    """What one call cost, as the server reported it when the call returned."""

    kind: str
    prefill_ms: int
    decode_ms: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int

    @property
    def total_ms(self) -> int:
        """The server's own clock for this call: prefill and decode together."""
        return self.prefill_ms + self.decode_ms

    @property
    def read_tokens(self) -> int:
        """Prompt tokens the server really evaluated, the cache hits taken off."""
        return max(self.input_tokens - self.cached_tokens, 0)

    @property
    def decode_rate(self) -> float | None:
        """Tokens a second while writing, and nothing when it wrote for no time."""
        return None if self.decode_ms <= 0 else self.output_tokens / (self.decode_ms / 1000)


@dataclass(frozen=True, slots=True)
class Split:
    """One decode apportioned between the summary and the picture behind it."""

    summary_ms: int
    plan_ms: int
    summary_tokens: int
    plan_tokens: int
    is_estimate: bool


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
    finish_reason: str
    cost: Cost | None
    split: Split | None

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


def whole(value: Any) -> int:
    """One cell as a whole number, and zero where it was never filled."""
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def cost_of(payload: Any) -> Cost | None:
    """The five numbers out of a capture file, or nothing where it has none."""
    if not isinstance(payload, Mapping):
        return None
    return Cost(
        kind=str(payload.get("kind", "")),
        prefill_ms=whole(payload.get("prefill_ms")),
        decode_ms=whole(payload.get("decode_ms")),
        input_tokens=whole(payload.get("input_tokens")),
        output_tokens=whole(payload.get("output_tokens")),
        cached_tokens=whole(payload.get("cached_tokens")),
    )


def split_of(payload: Any) -> Split | None:
    """The decode apportionment out of a capture file, or nothing."""
    if not isinstance(payload, Mapping):
        return None
    return Split(
        summary_ms=whole(payload.get("summary_ms")),
        plan_ms=whole(payload.get("plan_ms")),
        summary_tokens=whole(payload.get("summary_tokens")),
        plan_tokens=whole(payload.get("plan_tokens")),
        is_estimate=bool(payload.get("is_estimate", True)),
    )


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
        finish_reason=str(payload.get("finish_reason") or ""),
        cost=cost_of(payload.get("cost")),
        split=split_of(payload.get("decode_split")),
    )


def pairs(directory: Path) -> dict[str, dict[str, Capture]]:
    """Every capture in the directory, grouped by item and keyed by call."""
    found: dict[str, dict[str, Capture]] = {}
    for path in sorted(directory.rglob("*.json")):
        capture = load(path)
        found.setdefault(capture.item_id, {})[capture.call] = capture
    return found


def ledger_split(row: Mapping[str, str]) -> Split | None:
    """The picture's share of the summarize-and-plan decode, off an item-health row.

    The row carries the picture's half and not the summary's, so the summary's
    is what is left of the decode. That subtraction is the identity the writer
    used, which is why it is safe here and is done nowhere else.
    """
    if not row.get("visual_plan_tokens_written"):
        return None
    plan_ms = whole(row.get("visual_plan_ms"))
    plan_tokens = whole(row.get("visual_plan_tokens_written"))
    return Split(
        summary_ms=max(whole(row.get("summary_decode_ms")) - plan_ms, 0),
        plan_ms=plan_ms,
        summary_tokens=max(whole(row.get("summary_output_tokens")) - plan_tokens, 0),
        plan_tokens=plan_tokens,
        is_estimate=True,
    )


def from_ledger(path: Path) -> dict[str, dict[str, tuple[Cost, Split | None, str]]]:
    """The cost numbers the run wrote to its item-health rows, by item and call.

    The fallback for a capture taken before this utility recorded its own. Both
    sources are the same five numbers off the same reply, so a capture that
    carries them wins and this fills only what it left empty.

    One named day file, read once for the whole directory. A read whose cost
    grows with the archive has to justify itself (Guardrail #12), and one that
    reopens the same file once an item is just slow. The last matching row wins:
    a day can hold two runs over one item, and the later one is the one a reader
    downloading today's artifact is asking about.
    """
    found: dict[str, dict[str, tuple[Cost, Split | None, str]]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            item_id = row.get("item_id") or ""
            for call in CALL_ORDER:
                if not row.get(f"{call}_input_tokens"):
                    continue
                found.setdefault(item_id, {})[call] = (
                    Cost(
                        kind=str(row.get(f"{call}_kind") or ""),
                        prefill_ms=whole(row.get(f"{call}_prefill_ms")),
                        decode_ms=whole(row.get(f"{call}_decode_ms")),
                        input_tokens=whole(row.get(f"{call}_input_tokens")),
                        output_tokens=whole(row.get(f"{call}_output_tokens")),
                        cached_tokens=whole(row.get(f"{call}_cached_tokens")),
                    ),
                    ledger_split(row) if call == "summary" else None,
                    str(row.get(f"{call}_finish_reason") or ""),
                )
    return found


def merged(
    pair: Mapping[str, Capture], rows: Mapping[str, tuple[Cost, Split | None, str]]
) -> dict[str, Capture]:
    """The captures, with any cost the ledger can fill that the file did not."""
    out = dict(pair)
    for call, (money, split, finish) in rows.items():
        here = out.get(call)
        if here is None or here.cost is not None:
            continue
        out[call] = replace(
            here, cost=money, split=split, finish_reason=here.finish_reason or finish
        )
    return out


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
        f"... {cut:,} characters elided, drop --head to print them ...\n\n"
        f"{text[-tail:]}"
    )


def longest_run(text: str) -> tuple[int, str]:
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


def reply_json(reply: str) -> tuple[dict[str, Any] | None, str, int]:
    """The reply's JSON object, what stopped it being read, and the thinking.

    Permissive on purpose. The reply worth opening is the one the pipeline could
    not parse, so reading it strictly against the contract would render nothing
    on exactly the item somebody came here about. What is reported instead is
    the character the JSON broke at, which is the one fact a stall log never had.
    """
    body = THINK.sub("", reply)
    if "<think>" in body:
        body = body[: body.index("<think>")]
    thought = len(reply) - len(body)
    body = body.strip()
    start = body.find("{")
    if start < 0:
        return None, "the reply carries no JSON object at all", thought
    try:
        value, end = json.JSONDecoder().raw_decode(body, start)
    except json.JSONDecodeError as error:
        broke = f"the JSON stops being readable at character {error.pos:,} - {error.msg}"
        return None, broke, thought
    if not isinstance(value, dict):
        return None, "the reply's JSON is not an object", thought
    trailing = body[end:].strip()
    note = f"{len(trailing):,} characters follow the closing brace" if trailing else ""
    return value, note, thought


def flat(value: Any) -> str:
    """Any JSON value as one line, so it fits inside a table cell."""
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={flat(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(flat(item) for item in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return ""
    return str(value)


def cell(value: Any) -> str:
    """One value as a table cell, with everything markdown would read taken out."""
    text = flat(value).replace("|", "\\|").replace("\n", " ").strip()
    return text if text else "-"


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, align: str = "") -> list[str]:
    """One markdown table, or a line saying there was nothing to put in it."""
    if not rows:
        return ["Nothing to show here.", ""]
    marks = {"l": ":---", "r": "---:"}
    rule = [marks.get(align[i] if i < len(align) else "l", ":---") for i in range(len(headers))]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(rule) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return [*lines, ""]


def quantity(value: int) -> str:
    """One number with its thousands separators."""
    return f"{value:,}"


def clock(ms: int) -> str:
    """One duration in the unit a reader compares in, with that unit attached.

    Seconds up to two minutes and minutes past it. A decode that ran for
    1,020,913 ms reads as `17m 01s` rather than as `1021.0`, and the difference
    is whether the number is read or divided.
    """
    if ms < 120_000:
        return f"{ms / 1000:.1f} s"
    minutes, rest = divmod(round(ms / 1000), 60)
    return f"{minutes}m {rest:02d}s"


def share(part: int, whole_of: int) -> str:
    """One number as a percentage of another, and a dash where there is no whole."""
    return "-" if whole_of <= 0 else f"{100 * part / whole_of:.1f}%"


def counted(many: int, one_of: str, more_of: str) -> str:
    """A count with the right form of its unit beside it.

    Because `1 entries` is the tell that a number was formatted by a program
    that was not reading it, and this document exists to be read.
    """
    return f"{many:,} {one_of}" if many == 1 else f"{many:,} {more_of}"


def is_empty(value: Any) -> bool:
    """Nothing came back under this key, so it earns a line and not a table."""
    return value is None or value == [] or value == {} or value == ""


def shape_of(value: Any) -> str:
    """What came back under one key, in the unit that key is counted in."""
    if isinstance(value, Mapping):
        return counted(len(value), "field", "fields") if value else "empty"
    if isinstance(value, list):
        return counted(len(value), "entry", "entries") if value else "empty"
    if isinstance(value, str):
        return counted(len(value), "character", "characters") if value else "empty"
    return flat(value) or "empty"


def fits_a_cell(value: Any) -> bool:
    """This value is small enough to read inside a table cell."""
    return not isinstance(value, Mapping | list) and len(flat(value)) <= CELL_MAX


def quoted(text: str) -> list[str]:
    """One long value as a block quote, so its own line breaks survive."""
    return [*[f"> {line}" if line else ">" for line in text.splitlines()], ""]


def fence(text: str) -> str:
    """A code fence longer than any run of backticks the text already holds.

    Fetched article text reaches this file, and an article that quotes a code
    block would otherwise close the fence early and spill the rest of the prompt
    into the page as markdown. The bytes are evidence, so they are shown rather
    than escaped (Guardrail #11: this is data, and the fence is what keeps it
    data).
    """
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def value_block(value: Any) -> list[str]:
    """One JSON value as the markdown that suits its shape.

    A list of objects becomes a table, because every entry answers the same
    columns and the reading is down one of them. A list of scalars becomes a
    numbered list, because the count is half of what is being checked. An object
    becomes a field table, with any value too long for a cell quoted under its
    own name rather than cut to fit one.
    """
    if isinstance(value, list) and value and all(isinstance(row, Mapping) for row in value):
        columns: list[str] = []
        for row in value:
            for key in row:
                if key not in columns:
                    columns.append(key)
        body = [
            [str(index), *[cell(row.get(column)) for column in columns]]
            for index, row in enumerate(value, 1)
        ]
        return table(["#", *columns], body, align="r" + "l" * len(columns))
    if isinstance(value, list):
        return [*[f"{index}. {cell(item)}" for index, item in enumerate(value, 1)], ""]
    if isinstance(value, Mapping):
        short = [[f"`{key}`", cell(item)] for key, item in value.items() if fits_a_cell(item)]
        out = table(["field", "value"], short, align="ll") if short else []
        for key, item in value.items():
            if fits_a_cell(item):
                continue
            out += [f"**{key}** - {shape_of(item)}", ""]
            out += quoted(item) if isinstance(item, str) else value_block(item)
        return out
    return quoted(str(value))


def priced_calls(pair: Mapping[str, Capture]) -> list[tuple[int, str, Capture, Cost]]:
    """Every call in this pair that says what it cost, in the order they ran."""
    found: list[tuple[int, str, Capture, Cost]] = []
    for call in CALL_ORDER:
        capture = pair.get(call)
        if capture is not None and capture.cost is not None:
            found.append((len(found) + 1, call, capture, capture.cost))
    return found


def cost_section(pair: Mapping[str, Capture], number: int) -> list[str]:
    """The numbers a reader opens this document for: time first, then tokens.

    One row a call and one row for the pair. The clock is the server's own -
    prefill plus decode - and it is named as that rather than as the item's wall
    clock, which also holds the queue and the HTTP round trip and is a different
    number (Guardrail #10).
    """
    step = count(1)
    out = [f"## {number}. What the calls cost", ""]
    priced = priced_calls(pair)
    if not priced:
        return [
            *out,
            "No call in this pair recorded what it cost. A capture written before "
            "2026-09-15 carries no cost numbers; pass "
            "`--health state/item-health/<yyyy>/<mm>/<dd>.csv` to fill this section "
            "from the row that run did write.",
            "",
        ]

    out += [f"### {number}.{next(step)} Time and tokens, one row a call", ""]
    rows = [
        [
            str(index),
            call if money.kind in {"", call} else f"{call} ({money.kind})",
            clock(money.total_ms),
            quantity(money.prefill_ms),
            quantity(money.decode_ms),
            quantity(money.input_tokens),
            quantity(money.cached_tokens),
            quantity(money.read_tokens),
            quantity(money.output_tokens),
            "-" if money.decode_rate is None else f"{money.decode_rate:.1f}",
            capture.finish_reason or "-",
        ]
        for index, call, capture, money in priced
    ]
    spent = [money for _, _, _, money in priced]
    rows.append(
        [
            "",
            f"**{counted(len(spent), 'call', 'calls')}**",
            f"**{clock(sum(money.total_ms for money in spent))}**",
            f"**{quantity(sum(money.prefill_ms for money in spent))}**",
            f"**{quantity(sum(money.decode_ms for money in spent))}**",
            f"**{quantity(sum(money.input_tokens for money in spent))}**",
            f"**{quantity(sum(money.cached_tokens for money in spent))}**",
            f"**{quantity(sum(money.read_tokens for money in spent))}**",
            f"**{quantity(sum(money.output_tokens for money in spent))}**",
            "-",
            "-",
        ]
    )
    out += table(
        [
            "#",
            "call",
            "model time",
            "prefill ms",
            "decode ms",
            "in tok",
            "cached tok",
            "read tok",
            "out tok",
            "decode tok/s",
            "stopped on",
        ],
        rows,
        align="rlrrrrrrrrl",
    )
    out += [
        "`model time` is the server's own clock - prefill plus decode - and not the item's "
        "wall clock, which also holds the queue and the HTTP round trip. `read tok` is "
        "what the server really evaluated: the prompt minus the part it answered out of "
        "its cache, and the only token count a prefill time can fairly be judged against.",
        "",
    ]
    out += cache_block(pair, number, step)
    out += split_block(pair, number, step)
    return out


def cache_block(pair: Mapping[str, Capture], number: int, step: Iterator[int]) -> list[str]:
    """How much of the second call's prompt the server did not read again."""
    label, summary = pair.get("label"), pair.get("summary")
    if summary is None or summary.cost is None:
        return []
    money = summary.cost
    out = [f"### {number}.{next(step)} What the cache saved on the second call", ""]
    out += [
        f"The server reused {quantity(money.cached_tokens)} of the summarize-and-plan "
        f"call's {quantity(money.input_tokens)} prompt tokens "
        f"({share(money.cached_tokens, money.input_tokens)}), so it read "
        f"{quantity(money.read_tokens)} of them and paid {quantity(money.prefill_ms)} ms "
        "for that. A zero here is a cold slot, and a cold slot means the whole article "
        "was read twice.",
        "",
    ]
    if label is not None and label.prompt and summary.prompt:
        common = shared_prefix_chars(label.prompt, summary.prompt)
        out += [
            "In characters rather than tokens: the summarize-and-plan prompt is "
            f"{quantity(len(summary.prompt))} characters and its first {quantity(common)} "
            f"({share(common, len(summary.prompt))}) are the label prompt unchanged, which "
            "is the most the cache could ever have answered.",
            "",
        ]
    return out


def split_block(pair: Mapping[str, Capture], number: int, step: Iterator[int]) -> list[str]:
    """Where the second call's decode went: the summary first, the picture after."""
    summary = pair.get("summary")
    if summary is None or summary.split is None:
        return []
    split = summary.split
    ms = split.summary_ms + split.plan_ms
    tokens = split.summary_tokens + split.plan_tokens
    out = [f"### {number}.{next(step)} The summary's share and the picture's", ""]
    out += table(
        ["half", "decode ms", "tokens written", "share of the decode"],
        [
            [
                "the summary",
                quantity(split.summary_ms),
                quantity(split.summary_tokens),
                share(split.summary_tokens, tokens),
            ],
            [
                "the visual plan",
                quantity(split.plan_ms),
                quantity(split.plan_tokens),
                share(split.plan_tokens, tokens),
            ],
            ["**both halves**", f"**{quantity(ms)}**", f"**{quantity(tokens)}**", "100.0%"],
        ],
        align="lrrr",
    )
    out += [
        "The prompt belongs to neither half, so there are no input or cached tokens to "
        "split here: both halves were written off the one prefill in row 2 above.",
        "",
    ]
    if split.is_estimate:
        out += [
            "**These two rows are an estimate.** The summary is written before the plan and "
            "the halves never interleave, so a boundary in the bytes really is a boundary "
            "in time - but the two were never timed separately. The share is apportioned "
            "by characters.",
            "",
        ]
    return out


def reply_section(capture: Capture, title: str, number: int) -> list[str]:
    """One reply read as what it says, rather than as the bytes it arrived in."""
    out = [f"## {number}. What {title} sent back", ""]
    if capture.reply is None:
        return [*out, "The reply was not captured on this run.", ""]
    payload, trouble, thought = reply_json(capture.reply)
    step = count(1)
    if thought:
        out += [
            f"The reply opened with {quantity(thought)} characters of reasoning. They are "
            "in the raw block and in none of the tables below.",
            "",
        ]
    if payload is None:
        return [
            *out,
            f"**This reply cannot be read as JSON**: {trouble}. That is the whole finding "
            f"here - read it under [{capture.call} came back](#{anchor(capture.call)}).",
            "",
        ]
    if trouble:
        out += [f"**{trouble}.** The tables below read the object and stop at it.", ""]

    out += [f"### {number}.{next(step)} At a glance", ""]
    out += table(
        ["field", "what came back"],
        [[f"`{key}`", shape_of(value)] for key, value in payload.items()],
        align="ll",
    )
    for key, value in payload.items():
        if is_empty(value):
            continue
        out += [f"### {number}.{next(step)} `{key}` - {shape_of(value)}", ""]
        out += value_block(value)
    blank = [f"`{key}`" for key, value in payload.items() if is_empty(value)]
    if blank:
        out += [f"Nothing came back under {', '.join(blank)}.", ""]
    return out


def findings(pair: Mapping[str, Capture]) -> list[str]:
    """Everything that looks wrong in this pair, ahead of everything that does not."""
    said: list[str] = []
    for call in CALL_ORDER:
        name = CALL_TITLE.get(call, call)
        capture = pair.get(call)
        if capture is None:
            said.append(f"There is no capture file for {name}.")
            continue
        if capture.missing:
            said.append(f"On {name}, {capture.missing} was not captured.")
        if capture.finish_reason == "length":
            said.append(
                f"{name.capitalize()} stopped on `length`, so its reply was cut by the "
                "output budget rather than finished."
            )
        if capture.reply is None:
            continue
        run_length, sample = longest_run(capture.reply)
        if run_length > RUN_ALARM:
            said.append(
                f"The reply to {name} holds a {run_length:,}-character unbroken lowercase "
                f"run starting `{sample}`. That is a decoder that could not leave a state, "
                "not an article that was long."
            )
        _, trouble, _ = reply_json(capture.reply)
        if trouble:
            said.append(f"The reply to {name}: {trouble}.")
    return said


def anchor(call: str) -> str:
    """The link target for one call's raw reply.

    A named HTML anchor rather than the heading's own slug, because the heading
    carries a section number and the number moves the day a section is added.
    A link that breaks silently when the document is renumbered is worse than no
    link, since nothing in a markdown file checks one.
    """
    return f"raw-{call}-came-back"


def raw_section(pair: Mapping[str, Capture], number: int, *, head: int, tail: int) -> list[str]:
    """The last section: every prompt and every reply, whole, and folded away.

    Folded rather than dropped. The bytes are the evidence, and a document that
    summarises evidence without carrying it cannot be checked - but a reader who
    wanted the summary should not have to scroll a prompt to reach it.
    """
    step = count(1)
    out = [
        f"## {number}. The raw text",
        "",
        "Exactly what was sent and what came back, nothing reformatted. Open one to read it.",
        "",
    ]
    for call in CALL_ORDER:
        capture = pair.get(call)
        if capture is None:
            continue
        halves = (("sent", capture.prompt), ("came back", capture.reply))
        for half, text in halves:
            if half == "came back":
                out += [f'<a id="{anchor(call)}"></a>', ""]
            out += [f"### {number}.{next(step)} {call} {half}", ""]
            if text is None:
                out += ["Not captured on this run.", ""]
                continue
            digest = f", sha256 {capture.prompt_sha256[:12]}" if half == "sent" else ""
            shown = elide(text, head=head, tail=tail)
            rail = fence(shown)
            out += [
                "<details>",
                f"<summary>{counted(len(text), 'character', 'characters')}{digest}</summary>",
                "",
                f"{rail}text",
                shown,
                rail,
                "",
                "</details>",
                "",
            ]
    return out


def render(pair: Mapping[str, Capture], *, head: int, tail: int) -> str:
    """One item's calls as a document: what is wrong, what it cost, then the bytes.

    Every heading carries its number, and the numbers run in the order a reader
    needs them rather than the order the run produced them: the verdict, the
    cost, each reply read as what it says, and the bytes last.
    """
    item_id = next(iter(pair.values())).item_id
    said = findings(pair)
    out: list[str] = [f"# {item_id}", "", "## 1. What to look at", ""]
    if said:
        out += [*[f"- {line}" for line in said], ""]
    else:
        captured = sum(1 for call in CALL_ORDER if call in pair)
        out += [
            "**Nothing in this pair looks wrong.** "
            f"{counted(captured, 'call', 'calls')} captured, each finished on its own "
            "terms, each reply readable as JSON.",
            "",
        ]

    out += cost_section(pair, 2)
    for number, call in enumerate(CALL_ORDER, 3):
        capture = pair.get(call)
        title = CALL_TITLE.get(call, call)
        if capture is None:
            out += [f"## {number}. What {title} sent back", ""]
            out += ["There is no capture file for this call.", ""]
            continue
        out += reply_section(capture, title, number)
    out += raw_section(pair, len(CALL_ORDER) + 3, head=head, tail=tail)
    return "\n".join(out)


def summarise(found: Mapping[str, Mapping[str, Capture]]) -> str:
    """One line an item, so a reader can pick the one worth opening."""
    header = (
        f"{'item_id':<30} {'label sent':>10} {'label back':>11} "
        f"{'summ sent':>10} {'summ back':>10} {'model time':>10} {'out tok':>8}"
    )
    rows = [header, "-" * len(header)]
    for item_id, pair in found.items():
        label, summary = pair.get("label"), pair.get("summary")
        spent = [money for _, _, _, money in priced_calls(pair)]
        rows.append(
            f"{item_id:<30} "
            f"{label.prompt_chars if label else 0:>10,} "
            f"{label.reply_chars if label else 0:>11,} "
            f"{summary.prompt_chars if summary else 0:>10,} "
            f"{summary.reply_chars if summary else 0:>10,} "
            f"{clock(sum(money.total_ms for money in spent)) if spent else '-':>10} "
            f"{sum(money.output_tokens for money in spent):>8,}"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", type=Path, help="a captures directory from a run artifact")
    parser.add_argument("--item", help="an item id, or any part of one. Omit to list every item")
    parser.add_argument(
        "--full",
        action="store_true",
        help="accepted and no longer needed: every character is printed by default",
    )
    parser.add_argument(
        "--head",
        type=int,
        default=0,
        help="characters kept from the front of each raw block. 0, the default, keeps all",
    )
    parser.add_argument(
        "--tail", type=int, default=2500, help="characters kept from the back, when --head is set"
    )
    parser.add_argument(
        "--health",
        type=Path,
        help="the day's item-health CSV, for a capture written before costs were recorded",
    )
    parser.add_argument("--out", type=Path, help="write markdown here instead of to the terminal")
    args = parser.parse_args(argv)

    if not args.directory.is_dir():
        parser.error(f"{args.directory} is not a directory")
    if args.health is not None and not args.health.is_file():
        parser.error(f"{args.health} is not a file")
    found = pairs(args.directory)
    if not found:
        parser.error(
            f"{args.directory} holds no capture files. Both logging.capture_prompts and "
            "logging.capture_replies default on; a run with both off writes nothing here"
        )

    if not args.item:
        listed = found
        if args.health is not None:
            rows = from_ledger(args.health)
            listed = {
                item_id: merged(pair, rows.get(item_id, {})) for item_id, pair in found.items()
            }
        print(summarise(listed))
        print(f"\n{len(listed)} item(s). Add --item <id> to read one.")
        return 0

    wanted = [item_id for item_id in found if args.item in item_id]
    if not wanted:
        parser.error(f"no item id contains {args.item!r}. Run without --item to list them")

    head = 0 if args.full else args.head
    rows = from_ledger(args.health) if args.health is not None else {}
    documents = []
    for item_id in wanted:
        pair = merged(found[item_id], rows.get(item_id, {}))
        documents.append(render(pair, head=head, tail=args.tail))
    text = "\n\n".join(documents)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"{args.out} written, {len(text):,} characters")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
