"""The offline write-critique-revise prompt loop. Operator tooling, never the pipeline.

The summariser prompt used to be argued in prose and never measured. This turns
the argument into a measurement: a model judge and the Editor rubric PROPOSE a
revised prompt, and the deterministic, model-free scorers DISPOSE. A candidate
replaces the incumbent only when it beats the incumbent on those scorers over a
frozen article set. The judge proposes; the scorers dispose.

Four things here are controls, and each one is a specific failure that cannot
happen because of it:

- **The gate is deterministic.** Promotion is decided by `beats_incumbent`, which
  reads only the model-free scorers in `idhazh.evals.metrics`. The model judge's
  preference is recorded and never promotes anything. A model that shares a
  summary's failure modes cannot wave its own output through (CLAUDE.md section
  0a, the LLM-as-judge non-goal).
- **`new_fact_rate` is recorded, never a gate target.** A metric used to choose an
  output can no longer detect that outputs are getting worse. The new-fact rate
  is read to report and never to select - best-of-N against it is the Goodhart
  form the metric's own contract forbids (`idhazh.evals.metrics.new_fact_rate`).
- **It runs offline.** The frozen set is committed article text. The loop makes no
  open-web fetch (Rule #7); its only network call is to a local model server on
  loopback. It runs on a developer machine or a manual dispatch and is never
  imported by the pipeline, so it can never sit on the daily critical path.
- **Nothing it writes reaches a reader.** The winning prompt, the rubric, the
  scores of every candidate and the seed are the artefacts. Promoting a winner
  into `backend/idhazh/prompts/summarize.txt` is a human act, taken after reading
  the deterministic scores. The loop never edits the live prompt itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Final, Protocol

from idhazh import config, summarize
from idhazh.contracts.app_config import SummarizeConfig
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.evals.metrics import (
    hedge_dropped,
    lead_coverage,
    new_fact_rate,
    unsupported_numbers,
    verbatim_run,
)
from idhazh.llm.server import DEFAULT_ENDPOINT, post, props, request_payload

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
RUBRIC_PATH: Final = Path(__file__).parent / "prompt_loop_rubric.md"
INCUMBENT_PROMPT_PATH: Final = REPO_ROOT / "backend" / "idhazh" / "prompts" / "summarize.txt"
DEFAULT_FROZEN_SET: Final = REPO_ROOT / "tests" / "fixtures" / "contracts" / "article"
DEFAULT_OUTPUT_ROOT: Final = REPO_ROOT / "backend" / "var" / "prompt-loop"

# Float noise guard for the gate comparisons. The scorecard averages integers and
# ratios over the frozen set, so a genuine tie must not read as a strict beat.
_EPS: Final = 1e-9


# --- The frozen set and one produced summary --------------------------------


@dataclass(frozen=True)
class FrozenItem:
    """One article a prompt is scored against.

    Source text only. The loop generates the summary, so nothing here is a
    reference answer - the frozen set is the questions, never the answers.
    """

    key: str
    source: str


@dataclass(frozen=True)
class ItemSummary:
    """What a summariser produced for one frozen item under one prompt."""

    key: str
    summary: str
    key_points: tuple[str, ...]


# --- The deterministic scorecard (the DISPOSE) ------------------------------

#: The gate reads these four, and only these four. Every one is a defect rate
#: where lower is better, and none needs a model, a label, or a network call.
#: `new_fact_rate` is deliberately absent: it is recorded on the scorecard and is
#: never a gate target (see the module docstring and `beats_incumbent`).
GATE_TARGETS: Final[tuple[str, ...]] = (
    "unsupported_numbers",
    "lead_missing_rate",
    "hedge_dropped_rate",
    "verbatim_run",
)


@dataclass(frozen=True)
class Scorecard:
    """The deterministic reading of one prompt over the whole frozen set.

    The four gate fields are defect rates: lower is better. `new_fact_rate` sits
    beside them and is NOT a gate field - acting on it is the Goodhart form the
    metric's own contract forbids, so the loop reads it to report and never to
    choose.
    """

    unsupported_numbers: float
    lead_missing_rate: float
    hedge_dropped_rate: float
    verbatim_run: float
    new_fact_rate: float

    def gate_values(self) -> dict[str, float]:
        """The four numbers the gate compares. `new_fact_rate` is not among them."""
        return {name: float(getattr(self, name)) for name in GATE_TARGETS}

    def as_row(self) -> dict[str, float]:
        """Every number on the card, for the committed scores artefact."""
        return {
            "unsupported_numbers": self.unsupported_numbers,
            "lead_missing_rate": self.lead_missing_rate,
            "hedge_dropped_rate": self.hedge_dropped_rate,
            "verbatim_run": self.verbatim_run,
            "new_fact_rate": self.new_fact_rate,
        }


def score_prompt(
    summaries: Sequence[ItemSummary],
    items: Sequence[FrozenItem],
    *,
    lead_coverage_min: float,
    restatement_ceiling: float,
) -> Scorecard:
    """Reduce a prompt's summaries over the frozen set to one deterministic card.

    `lead_coverage_min` is `evaluation.lead_coverage_min` - the same threshold the
    published band reason `lead_missing` uses, so the loop steers by the defect a
    reader is told about. `restatement_ceiling` is
    `summarize.key_point_restatement_ceiling`, the distinctness floor
    `new_fact_rate` is measured against.
    """
    by_key = {item.key: item.source for item in items}
    total = len(summaries)
    if total == 0:
        return Scorecard(0.0, 0.0, 0.0, 0.0, 0.0)
    unsupported = 0.0
    lead_missing = 0
    hedged = 0
    copied = 0.0
    new_facts = 0.0
    for produced in summaries:
        source = by_key[produced.key]
        unsupported += unsupported_numbers(produced.summary, source)
        if lead_coverage(produced.summary, source) < lead_coverage_min:
            lead_missing += 1
        if hedge_dropped(produced.summary, source):
            hedged += 1
        copied += verbatim_run(produced.summary, source)
        new_facts += new_fact_rate(
            list(produced.key_points), produced.summary, ceiling=restatement_ceiling
        )
    return Scorecard(
        unsupported_numbers=unsupported / total,
        lead_missing_rate=lead_missing / total,
        hedge_dropped_rate=hedged / total,
        verbatim_run=copied / total,
        new_fact_rate=new_facts / total,
    )


def beats_incumbent(candidate: Scorecard, incumbent: Scorecard) -> bool:
    """The gate, and the whole promotion decision.

    True iff the candidate is no worse than the incumbent on EVERY gate target and
    strictly better on at least one - a Pareto beat over the deterministic
    scorers, not an optimiser and not a weighted sum. It never reads
    `new_fact_rate`: a candidate cannot win by moving a number nothing is allowed
    to steer by.
    """
    cand = candidate.gate_values()
    inc = incumbent.gate_values()
    no_worse = all(cand[name] <= inc[name] + _EPS for name in GATE_TARGETS)
    strictly_better = any(cand[name] < inc[name] - _EPS for name in GATE_TARGETS)
    return no_worse and strictly_better


# --- The two judges ---------------------------------------------------------


class Summarizer(Protocol):
    """Produce a summary per frozen item under a given prompt.

    The live implementation calls a local model server; a recorded one (the
    tests) returns fixtures. Either way the loop fetches nothing from the open
    web (Rule #7).
    """

    def summarize(self, prompt: str, items: Sequence[FrozenItem]) -> list[ItemSummary]: ...


class Judge(Protocol):
    """The MODEL judge. It PROPOSES a revised prompt and may state a preference.

    It never decides promotion - the deterministic gate does. `prefers_candidate`
    is recorded so a run can show where the judge and the scorers disagreed, and
    a disagreement is always resolved in the scorers' favour.
    """

    def revise(
        self, prompt: str, rubric: str, scores: Scorecard, round_index: int
    ) -> str: ...

    def prefers_candidate(self, incumbent: str, candidate: str, rubric: str) -> bool: ...


# --- The loop ---------------------------------------------------------------


@dataclass(frozen=True)
class Round:
    """One iteration's record. Committed as a score row, never as a transcript."""

    index: int
    prompt: str
    scores: Scorecard
    judge_preferred: bool
    beat_incumbent: bool
    promoted: bool


@dataclass(frozen=True)
class LoopResult:
    """What the run decided, and every candidate's scores behind it."""

    winning_prompt: str
    winning_scores: Scorecard
    incumbent_scores: Scorecard
    rounds: tuple[Round, ...]
    seed: int
    promoted: bool


def run_loop(
    *,
    incumbent_prompt: str,
    items: Sequence[FrozenItem],
    summarizer: Summarizer,
    judge: Judge,
    rubric: str,
    iterations: int,
    lead_coverage_min: float,
    restatement_ceiling: float,
    seed: int,
) -> LoopResult:
    """Write-critique-revise, bounded by `iterations`.

    Returns the winning prompt, which is the incumbent unless a candidate BEAT it
    on the deterministic gate. A disagreement is a stop: when the model judge
    prefers a candidate the deterministic suite refuses, the incumbent stays. The
    promotion on every round is `beats_incumbent(...)` alone - the judge's
    preference is recorded and never consulted for the decision.
    """
    scored = _score(summarizer, incumbent_prompt, items, lead_coverage_min, restatement_ceiling)
    winning_prompt = incumbent_prompt
    winning_scores = scored
    incumbent_scores = scored
    rounds: list[Round] = []
    promoted_any = False
    for index in range(iterations):
        candidate = judge.revise(winning_prompt, rubric, winning_scores, index)
        candidate_scores = _score(
            summarizer, candidate, items, lead_coverage_min, restatement_ceiling
        )
        judge_preferred = judge.prefers_candidate(winning_prompt, candidate, rubric)
        # Promotion is the gate's call, and only the gate's. `judge_preferred` is
        # recorded on the round and is never read here.
        promoted = beats_incumbent(candidate_scores, winning_scores)
        rounds.append(
            Round(
                index=index,
                prompt=candidate,
                scores=candidate_scores,
                judge_preferred=judge_preferred,
                beat_incumbent=promoted,
                promoted=promoted,
            )
        )
        if promoted:
            winning_prompt = candidate
            winning_scores = candidate_scores
            promoted_any = True
    return LoopResult(
        winning_prompt=winning_prompt,
        winning_scores=winning_scores,
        incumbent_scores=incumbent_scores,
        rounds=tuple(rounds),
        seed=seed,
        promoted=promoted_any,
    )


def _score(
    summarizer: Summarizer,
    prompt: str,
    items: Sequence[FrozenItem],
    lead_coverage_min: float,
    restatement_ceiling: float,
) -> Scorecard:
    return score_prompt(
        summarizer.summarize(prompt, items),
        items,
        lead_coverage_min=lead_coverage_min,
        restatement_ceiling=restatement_ceiling,
    )


# --- The live implementations (the bounded run) -----------------------------


def render_system(
    template_text: str, ask: SummarizeConfig, *, source_words: int, brief: bool
) -> str:
    """Render a candidate prompt template the way the pipeline renders the live one.

    Mirrors `summarize.system_prompt`: the same band is chosen by source length,
    the same config numbers are substituted, and `substitute` (never
    `safe_substitute`) so a candidate that misspells a placeholder raises here
    rather than sending `$target_words_max` to a model as if it were an
    instruction.
    """
    band = ask.band_for(0 if brief else source_words)
    return Template(template_text).substitute({**ask.model_dump(), **band.model_dump()})


class LiveSummarizer:
    """Summarise each frozen article by calling a local model server.

    Reuses `summarize.build_request` for the schema, the fenced user turn and the
    inference settings, then swaps in the candidate system prompt. No open-web
    fetch; the only call is to loopback.
    """

    def __init__(self, *, settings: config.Settings, articles: Sequence[Article], endpoint: str):
        self._settings = settings
        self._articles = {_article_key(article): article for article in articles}
        self._endpoint = endpoint

    def summarize(self, prompt: str, items: Sequence[FrozenItem]) -> list[ItemSummary]:
        ask = self._settings.app.summarize
        evaluation = self._settings.app.evaluation
        inference = self._settings.app.models.inference
        model_id = self._settings.app.models.summarize.id
        produced: list[ItemSummary] = []
        for item in items:
            article = self._articles[item.key]
            payload = summarize.build_request(
                article,
                model_id=model_id,
                inference=inference,
                prompt_config=ask,
                evaluation=evaluation,
            )
            payload["messages"][0]["content"] = render_system(
                prompt, ask, source_words=article.band_source_words, brief=article.brief
            )
            completion = post(
                payload, endpoint=self._endpoint, timeout=inference.request_timeout_minutes * 60
            )
            draft = summarize.parse_draft(
                completion.content,
                prompt_config=ask,
                evaluation=evaluation,
                source_words=article.band_source_words,
                brief=article.brief,
            )
            produced.append(
                ItemSummary(
                    key=item.key, summary=draft.summary, key_points=tuple(draft.key_points)
                )
            )
        return produced


_REVISE_SCHEMA: Final[dict[str, object]] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"revised_prompt": {"type": "string", "minLength": 1}},
    "required": ["revised_prompt"],
}

