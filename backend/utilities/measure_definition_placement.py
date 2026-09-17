"""Price the 30 definition sentences the labelling prompt is about to carry.

Putting the definitions in the shared system turn spends about 1,000 tokens of
every prompt this pipeline sends, on every item, for ever. It is the right
placement - the shared system turn costs 1.4 minutes a shard where the user turn
costs 27.3 - but that answers where the definitions go and not whether they are
worth carrying. **Nobody has measured what they buy.** This is the instrument
that does.

Three mechanisms are live and none of them has a reading.

- **Context dilution.** A thousand tokens of definition in front of the article
  is a thousand tokens of attention spent on text that is identical for every
  item.
- **Ordering.** A model asked to pick from a list is not indifferent to the
  list's order. The permuted case is the one worth the run: if permuting moves
  the answer, the definitions are being read as an ordering and not as
  definitions, and every figure the other three produce is about the list rather
  than about the words in it.
- **Cross-task interference.** Definitions in the shared turn sit in front of
  the summariser on both calls, and the summary is what a reader reads. That case
  scores summaries rather than labels, because a label nobody sees going one
  percent better does not pay for a summary going worse.

**A cheaper prompt that scores the same is the answer. A cheaper prompt that
scores worse is the cost the ruling pays knowingly.** Either way the number
exists afterwards, which it did not before.

**What it takes today, and what it refuses to.** The cost side runs on a clean
clone with no weights and no network: the four variants are built from
`Taxonomy.definition_block()` and measured. The agreement side needs two things
this tree does not have yet - a GGUF under `backend/models/`, and a `labels.desk`
column somebody filled in `corpus/reference-dataset-1/dataset.jsonl`, which is
null on all 641 rows as of 2026-09-13. It refuses by name rather than printing a
clean zero, because an unlabelled set scores 0.0 percent on all four variants and
that reads as a finding.

**It is an operator tool and never a test.** The agreement case needs a
multi-gigabyte GGUF that `backend/models/` does not commit and a `llama-server`
binary that `backend/bin/` does not either, and it runs a real model for minutes
(`CLAUDE.md` section 13). Nothing in CI calls it.
`backend/utilities/measure_two_calls.py` is the precedent and the shape is
deliberately the same one.

**Nothing it produces selects what publishes or grades a published summary.**
The four label cases score a model's answer against a human's, which is a
measurement of the model and not a verdict on an item; the summary case scores
`idhazh.evals.metrics`, which are deterministic and model-free. `CLAUDE.md`
section 0a.

    python backend/utilities/measure_definition_placement.py
    python backend/utilities/measure_definition_placement.py --agreement \\
        --binary backend/bin/llama-server.exe \\
        --weights backend/models/Qwen3.5-9B-Q4_K_M.gguf
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "backend")]

from idhazh import config  # noqa: E402
from idhazh.contracts.taxonomy import Taxonomy  # noqa: E402

DATASET: Final = REPO_ROOT / "corpus" / "reference-dataset-1" / "dataset.jsonl"
DEV_SPLIT: Final = REPO_ROOT / "corpus" / "reference-dataset-1" / "splits" / "dev.txt"

#: The four ways the same vocabulary can reach the model, cheapest first. The
#: order is the order the report prints them in, and it is cheapest-first on
#: purpose: the question this answers is what the expensive end buys, so the
#: cheap end is the baseline and not an afterthought.
VARIANTS: Final = ("ids_only", "one_line", "full", "full_permuted")

#: What the label cases agree or disagree about. Both are top-1 - one answer, one
#: right answer - because a set-valued vocabulary like the lenses turns
#: agreement into a similarity measure and a similarity measure needs its own
#: argument about the threshold.
FIELDS: Final = ("desk", "article_kind")


class NoLabelsError(RuntimeError):
    """The dev split carries no human labels, so there is nothing to agree with."""


@dataclass(frozen=True)
class Agreement:
    """One variant's reading: how often the model's top answer was the human's."""

    variant: str
    field: str
    agreed: int
    scored: int

    @property
    def rate(self) -> float:
        return self.agreed / self.scored if self.scored else 0.0

    def line(self) -> str:
        return (
            f"{self.variant:>14}  {self.field:>13}  "
            f"{self.rate:6.1%}  ({self.agreed} of {self.scored})"
        )


def dev_rows() -> list[dict[str, Any]]:
    """The dev split of the frozen reference set, as rows.

    The dev split rather than the whole set, because the test split is the one
    that has to stay unseen. Both are committed lists of `url_key`, so this
    reads two files by name and never walks the corpus.
    """
    wanted = set(DEV_SPLIT.read_text(encoding="utf-8").split())
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]
    return [row for row in rows if row["url_key"] in wanted]


