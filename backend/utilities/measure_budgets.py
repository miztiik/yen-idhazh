"""Retake the three budgets a vocabulary sizes, and say out loud when they are stale.

Three constants in this repository were sized by asking a tokenizer a question,
and all three sit where a loaded record cannot reach them: `DefinitionText` and
`WORST_CASE_REPLY_CHARACTERS` are in `contracts/`, which is the bottom of the
dependency graph and imports no other subpackage (`CLAUDE.md` section 4), and
`TOKENS_PER_WORD` is read by an import-time assertion in `classify.calls`.
`idhazh.measured.SIZED_BY_A_READING_HERE` pairs each site with the reading behind
it, which is what makes the question askable at all.

Two verbs, and the split is deliberate.

- `check` opens no socket. It compares each reading's `subject` against the
  weights `config/` names and exits non-zero on any that disagree. This is an
  operator surface rather than a test, because all three are stale on every
  commit until somebody retakes them, and a test that is red on a state nobody
  has fixed yet is a test people learn to scroll past (`CLAUDE.md` section 13).
- `read` needs a running `llama-server` and asks its `/tokenize` for each of the
  three quantities. **It asks the server rather than reasoning about a
  vocabulary**, which is the whole difference between a reading and an argument:
  the tokenizer ships inside the weights and it moves when they do.

**This writes nothing a commit would carry.** It prints, and optionally saves a
JSON artifact under a path the caller names. A person reads the print-out and
edits `backend/idhazh/measured.py`. A workflow that wrote a measurement into a
commit would be a workflow deciding a number, which this tree reserves for people
- printing is not writing.

**No fetched text leaves this module.** The tokens-a-word probe reads corpus
article bodies, which came off the open web, and emits counts of them and never a
character of them (Guardrail #11).

Each probe is one fixed text, so **spread is 0 and the reading says so rather
than omitting the field**: a tokenizer is deterministic, so the same inputs and
the same weights return the identical number on every run. There is nothing to
repeat and no variance to report, which is exactly what a timing cannot say.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final, Protocol

from idhazh import config
from idhazh.contracts.corpus import ChatRole, CorpusRow
from idhazh.contracts.taxonomy import LifecycleStatus
from idhazh.contracts.visual import PlanEncodings
from idhazh.measured import (
    SIZED_BY_A_READING_HERE,
    Unreached,
    describe_a_retake,
    readings_awaiting_a_retake,
)
from idhazh.sanitize import FENCE_CLOSE, FENCE_OPEN

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
CONFIG_DIR: Final = REPO_ROOT / "config"
CORPUS: Final = REPO_ROOT / "corpus" / "corpus.jsonl"
PLAN_FIXTURES: Final = REPO_ROOT / "tests" / "fixtures" / "contracts" / "visual-plan"

#: The two committed plans, declining first. The empty-role cost is a per-role
#: rate and the declining plan is where every role is empty, so it is the case
#: that fixes the rate; the four-bar one is what says the rate holds when two
#: roles are filled.
PLAN_PROBES: Final = ("declined.json", "bar-chart.json")

#: Every encoding role the plan shape declares, in the order the schema does. A
#: role missing from a fixture is an empty role that the fixture omitted, so the
#: list has to come from the shape rather than from the fixture.
_PLAN_ENCODINGS: Final = "encodings"

#: How many corpus rows the tokens-a-word probe reads. Bounded on purpose: the
#: corpus grows with every harvest and a probe whose cost rises because a run
#: appended is the defect Guardrail #12 names. 200 rows is about 250,000 words,
#: which is enough that one long article cannot move the ratio.
DEFAULT_SAMPLES: Final = 200

#: Long enough that a cold server answers, short enough that a dead one is not a
#: five-minute wait.
DEFAULT_TIMEOUT: Final = 120.0


class ServerSilentError(RuntimeError):
    """The server did not answer, so there is no reading rather than a guessed one."""


class CountsTokens(Protocol):
    """Anything that can say how many tokens a string is.

    The probes below are typed against this rather than against `Tokenizer`, so a
    test can drive every one of them from a committed fixture without opening a
    socket (Guardrail #7). The live implementation is the only one that ships.
    """

    def count(self, text: str) -> int: ...


def tokens_in_reply(body: Any, *, base: str) -> int:
    """How many tokens llama.cpp's `/tokenize` said, refusing anything else.

    Split out of the request so the rule can be proved without a server. A reply
    with no `tokens` array is not a small count - it is not a count - and the
    difference has to be a refusal rather than a zero.
    """
    tokens = body.get("tokens") if isinstance(body, dict) else None
    if not isinstance(tokens, list):
        raise ServerSilentError(
            f"{base} answered /tokenize without a tokens array, so nothing here is a "
            f"count: it said {body!r}"
        )
    return len(tokens)


@dataclass(frozen=True, slots=True)
class BudgetReading:
    """One quantity, what was tokenized to get it, and why that text.

    `spread` is 0 and present. A tokenizer over a fixed text is exact, so there
    is no run-to-run variance to report - but a reading that omitted the field
    would read as a reading that forgot to take it (Guardrail #10).
    """

    record: str
    measures: str
    value: float
    unit: str
    spread: float
    probe: str
    why_that_probe: str
    #: How much text was counted, in the probe's own units. A total can move
    #: because the probe changed rather than the vocabulary, so the two are
    #: printed side by side and neither is quoted alone.
    probe_size: str
    #: What the value was divided by, so the number can be re-derived from the
    #: same two counts rather than trusted.
    working: dict[str, float]
    subject: str
    runner: str
    taken_on: str

    def as_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Tokenizer:
    """The running server's own tokenizer, over its own HTTP.

    The same shape `measure_two_calls.Tokenizer` uses and for the same reason:
    asking the server is the only way to count with the vocabulary that is
    actually loaded. It differs in one way - a server that will not answer raises
    here rather than yielding `None`, because every caller below has exactly one
    thing to do about it and that is to stop.
    """

    base: str
    timeout: float

    def count(self, text: str) -> int:
        outbound = urllib.request.Request(
            f"{self.base.rstrip('/')}/tokenize",
            data=json.dumps({"content": text, "add_special": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(outbound, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as unreachable:
            raise ServerSilentError(
                f"{self.base} did not answer /tokenize ({unreachable}). Start llama-server "
                "on the configured weights first - there is no reading without one, and a "
                "number taken any other way would not be a reading"
            ) from unreachable
        return tokens_in_reply(body, base=self.base)


# --- The three probes --------------------------------------------------------


def definition_probe(config_dir: Path) -> tuple[str, int]:
    """The definition block a labelling prompt carries, and how many entries it offers.

    `Taxonomy.definition_block` rather than a join written here: it is already
    the one place the prompt's wording comes from, so probing anything else
    would measure a string this pipeline never sends. A draft entry contributes
    nothing to the block and is not counted, which is what makes the per-entry
    figure the cost of an entry a prompt actually carries.
    """
    taxonomy = config.load(config_dir).taxonomy
    offered = sum(
        1
        for group in (taxonomy.verticals, taxonomy.lenses, taxonomy.events)
        for entry in group
        if entry.status is LifecycleStatus.ACTIVE
    )
    return taxonomy.definition_block(), offered


def empty_role_fragment(plan: dict[str, Any], roles: Sequence[str]) -> str:
    """The JSON an empty encoding role costs, for every role this plan leaves empty.

    `"<name>":[]` and a comma, which is what the 114 characters on the declining
    plan and the 87 on the four-bar one are. Built from the role list rather than
    from the fixture's own keys, because a role a fixture omits is an empty role
    too and a grammar-constrained decoder emits it either way.
    """
    filled = plan.get(_PLAN_ENCODINGS) or {}
    return "".join(f'"{role}":[],' for role in roles if not filled.get(role))


def plan_roles() -> tuple[str, ...]:
    """The encoding roles the plan shape declares, read off the shape itself.

    Not a list written here. A role added to `PlanEncodings` is a role a decoder
    starts emitting, and a probe that did not know about it would understate the
    cost of the decision it is measuring.
    """
    return tuple(PlanEncodings.model_fields)


def corpus_bodies(corpus: Path, *, samples: int) -> list[str]:
    """The article body of the first `samples` corpus rows.

    The corpus is the only committed article prose in this repository
    (`CLAUDE.md` section 0a), and article prose is what `truncate_to_tokens`
    cuts - a ratio taken over prompt scaffolding or over definition sentences
    would be a ratio of the wrong text. Bounded by `samples` rather than read
    whole, so the probe costs the same after a year of harvesting as it does
    today (Guardrail #12).
    """
    bodies: list[str] = []
    with corpus.open(encoding="utf-8") as rows:
        for line in rows:
            if len(bodies) >= samples:
                break
            if not line.strip():
                continue
            row = CorpusRow.from_json(line)
            turn = next((one.content for one in row.messages if one.role is ChatRole.USER), None)
            if turn is None or FENCE_OPEN not in turn or FENCE_CLOSE not in turn:
                continue
            opened = turn.index(FENCE_OPEN) + len(FENCE_OPEN)
            inside = turn[opened : turn.index(FENCE_CLOSE)].strip("\n")
            body = inside.partition("\n\n")[2] if inside.startswith("Title: ") else inside
            if body.strip():
                bodies.append(body.strip("\n"))
    return bodies


# --- Taking the three readings ----------------------------------------------


def read_definition_budget(
    tokenizer: CountsTokens, *, config_dir: Path, stamp: dict[str, str]
) -> BudgetReading:
    block, offered = definition_probe(config_dir)
    if not offered:
        raise ValueError(
            f"{config_dir / 'taxonomy.json'} offers no definition to any prompt, so there "
            "is nothing here to size a bound on"
        )
    tokens = tokenizer.count(block)
    return BudgetReading(
        record="DEFINITION_SENTENCE_TOKENS",
        measures=f"{offered} taxonomy definition sentences together, in tokens",
        value=tokens,
        unit="tokens",
        spread=0.0,
        probe=(
            "`Taxonomy.definition_block`, which is the exact block a labelling prompt "
            f"carries: every active entry of {config_dir.name}/taxonomy.json, in the "
            "vocabulary's own order"
        ),
        why_that_probe=(
            "it is the text the bound bounds, and it is the string this pipeline really "
            "sends. Sizing the bound on a join written beside it would size it on prose "
            "no prompt carries, and the two would part the first time the block's layout "
            "moved"
        ),
        probe_size=f"{offered} definition sentences",
        working={
            "entries_offered": offered,
            "tokens": tokens,
            "characters": len(block),
            "tokens_an_entry": round(tokens / offered, 4),
            "characters_an_entry": round(len(block) / offered, 4),
        },
        **stamp,
    )


def read_empty_role_budget(
    tokenizer: CountsTokens, *, fixtures: Path, stamp: dict[str, str]
) -> BudgetReading:
    roles = plan_roles()
    working: dict[str, float] = {"roles_declared": len(roles)}
    widest = 0
    for name in PLAN_PROBES:
        plan = json.loads((fixtures / name).read_text(encoding="utf-8"))
        fragment = empty_role_fragment(plan, roles)
        empty = fragment.count("[]")
        tokens = tokenizer.count(fragment) if fragment else 0
        working[f"{name}_empty_roles"] = empty
        working[f"{name}_characters"] = len(fragment)
        working[f"{name}_tokens"] = tokens
        if empty:
            working[f"{name}_tokens_a_role"] = round(tokens / empty, 4)
        widest = max(widest, tokens)
    return BudgetReading(
        record="EMPTY_ROLE_TOKENS",
        measures="the nine empty encoding roles on a visual plan that declines, in tokens",
        value=widest,
        unit="tokens",
        spread=0.0,
        probe=(
            "the `\"<role>\":[],` fragment for every encoding role each of the two "
            f"committed plan fixtures leaves empty ({', '.join(PLAN_PROBES)})"
        ),
        why_that_probe=(
            "the fixtures are the narrowest and widest plans this pipeline has committed, "
            "and the declining one is where all nine roles are empty - which is what fixes "
            "the per-role rate rather than an average of it"
        ),
        probe_size=f"{len(roles)} encoding roles",
        working=working,
        **stamp,
    )


def read_tokens_a_word(
    tokenizer: CountsTokens, *, corpus: Path, samples: int, stamp: dict[str, str]
) -> BudgetReading:
    bodies = corpus_bodies(corpus, samples=samples)
    if not bodies:
        raise ValueError(
            f"{corpus} yielded no article body in its first {samples} rows, so there is "
            "nothing here to take a ratio over"
        )
    words = sum(len(one.split()) for one in bodies)
    tokens = sum(tokenizer.count(one) for one in bodies)
    return BudgetReading(
        record="TOKENS_A_WORD_AT_THE_CUT",
        measures="tokens a word, used to spend a token cap as a word count at the cut",
        value=round(tokens / words, 4),
        unit="tokens a word",
        spread=0.0,
        probe=f"the article body of the first {len(bodies)} rows of {corpus.name}",
        why_that_probe=(
            "it is the prose `truncate_to_tokens` cuts. The row count is bounded so the "
            "probe costs the same after a year of harvesting, and the ratio is the two "
            "totals divided rather than a mean of per-article ratios, so one short "
            "article cannot weigh as much as one long one"
        ),
        probe_size=f"{len(bodies)} articles, {words:,} words",
        working={"articles": len(bodies), "words": words, "tokens": tokens},
        **stamp,
    )


def take_every_reading(
    tokenizer: CountsTokens,
    *,
    config_dir: Path,
    fixtures: Path,
    corpus: Path,
    samples: int,
    stamp: dict[str, str],
) -> list[BudgetReading]:
    return [
        read_definition_budget(tokenizer, config_dir=config_dir, stamp=stamp),
        read_empty_role_budget(tokenizer, fixtures=fixtures, stamp=stamp),
        read_tokens_a_word(tokenizer, corpus=corpus, samples=samples, stamp=stamp),
    ]


# --- Printing ----------------------------------------------------------------


def format_number(value: float) -> str:
    """Two decimals at most, and no trailing zeros on a whole number.

    No thousands separator. The number goes into a Python source line somebody
    pastes, and `805,000` is a tuple.
    """
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0")


def render_paste(readings: Sequence[BudgetReading]) -> str:
    """The three-line edit each record needs, in the words `measured.py` uses.

    Three lines rather than a whole record, because every other field on the
    record is prose that belongs beside the value in `measured.py` and nowhere
    else. A tool that reprinted that prose would be a second copy of it, and the
    two would disagree the first time one was edited.

    `subject` is left as a placeholder naming the digest rather than guessed. It
    is a named constant in `measured.py`, and this tool can be pointed at a
    candidate's weights, so printing the incumbent's constant name would hand
    somebody a line that says the wrong vocabulary and still compiles.
    """
    subject = readings[0].subject if readings else ""
    lines = [
        "Paste into backend/idhazh/measured.py. Each block replaces three lines on the",
        "record it names and nothing else. Read the record's `measures` first: if the",
        "retake changed what the quantity means, the prose has to move too, and a value",
        "that no longer matches its `measures` is worse than a stale one.",
        "",
        f"`subject` is a named constant, not a string. These were taken against {subject}.",
        "Use the constant that already names those weights, or add one beside",
        "QWEN35_9B_Q4_K_M named for the weights file rather than for a config slot.",
        "",
        "A retake that moves a number deletes the old one. A reading is a variable and",
        "not a log entry, and git history holds what it used to say (Guardrail #10).",
        "",
    ]
    for reading in readings:
        taken = date.fromisoformat(reading.taken_on)
        lines += [
            reading.record,
            f"    value={format_number(reading.value)},",
            f"    taken_on=date({taken.year}, {taken.month}, {taken.day}),",
            "    subject=<the constant naming those weights>,",
            "",
        ]
    return "\n".join(lines)


def render_dossier(readings: Sequence[BudgetReading]) -> str:
    """The dossier section these readings replace, ready to paste as it stands.

    The tool prints the heading, the table and the note, because those are the
    reading restated and a person retyping them is how the last set went stale
    unnoticed. It prints no sentence about *why* a number moved: that is history
    the tool cannot see, it survives a retake, and it is marked here as the
    person's to keep.

    `Taken over` is the load-bearing column. A total can move because the probe
    text moved rather than the vocabulary, so the size sits beside the value and
    neither is quoted alone.
    """
    if not readings:
        return ""
    taken = readings[0].taken_on
    lines = [
        "Paste into docs/reference/models/<the configured model>.md, replacing the",
        "'## What the tokenizer costs' heading down to the end of the note below the",
        "table. Keep the '### Each reading is a point in time' subsection that follows",
        "it: that is the history of what moved and why, it survives a retake, and this",
        "tool cannot see it.",
        "",
        "-----8<-----",
        "",
        "## What the tokenizer costs",
        "",
        "Three counts of **our own text** in this model's vocabulary. Each sizes a budget",
        "the pipeline spends before it reads a single article word, so each one moves when",
        "the weights move.",
        "",
        f"**Taken {taken}** against these weights, by",
        "`python backend/utilities/measure_budgets.py read`, which asks the running",
        "`llama-server` to tokenize the exact text the pipeline sends.",
        "",
        "| Quantity | Reading | Taken over | What it measures |",
        "| --- | --- | --- | --- |",
    ]
    for reading in readings:
        value = f"{format_number(reading.value)} {reading.unit}"
        lines.append(
            f"| `{reading.record}` | {value} | {reading.probe_size} | {reading.measures} |"
        )
    lines += [
        "",
        "**Spread is 0 on all three, and is printed rather than left out.** A tokenizer",
        "over fixed text returns the identical count every time, so there is nothing to",
        "repeat - but a reading with no spread field would read as one that forgot to take",
        "it (Guardrail #10).",
        "",
        "-----8<-----",
        "",
    ]
    return "\n".join(lines)


def render_readings(readings: Iterable[BudgetReading]) -> str:
    """What was counted, what it was divided by, and what text was tokenized."""
    lines: list[str] = []
    for reading in readings:
        working = ", ".join(
            f"{key} {format_number(value)}" for key, value in reading.working.items()
        )
        lines += [
            f"{reading.record} = {format_number(reading.value)} {reading.unit} "
            f"(spread {format_number(reading.spread)})",
            f"  measures       {reading.measures}",
            f"  probe          {reading.probe}",
            f"  why that text  {reading.why_that_probe}",
            f"  working        {working}",
            f"  subject        {reading.subject}",
            f"  taken          {reading.taken_on} on {reading.runner}",
            "",
        ]
    lines += [
        "Spread is 0 on all three and is printed rather than omitted. A tokenizer is",
        "deterministic, so the same probe text on the same weights returns the identical",
        "count every time - there is nothing to repeat. A reading with no spread field at",
        "all would read as one that forgot to take it.",
        "",
    ]
    return "\n".join(lines)


def render_check(stale: Sequence[Unreached], configured: str) -> str:
    """What `check` says, whether or not anything is stale."""
    if not stale:
        return (
            f"Every constant sized by a reading names the configured weights ({configured}).\n"
            f"{len(SIZED_BY_A_READING_HERE)} checked."
        )
    sites = "\n".join(describe_a_retake(site) for site in stale)
    return (
        f"{len(stale)} of {len(SIZED_BY_A_READING_HERE)} constants sized by a reading were "
        "sized on weights this repository no longer runs.\n"
        f"the configured weights are {configured}\n"
        f"{sites}\n"
        "Retake them: start llama-server on the configured weights, then\n"
        "  python backend/utilities/measure_budgets.py read --runner <where you ran it>\n"
        "and paste what it prints into backend/idhazh/measured.py. A retake that moves a\n"
        "number deletes the old one (Guardrail #10)."
    )


# --- The verbs ---------------------------------------------------------------


def run_check(args: argparse.Namespace) -> int:
    configured = config.load(args.config).models.summarize.sha256
    if configured is None:
        print("the configured summarizer names no weights digest", file=sys.stderr)
        return 2
    stale = readings_awaiting_a_retake(configured_sha256=configured)
    print(render_check(stale, configured))
    return 1 if stale else 0


def run_read(args: argparse.Namespace) -> int:
    subject = args.subject or config.load(args.config).models.summarize.sha256
    if subject is None:
        print(
            "no weights digest to stamp the readings with: pass --subject, or configure "
            "one on models.summarize",
            file=sys.stderr,
        )
        return 2
    stamp = {
        "subject": subject,
        "runner": args.runner,
        "taken_on": (args.taken_on or date.today()).isoformat(),
    }
    tokenizer = Tokenizer(base=args.base, timeout=args.timeout)
    try:
        readings = take_every_reading(
            tokenizer,
            config_dir=args.config,
            fixtures=args.fixtures,
            corpus=args.corpus,
            samples=args.samples,
            stamp=stamp,
        )
    except (ServerSilentError, ValueError) as refused:
        print(str(refused), file=sys.stderr)
        return 2

    body = f"{render_readings(readings)}\n{render_paste(readings)}\n{render_dossier(readings)}"
    print(body)
    if args.readings is not None:
        args.readings.parent.mkdir(parents=True, exist_ok=True)
        args.readings.write_text(
            json.dumps([one.as_json() for one in readings], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if args.page is not None:
        args.page.parent.mkdir(parents=True, exist_ok=True)
        args.page.write_text(body + "\n", encoding="utf-8", newline="\n")
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    verbs = parser.add_subparsers(dest="verb", required=True)

    check = verbs.add_parser("check", help="say which sized constants name retired weights")
    check.add_argument("--config", type=Path, default=CONFIG_DIR)

    read = verbs.add_parser("read", help="retake all three against a running server")
    read.add_argument("--base", default="http://127.0.0.1:8080")
    read.add_argument("--config", type=Path, default=CONFIG_DIR)
    read.add_argument("--fixtures", type=Path, default=PLAN_FIXTURES)
    read.add_argument("--corpus", type=Path, default=CORPUS)
    read.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    read.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    read.add_argument("--subject", default=None, help="weights digest; defaults to the config's")
    read.add_argument(
        "--runner",
        required=True,
        help="where this ran, for the record's provenance - a runner class or a box",
    )
    read.add_argument("--taken-on", dest="taken_on", type=date.fromisoformat, default=None)
    read.add_argument("--readings", type=Path, default=None, help="write the readings as JSON")
    read.add_argument("--page", type=Path, default=None, help="write the printed body to a file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run_check(args) if args.verb == "check" else run_read(args)


if __name__ == "__main__":
    raise SystemExit(main())