_PREFERENCE_SCHEMA: Final[dict[str, object]] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"prefers_candidate": {"type": "boolean"}},
    "required": ["prefers_candidate"],
}

_JUDGE_SYSTEM: Final = (
    "You are an editor improving the SYSTEM PROMPT a summariser is given. You are "
    "not writing a summary and not judging any published work. You propose a "
    "revised prompt that will make summaries follow the rubric better. Keep every "
    "$placeholder token exactly as written - they are substituted from config. "
    "Reply only in the requested JSON shape."
)


class ModelJudge:
    """The live model judge. It proposes a revised prompt and states a preference.

    Both replies are shape-constrained by the decoder, so an unexpected reply
    fails to parse rather than reaching the loop. The preference is advisory - the
    loop records it and promotes on the deterministic gate regardless.
    """

    def __init__(self, *, settings: config.Settings, endpoint: str):
        self._settings = settings
        self._endpoint = endpoint

    def revise(self, prompt: str, rubric: str, scores: Scorecard, round_index: int) -> str:
        user = (
            f"Round {round_index}. The rubric:\n\n{rubric}\n\n"
            f"The current prompt:\n\n{prompt}\n\n"
            f"The current deterministic scores (lower is better on the gate "
            f"targets): {json.dumps(scores.as_row())}\n\n"
            "Propose a revised prompt that keeps every $placeholder and reads as a "
            "complete system prompt."
        )
        reply = self._call(user, _REVISE_SCHEMA, "prompt_revision")
        revised = reply.get("revised_prompt")
        if not isinstance(revised, str) or not revised.strip():
            raise ValueError("the judge returned no revised_prompt")
        return revised

    def prefers_candidate(self, incumbent: str, candidate: str, rubric: str) -> bool:
        user = (
            f"The rubric:\n\n{rubric}\n\n"
            f"Prompt A (incumbent):\n\n{incumbent}\n\n"
            f"Prompt B (candidate):\n\n{candidate}\n\n"
            "Does prompt B follow the rubric better than prompt A?"
        )
        reply = self._call(user, _PREFERENCE_SCHEMA, "prompt_preference")
        return bool(reply.get("prefers_candidate", False))

    def _call(self, user: str, schema: dict[str, object], schema_name: str) -> dict[str, object]:
        inference = self._settings.app.models.inference
        payload = request_payload(
            model_id=self._settings.app.models.summarize.id,
            system=_JUDGE_SYSTEM,
            user=user,
            output_schema=schema,
            inference=inference,
            schema_name=schema_name,
        )
        completion = post(
            payload, endpoint=self._endpoint, timeout=inference.request_timeout_minutes * 60
        )
        parsed = json.loads(completion.content)
        if not isinstance(parsed, dict):
            raise ValueError("the judge returned a non-object reply")
        return parsed