def labelled(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows a human has answered, which is what agreement is measured against.

    **It refuses rather than reporting zero.** An unlabelled reference set
    produces a clean 0.0 percent on all four variants, which reads as a finding
    and is an empty file. The refusal names the two things that fill it.
    """
    answered = [row for row in rows if row.get("labels", {}).get("desk")]
    if not answered:
        raise NoLabelsError(
            "the dev split carries no human labels, so top-1 agreement has nothing to "
            "agree with. Fill them with `python backend/utilities/label_queue.py` and "
            "re-run; every `labels.desk` in corpus/reference-dataset-1/dataset.jsonl is "
            "null today"
        )
    return answered


def definition_text(taxonomy: Taxonomy, variant: str, *, seed: int = 7) -> str:
    """The vocabulary, written the way this variant writes it.

    All four are built from `Taxonomy.definition_block()` rather than from four
    hand-written strings, so the cases differ in exactly the dimension being
    measured and in nothing else. A hand-written cheap variant would also be a
    differently worded one, and the reading would carry both changes with no way
    to tell them apart.
    """
    block = taxonomy.definition_block()
    if variant == "full":
        return block
    if variant == "full_permuted":
        lines = block.splitlines()
        entries = [line for line in lines if line.startswith("- ")]
        shuffled = list(entries)
        random.Random(seed).shuffle(shuffled)
        moved = iter(shuffled)
        return "\n".join(next(moved) if line.startswith("- ") else line for line in lines)
    trimmed: list[str] = []
    for line in block.splitlines():
        if not line.startswith("- "):
            trimmed.append(line)
            continue
        head, _, tail = line.partition("): ")
        if variant == "ids_only":
            trimmed.append(f"{head})")
        else:
            trimmed.append(f"{head}): {tail.split('. ')[0].rstrip('.')}.")
    return "\n".join(trimmed)


def variant_sizes(taxonomy: Taxonomy) -> dict[str, int]:
    """Each variant's size in characters, which is what a run has to convert.

    Characters rather than tokens, because a token count needs the tokenizer
    that belongs to the weights and this half of the tool runs without them.
    This is the cheap half and it is the half that works today: it says what the
    four variants cost, which is one side of the trade the ruling made. The
    other side is agreement, and it needs a model and a filled label column.
    """
    return {variant: len(definition_text(taxonomy, variant)) for variant in VARIANTS}


def report(readings: Sequence[Agreement], sizes: dict[str, int]) -> str:
    """The figures, each beside the variant that produced it.

    Printed as one block so it can be pasted into a pull request body whole,
    which is where the row's acceptance gate says these numbers go. A figure
    without the variant beside it is not a reading of anything.

    **An empty agreement table prints nothing rather than a heading.** A heading
    over no rows reads as a measurement that came back zero, and the reason
    there are no rows is that the reading was refused.
    """
    lines = ["definition text, characters a call carries"]
    lines.extend(f"{variant:>14}  {size:>6}" for variant, size in sizes.items())
    if not readings:
        return "\n".join(lines)
    lines.extend(["", "top-1 agreement against the human labels", ""])
    lines.append(f"{'variant':>14}  {'field':>13}  {'agreed':>6}")
    lines.extend(reading.line() for reading in readings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, help="a llama-server executable")
    parser.add_argument("--weights", type=Path, help="the GGUF config/idhazh.json names")
    parser.add_argument(
        "--agreement",
        action="store_true",
        help="take the four-variant agreement reading, which needs weights and human labels",
    )
    args = parser.parse_args(argv)

    taxonomy = config.load(REPO_ROOT / "config").taxonomy
    sizes = variant_sizes(taxonomy)
    if not args.agreement:
        print(report([], sizes))
        return 0

    if not args.binary or not args.weights:
        parser.error("--agreement needs --binary and --weights")
    missing = [named for named in (args.binary, args.weights) if not named.exists()]
    if missing:
        print(
            "the agreement case needs a real model and these are not on disk: "
            + ", ".join(named.as_posix() for named in missing),
            file=sys.stderr,
        )
        return 2

    try:
        rows = labelled(dev_rows())
    except NoLabelsError as empty:
        print(str(empty), file=sys.stderr)
        return 3

    print(report(list(_agreement(rows, taxonomy)), sizes))
    return 0


def _agreement(rows: Sequence[dict[str, Any]], taxonomy: Taxonomy) -> Iterable[Agreement]:
    """The reading, once the labelling prompt exists to take it with.

    **It refuses instead of guessing at the prompt.** The four variants differ
    only in the definition text, and the turn that text rides in is the labelling
    prompt, which nothing builds yet. Inventing one here would measure a prompt
    this pipeline never sends, and a number taken against the wrong prompt is
    worse than no number: it looks like evidence.
    """
    raise NotImplementedError(
        f"{len(rows)} labelled rows and {len(taxonomy.verticals)} desks are ready, and the "
        "labelling prompt is not - nothing builds the turn these definitions ride in yet. "
        "Take this reading once something does, with the prompt the pipeline actually sends"
    )


if __name__ == "__main__":
    raise SystemExit(main())