# --- Loading the frozen set and writing the artefacts -----------------------


def _article_key(article: Article) -> str:
    """A stable key for a frozen article: its source address, always present."""
    return str(article.source_url)


def load_frozen_articles(directory: Path) -> tuple[list[Article], list[FrozenItem]]:
    """Read committed `Article` payloads into a frozen set.

    Only articles that fetched and carry body text are kept: a fetch failure or an
    empty body is not something a summariser prompt can be scored on. The set is a
    fixed, committed directory, so the loop reads a bounded input and never a
    collection that grows with the archive (Rule #12).
    """
    articles: list[Article] = []
    items: list[FrozenItem] = []
    for path in sorted(directory.glob("*.json")):
        article = Article.from_json(path.read_bytes().decode("utf-8"))
        if article.status is not ArticleStatus.OK or not article.text:
            continue
        articles.append(article)
        items.append(FrozenItem(key=_article_key(article), source=article.text))
    return articles, items


def write_run(result: LoopResult, out_dir: Path, *, rubric_path: Path) -> None:
    """Write the committed artefacts: the scores of every candidate, the winning
    prompt, the seed, and the rubric that was used. Never the transcripts.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    scores = {
        "seed": result.seed,
        "promoted": result.promoted,
        "gate_targets": list(GATE_TARGETS),
        "incumbent": result.incumbent_scores.as_row(),
        "rounds": [
            {
                "index": round_.index,
                "scores": round_.scores.as_row(),
                "judge_preferred": round_.judge_preferred,
                "beat_incumbent": round_.beat_incumbent,
                "promoted": round_.promoted,
            }
            for round_ in result.rounds
        ],
        "winning": result.winning_scores.as_row(),
    }
    (out_dir / "scores.json").write_bytes(
        (json.dumps(scores, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    )
    (out_dir / "winning-prompt.txt").write_bytes(result.winning_prompt.encode("utf-8"))
    (out_dir / "rubric.md").write_bytes(rubric_path.read_bytes())


# --- The CLI ----------------------------------------------------------------


def _format_verdict(result: LoopResult) -> str:
    lines = [
        f"seed {result.seed}, {len(result.rounds)} round(s)",
        "gate targets (lower is better): " + ", ".join(GATE_TARGETS),
    ]
    for round_ in result.rounds:
        gate = round_.scores.gate_values()
        gate_text = " ".join(f"{name}={gate[name]:.4f}" for name in GATE_TARGETS)
        lines.append(
            f"round {round_.index}: {gate_text} "
            f"| judge_preferred={round_.judge_preferred} "
            f"| beat_incumbent={round_.beat_incumbent}"
        )
    if result.promoted:
        lines.append("verdict: a candidate beat the incumbent. Review scores.json, then")
        lines.append("commit the winning prompt into summarize.txt by hand if it holds.")
    else:
        lines.append("verdict: the incumbent stands. No candidate beat it on the gate.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    settings = config.load()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=settings.app.finetune.prompt_iterations,
        help="Rounds to run. Defaults to finetune.prompt_iterations.",
    )
    parser.add_argument(
        "--frozen-set",
        type=Path,
        default=DEFAULT_FROZEN_SET,
        help="Directory of committed Article payloads to score against.",
    )
    parser.add_argument(
        "--max-items", type=int, default=0, help="Cap the frozen set (0 means all)."
    )
    parser.add_argument("--seed", type=int, default=0, help="Recorded, for reproducibility.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Where to write the artefacts. Defaults to backend/var/prompt-loop/<timestamp>.",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Local model server endpoint.")
    args = parser.parse_args(argv)

    articles, items = load_frozen_articles(args.frozen_set)
    if args.max_items > 0:
        articles, items = articles[: args.max_items], items[: args.max_items]
    if not items:
        print(f"no usable articles under {args.frozen_set}", file=sys.stderr)
        return 2

    if not props(args.endpoint, timeout=5.0):
        print(
            "the local model server is not reachable, so the live run was skipped.\n"
            "the loop's gate and the disagreement oracle are proven by the fixture\n"
            "tests in backend/tests/test_prompt_loop.py - no model is needed for those.",
            file=sys.stderr,
        )
        return 0

    incumbent_prompt = INCUMBENT_PROMPT_PATH.read_bytes().decode("utf-8")
    rubric = RUBRIC_PATH.read_bytes().decode("utf-8")
    summarizer = LiveSummarizer(settings=settings, articles=articles, endpoint=args.endpoint)
    judge = ModelJudge(settings=settings, endpoint=args.endpoint)

    result = run_loop(
        incumbent_prompt=incumbent_prompt,
        items=items,
        summarizer=summarizer,
        judge=judge,
        rubric=rubric,
        iterations=args.iterations,
        lead_coverage_min=settings.app.evaluation.lead_coverage_min,
        restatement_ceiling=settings.app.summarize.key_point_restatement_ceiling,
        seed=args.seed,
    )

    out_dir = args.out or DEFAULT_OUTPUT_ROOT / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    write_run(result, out_dir, rubric_path=RUBRIC_PATH)
    print(_format_verdict(result))
    try:
        shown = out_dir.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = out_dir.as_posix()
    print(f"artefacts: {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
