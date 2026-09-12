"""Say where every token call 2 had to read again went.

Row 3's first reading printed `FLOOR BROKEN - 4 tokens` while 670 tokens an item
burned with no reading at all. The floor was a boolean watching the smaller of
two wastes, and its alarm fired on the good case - which teaches its reader to
discount it on the bad one. **A number that is not decomposed is a number nobody
can act on**, so this reports three numbers that sum to the total instead.

**The three causes, and each one belongs to somebody.**

- **The article changed.** Call 1 on a new item reads a new article. Irreducible:
  no prompt layout removes it, and it is the cost the design exists to pay.
- **The chat template broke the prefix.** It used to: call 2 replayed call 1's
  turns as history, the template rendered them differently, and everything
  behind the divergence prefilled again. Row #3c renders the prompt bytes
  itself, so what is left here is a token seam rather than a layout - measured
  at 1 token an item against the 100 the template cost. **The row stays on the
  page reading about zero** - a cause that is printed is a cause a build change
  or a prompt edit cannot reintroduce quietly, and a deleted row catches
  nothing.
- **The trailing turn sits behind the article.** Call 2's question is the same
  bytes on every item, but the article in front of it is not, so a prefix cache
  cannot reach it and every token of it is read again, for ever. Row #3e moved
  both jobs into the system turn and left three lines behind - measured at 42
  tokens an item against the 692 the whole question cost. **The row stays on the
  page for the reason the template row does**: what is printed cannot come back
  quietly.

**Two items, not one.** One item is a cold cache slot and a cold slot is not the
steady state a shard spends its life in. On item 2 the system turn should be
served from cache and item 1's copy of call 2's question should be gone. A third
item runs call 1 on its real output budget, because the template cause is call
1's reply length plus the divergence, and a decode cap hides it.

**It refuses a weights file `config/` does not name.** The reading this replaces
was taken on a retired model and nobody noticed, because the tool read the
inference block from config and the weights from the command line and never
compared the two.

It is an operator tool and never a test: it needs a multi-gigabyte GGUF that
`backend/models/` does not commit, and it runs a real model for minutes
(`CLAUDE.md` section 13). Nothing in CI calls it. The arithmetic it prints is
tested from recorded replies in `backend/tests/test_measure_two_calls.py`.

    python backend/utilities/measure_two_calls.py \
        --binary backend/bin/llama-server.exe \
        --weights backend/models/Qwen3.5-9B-Q4_K_M.gguf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from idhazh import config
from idhazh.classify.calls import (
    build_call_one_request,
    build_call_two_request,
    call_one_system_prompt,
    call_two_output_tokens,
    call_two_user_turn,
)
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.corpus import ChatRole, CorpusRow
from idhazh.elements import element_table
from idhazh.extract import TOKENS_PER_WORD, approx_tokens, truncate_to_tokens
from idhazh.llm.server import Completion, completion_url, post, props, server_argv, turn_markers
from idhazh.sanitize import FENCE_CLOSE, FENCE_OPEN

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTICLE = REPO_ROOT / "tests" / "fixtures" / "contracts" / "article" / "ok.json"
CORPUS = REPO_ROOT / "corpus" / "corpus.jsonl"

#: Read in blocks rather than whole. The weights are several gigabytes and the
#: refusal is the first thing that runs, before a server is started.
_HASH_BLOCK: Final = 1 << 20


def wait_for_health(port: int, *, deadline_seconds: float) -> None:
    """Block until the server answers, or give up saying how long it waited."""
    started = time.monotonic()
    while time.monotonic() - started < deadline_seconds:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2.0):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(1.0)
    raise TimeoutError(f"the server did not answer /health in {deadline_seconds:.0f} s")


class WrongWeightsError(RuntimeError):
    """The file on disk is not the file `config/` declares for this role."""


def weights_digest(weights: Path) -> str:
    digest = hashlib.sha256()
    with weights.open("rb") as handle:
        while block := handle.read(_HASH_BLOCK):
            digest.update(block)
    return digest.hexdigest()


def refuse_undeclared_weights(weights: Path, app: AppConfig, role: str = "summarize") -> str:
    """Hash the file and compare it with the block that configures it.

    `inference.declared_for` is the sha256 of the entry its inference block
    belongs to, and `ModelsConfig` already refuses a config where those two
    disagree. So this is the one comparison config cannot make for itself: the
    bytes on this disk against the bytes the run was tuned for.
    """
    entry = getattr(app.models, role)
    declared = entry.inference.declared_for
    if declared is None:
        raise WrongWeightsError(
            f"models.{role}.inference.declared_for is unset, so there is nothing to "
            "check these weights against - set it before taking a reading"
        )
    print(f"hashing {weights} against models.{role}.inference.declared_for", flush=True)
    found = weights_digest(weights)
    if found != declared:
        raise WrongWeightsError(
            f"{weights.name} is not the file models.{role} declares.\n"
            f"  on disk    {found}\n"
            f"  declared   {declared}  ({entry.file})\n"
            "Every number below would be about a model this repository does not run."
        )
    return found


# --- Real articles, from the corpus ------------------------------------------


def article_from_user_turn(turn: str) -> tuple[str | None, str]:
    """Pull the title and the body back out of a summarizer user turn.

    `summarize.user_turn` writes `Source form: <form>`, then the title and the
    body inside one fence. The text has already been through `sanitize`, so what
    comes back out is what the model was given - which is the point. It is data
    on the way in and data on the way out (Guardrail #11).
    """
    opened = turn.index(FENCE_OPEN) + len(FENCE_OPEN)
    inside = turn[opened : turn.index(FENCE_CLOSE)].strip("\n")
    if not inside.startswith("Title: "):
        return None, inside
    title, _, body = inside.partition("\n\n")
    return title.removeprefix("Title: ").strip() or None, body.strip("\n")


@dataclass(frozen=True, slots=True)
class Sample:
    """One corpus row as something the call builders accept.

    The key stays beside the article rather than on it: `Article` recomputes
    `url_key` from `canonical_url` on read, and the corpus does not carry the
    URL. Neither field reaches a prompt, so the key is here only to say which
    row a number came from.
    """

    url_key: str
    article: Article


def corpus_samples(corpus: Path, template: Article) -> list[Sample]:
    """Every corpus row as an `Article`, longest body first.

    The corpus is the only committed source text in this repository
    (`CLAUDE.md` section 0a), so it is the only place real article prose can
    come from. It is not where the cap's worst case comes from: its longest body
    is whatever `extract.truncation_cap_tokens` allowed on the day it was
    harvested, which is what `sample_at_the_cap` exists for.

    Everything except the text, the title and the counts derived from them is
    the committed fixture's: none of it reaches a prompt, and inventing values
    would only add ways to fail validation.
    """
    base = template.model_dump(mode="json")
    built: list[Sample] = []
    for line in corpus.read_text(encoding="utf-8").splitlines():
        row = CorpusRow.from_json(line)
        user = next((one.content for one in row.messages if one.role is ChatRole.USER), None)
        if user is None:
            continue
        title, body = article_from_user_turn(user)
        words = len(body.split())
        built.append(
            Sample(
                url_key=str(row.url_key),
                article=Article.model_validate(
                    base
                    | {
                        "title": title,
                        "text": body,
                        "word_count": words,
                        "source_word_count": words,
                        "token_count": approx_tokens(words),
                    }
                ),
            )
        )
    return sorted(built, key=lambda one: one.article.word_count, reverse=True)


def sample_at_the_cap(samples: Sequence[Sample], *, cap_tokens: int) -> Sample:
    """One article at the configured truncation cap, built from corpus prose.

    **The corpus cannot supply one.** Its longest body is whatever the cap
    allowed on the day it was harvested, so the archive's worst case is a fossil
    of a retired setting - measured 2026-09-12, the longest of 1,444 rows is
    3,846 words, which is `int(5000 / 1.3)` under a cap that doubled to 10,000
    on 2026-09-09. `CLAUDE.md` section 13 rules that where the awkward shape is
    the point, the shape is **built**, because a built one carries the case the
    archive has never produced (Guardrail #12).

    Real prose, so the tokenizer sees real vocabulary and real punctuation; the
    length is the only part that is ours. The bodies are joined longest first
    and then cut by `truncate_to_tokens` itself, so the arm is the cap's worst
    case by construction and follows the cap the next time it moves.
    """
    words: list[str] = []
    used: list[str] = []
    allowed = int(cap_tokens / TOKENS_PER_WORD)
    for sample in samples:
        used.append(sample.url_key)
        words.extend((sample.article.text or "").split())
        if len(words) >= allowed:
            break
    body, truncated, cut = truncate_to_tokens(" ".join(words), cap_tokens)
    kept = len(body.split())
    return Sample(
        url_key="built from " + "+".join(used),
        article=Article.model_validate(
            samples[0].article.model_dump(mode="json")
            | {
                "text": body,
                "word_count": kept,
                "source_word_count": kept,
                "token_count": approx_tokens(kept),
                "truncated": truncated,
                "truncated_at_tokens": cut,
            }
        ),
    )


# --- The server's own template and tokenizer ---------------------------------


def _json_post(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    outbound = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(outbound, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body if isinstance(body, dict) else {}


@dataclass(frozen=True, slots=True)
class Tokenizer:
    """The running server's own tokenizer, over its own HTTP.

    Asking the server rather than reasoning about the vocabulary is the whole
    difference between a reading and an argument: the tokenizer is the model's
    and it moves when the model does. A server that will not answer yields
    nothing rather than a guess, and the caller says the diagnostic was unread
    (`CLAUDE.md` section 1a).

    **It takes prompt strings, not message arrays.** The prompts this measures
    are rendered by `idhazh.llm.server`, so there is no template to ask about -
    asking `/apply-template` would tokenise a prompt the server was never sent,
    which is how the reading this tool replaced came to be taken on the wrong
    model.
    """

    base: str
    timeout: float

    def tokenize(self, text: str) -> list[int] | None:
        try:
            body = _json_post(f"{self.base}/tokenize", {"content": text}, timeout=self.timeout)
        except (urllib.error.URLError, OSError, ValueError):
            return None
        tokens = body.get("tokens")
        return [int(one) for one in tokens] if isinstance(tokens, list) else None

    def detokenize(self, tokens: Sequence[int]) -> str | None:
        try:
            body = _json_post(
                f"{self.base}/detokenize", {"tokens": list(tokens)}, timeout=self.timeout
            )
        except (urllib.error.URLError, OSError, ValueError):
            return None
        content = body.get("content")
        return content if isinstance(content, str) else None

    def count(self, text: str) -> int | None:
        tokens = self.tokenize(text)
        return None if tokens is None else len(tokens)


def common_prefix(left: Sequence[int], right: Sequence[int]) -> int:
    """How many tokens two prompts share before they diverge.

    That is what a prefix cache reuses, so it is the break point rather than an
    estimate of one.
    """
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def describe(endpoint: str, *, digest: str) -> dict[str, Any]:
    """What the server says about itself, beside the weights it was handed.

    The chat template no longer renders these two prompts and is still recorded,
    because it ships with a build as well as with weights - this repository's own
    `Completion.reasoned` names a llama.cpp build that changes what a reply looks
    like with no weights change - and because a reader comparing this run against
    an earlier one needs to know whether the template moved under it. It is
    digested rather than quoted: it is a few thousand characters of Jinja and the
    only question is whether it is the same one.

    The turn markers are digested beside it. They are what renders these prompts
    now, so a run whose markers moved is a run whose outputs may have moved, and
    nothing else here would say so.
    """
    said = props(endpoint, timeout=60.0)
    template = said.get("chat_template")
    markers = turn_markers()
    return {
        "weights_sha256": digest,
        "build": said.get("build_info"),
        "model_path": said.get("model_path"),
        "chat_template_sha256": (
            derive_text_digest(template) if isinstance(template, str) else None
        ),
        "chat_template_characters": len(template) if isinstance(template, str) else None,
        "turn_markers_sha256": derive_text_digest(
            markers.turn_opening.template
            + markers.turn_closing
            + markers.reply_opening
            + markers.reply_opening_thinking
        ),
    }


# --- The decomposition -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Spend:
    """Where one item's re-prefilled tokens went. The parts sum to the total."""

    article_changed: int
    template_broke: int
    trailing_turn: int

    @property
    def total(self) -> int:
        return self.article_changed + self.template_broke + self.trailing_turn


def decompose(one: Completion, two: Completion) -> Spend:
    """Split an item's re-prefill three ways, by cause.

    `boundary` is how many entries call 1 left in the slot: its whole prompt
    plus the tokens it generated, both of which the runtime keeps. What call 2
    cached short of that is the template breaking the prefix; what call 2
    carries beyond it is the trailing turn, which is new bytes and always
    prefills.

    **The sum is an identity, so it is a reading aid and not the oracle.**
    `boundary` cancels: the two call-2 causes always come to
    `two.prompt_tokens - two.cached_tokens` whichever branch of the `max` runs,
    so a check that they add up cannot fail and proves nothing. What can fail is
    `Checks` below - whether the cache actually reached where the two rendered
    prompts say it had to.
    """
    boundary = one.prompt_tokens + one.completion_tokens
    return Spend(
        article_changed=one.prompt_tokens - one.cached_tokens,
        template_broke=max(0, boundary - two.cached_tokens),
        trailing_turn=two.prompt_tokens - max(boundary, two.cached_tokens),
    )


def prefilled(one: Completion, two: Completion) -> int:
    """Every token the server read for this item and did not have cached."""
    return (one.prompt_tokens - one.cached_tokens) + (two.prompt_tokens - two.cached_tokens)


@dataclass(frozen=True, slots=True)
class Checks:
    """What has to hold for the split above to be about this server.

    Each one is a statement that can come out false, which is the whole reason
    they are here rather than the sum. They are checked per item and the exit
    code is theirs.
    """

    #: The renderer and the live request agree on how long call 1's prompt is.
    #: False means the diagnostic is describing a prompt the server was not
    #: sent - a wrong reply opening does exactly that.
    prompt_renders_the_same: bool
    #: The two prompts do not diverge before the end of call 1's. **This is row
    #: #3c's oracle taken live**, and it is the exact statement rather than a
    #: tolerant one: call 2's prompt IS call 1's extended, so they cannot
    #: disagree anywhere inside it. Under the chat template this came out 1,493
    #: against 1,497 and was the whole reason for the row.
    prompts_agree_to_the_end_of_call_one: bool
    #: The cache reached at least as far as the two prompts agree. Reaching
    #: FURTHER is the good news - it means the slot also answered for the reply -
    #: so this is a floor and not an equality. False means the runtime is doing
    #: something this split does not model, and every share below it is then
    #: unexplained rather than wrong.
    cache_reached_the_shared_prefix: bool
    #: Call 2 carries at least everything call 1 left in the slot. False makes
    #: `trailing_turn` negative, which is not a share of anything.
    trailing_turn_is_positive: bool
    #: What was replayed is what was generated. False means the runtime returned
    #: less than it decoded, so the assistant turn call 2 sends is shorter than
    #: the reply call 1 wrote, and `boundary` overstates the depth.
    replay_is_the_whole_reply: bool

    @property
    def hold(self) -> bool:
        return (
            self.prompt_renders_the_same
            and self.prompts_agree_to_the_end_of_call_one
            and self.cache_reached_the_shared_prefix
            and self.trailing_turn_is_positive
            and self.replay_is_the_whole_reply
        )

    def failures(self) -> list[str]:
        named = {
            "call 1's rendered prompt is not the length the server charged for": (
                self.prompt_renders_the_same
            ),
            "the two prompts diverge before the end of call 1's": (
                self.prompts_agree_to_the_end_of_call_one
            ),
            "the cache stopped short of where the two prompts still agree": (
                self.cache_reached_the_shared_prefix
            ),
            "call 2 carries fewer tokens than call 1 left in the slot": (
                self.trailing_turn_is_positive
            ),
            "call 1's replayed turn is shorter than the reply it generated": (
                self.replay_is_the_whole_reply
            ),
        }
        return [what for what, held in named.items() if not held]


#: The label, the field and the row that owns removing it. One list, so the
#: printed table and the JSON cannot drift apart. The template row reads zero
#: since row #3c and stays printed: a cause on the page is one a build change
#: cannot reintroduce quietly.
CAUSES: Final = (
    ("the article changed", "article_changed", "irreducible"),
    ("the chat template broke the prefix", "template_broke", "row #3c, removed"),
    ("the trailing turn sits behind the article", "trailing_turn", "row #3e, removed"),
)


def report_call(name: str, completion: Completion) -> None:
    print(
        f"  {name:<7} prompt={completion.prompt_tokens:>6}"
        f"  cached={completion.cached_tokens:>6}"
        f"  decoded={completion.completion_tokens:>5}"
        f"  re-prefilled={completion.prompt_tokens - completion.cached_tokens:>6}"
        f"  prefill_ms={completion.prefill_ms:>7}"
        f"  decode_ms={completion.decode_ms:>7}"
        f"  finish={completion.finish_reason}"
    )


def report_spend(spend: Spend, measured: int, *, question: int | None) -> None:
    """Print the split, and the floor under the share row #3e can move."""
    print()
    print(f"  {'where the re-prefilled tokens went':<46}{'tokens':>8}{'share':>8}  owner")
    for label, field, owner in CAUSES:
        value = getattr(spend, field)
        share = (100.0 * value / spend.total) if spend.total else 0.0
        print(f"    {label:<44}{value:>8}{share:>7.1f}%  {owner}")
    print(f"    {'total':<44}{spend.total:>8}{100.0 if spend.total else 0.0:>7.1f}%")
    print(f"  the two calls re-prefilled {measured}, the three causes {spend.total}")
    if question is not None:
        print(
            f"  of the trailing turn, {question} tokens are the question's own text and "
            f"{spend.trailing_turn - question} are the turn markers no row moves"
        )


# --- The run -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reading:
    """One item, both calls, and where its re-prefilled tokens went."""

    label: str
    url_key: str
    article_words: int
    call_one_prompt: int
    one: Completion
    two: Completion
    spend: Spend
    question_tokens: int | None
    broke_at: int | None
    rendered_one: int | None
    rendered_two: int | None
    divergence: str | None
    replay_tokens: int | None
    checks: Checks

    def as_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "url_key": self.url_key,
            "article_words": self.article_words,
            "call_one_prompt_tokens": self.call_one_prompt,
            "call_one": asdict(self.one),
            "call_two": asdict(self.two),
            "spend": asdict(self.spend),
            "re_prefilled": prefilled(self.one, self.two),
            "question_tokens": self.question_tokens,
            "rendered_call_one_tokens": self.rendered_one,
            "rendered_call_two_tokens": self.rendered_two,
            "prefix_broke_at": self.broke_at,
            "divergence": self.divergence,
            "replay_tokens": self.replay_tokens,
            "checks": asdict(self.checks),
        }


@dataclass(frozen=True, slots=True)
class Break:
    """Where the two rendered prompts stop agreeing, and what sits there."""

    at: int | None = None
    rendered_one: int | None = None
    rendered_two: int | None = None
    tail: str | None = None
    replay_tokens: int | None = None


def prefix_break(
    first: dict[str, Any], second: dict[str, Any], reply: str, tokenizer: Tokenizer
) -> Break:
    """Where the two prompts stop agreeing, in this model's own tokens.

    The live `cached_tokens` says how far the cache reached. This says why, and
    since row #3c the expected answer is "they do not stop agreeing until call
    1's prompt and reply are both behind us". It is still measured rather than
    asserted, because a byte prefix is only a token prefix when the seam sits
    where the tokenizer cannot merge across - which is a property of the
    vocabulary and not of our arithmetic. It also tokenises the reply on its
    own: a runtime that splits reasoning out of `content` replays a shorter
    assistant turn than call 1 wrote, and nothing else here would show it.
    """
    one_tokens = tokenizer.tokenize(str(first["prompt"]))
    two_tokens = tokenizer.tokenize(str(second["prompt"]))
    if one_tokens is None or two_tokens is None:
        print("  the server would not tokenise a prompt, so the break is unread")
        return Break()
    at = common_prefix(one_tokens, two_tokens)
    tail = tokenizer.detokenize(one_tokens[at:])
    replay = tokenizer.tokenize(reply)
    print(
        f"  rendered: call 1 is {len(one_tokens)} tokens, call 2 is {len(two_tokens)},"
        f" and they diverge at token {at} -"
        f" call 1 carries {len(one_tokens) - at} token(s) the replay drops"
    )
    if tail is not None:
        print(f"  what call 1 has there, verbatim: {tail!r}")
    return Break(
        at=at,
        rendered_one=len(one_tokens),
        rendered_two=len(two_tokens),
        tail=tail,
        replay_tokens=None if replay is None else len(replay),
    )


def check(one: Completion, two: Completion, spend: Spend, broke: Break) -> Checks:
    """The five statements that can come out false. A missing reading is not one.

    An unread diagnostic is reported as unread rather than as a failure
    (`CLAUDE.md` section 1a), so a check whose evidence the server would not
    give holds by default and the run says the evidence is missing.

    **The template cause is reported and never failed on**, even though row #3c
    drives it to zero. Measured 2026-09-12 on the configured weights it came out
    at 1 token an item rather than 0: the reply's own text re-tokenises one
    token shorter when it is read back as part of a prompt than it was when it
    was decoded, which is a property of the vocabulary and not of the prompt
    layout. The statement that IS exact is that the two prompts do not diverge
    inside call 1's, and that is the check above.
    """
    return Checks(
        prompt_renders_the_same=broke.rendered_one in (None, one.prompt_tokens),
        prompts_agree_to_the_end_of_call_one=(
            broke.at is None or broke.at == broke.rendered_one
        ),
        cache_reached_the_shared_prefix=broke.at is None or two.cached_tokens >= broke.at,
        trailing_turn_is_positive=spend.trailing_turn >= 0,
        replay_is_the_whole_reply=(
            broke.replay_tokens is None or broke.replay_tokens >= one.completion_tokens - 1
        ),
    )


def run_item(
    sample: Sample,
    *,
    label: str,
    app: AppConfig,
    endpoint: str,
    tokenizer: Tokenizer,
    timeout: float,
    call_one_cap: int,
    call_two_cap: int,
    question_tokens: int | None,
) -> Reading:
    article = sample.article
    model = app.models.summarize
    table = element_table(article, config=app.elements)
    first = build_call_one_request(
        article,
        table,
        model_id=model.id,
        inference=model.inference,
        prompt_config=app.summarize,
    )
    if call_one_cap:
        first["n_predict"] = call_one_cap
    one = post(first, endpoint=endpoint, timeout=timeout)
    report_call("call 1", one)

    second = build_call_two_request(
        first, one.content, source_words=article.band_source_words, brief=article.brief
    )
    if call_two_cap:
        second["n_predict"] = call_two_cap
    two = post(second, endpoint=endpoint, timeout=timeout)
    report_call("call 2", two)

    broke = prefix_break(first, second, one.content, tokenizer)
    spend = decompose(one, two)
    report_spend(spend, prefilled(one, two), question=question_tokens)
    checks = check(one, two, spend, broke)
    for failure in checks.failures():
        print(f"  CHECK FAILED: {failure}")
    return Reading(
        label=label,
        url_key=sample.url_key,
        article_words=article.word_count,
        call_one_prompt=one.prompt_tokens,
        one=one,
        two=two,
        spend=spend,
        question_tokens=question_tokens,
        broke_at=broke.at,
        rendered_one=broke.rendered_one,
        rendered_two=broke.rendered_two,
        divergence=broke.tail,
        replay_tokens=broke.replay_tokens,
        checks=checks,
    )


def pick_samples(
    samples: Sequence[Sample],
    *,
    app: AppConfig,
    tokenizer: Tokenizer,
    wanted: int,
    prompt_ceiling: int,
) -> list[tuple[Sample, int]]:
    """The longest corpus articles whose call-1 prompt still fits.

    Longest, because every share this prints is a share of a prompt and the
    design's worst case is its longest one. Measured rather than estimated: the
    prompt is tokenised by the server that will answer it, so "fits" is a fact
    rather than a words-to-tokens rule of thumb.
    """
    model = app.models.summarize
    chosen: list[tuple[Sample, int]] = []
    for seen, sample in enumerate(samples, start=1):
        table = element_table(sample.article, config=app.elements)
        request = build_call_one_request(
            sample.article,
            table,
            model_id=model.id,
            inference=model.inference,
            prompt_config=app.summarize,
        )
        tokens = tokenizer.count(str(request["prompt"]))
        if tokens is None:
            raise RuntimeError(
                "the server would not tokenise a prompt, so no article can be "
                "chosen by measurement - check /tokenize"
            )
        if tokens <= prompt_ceiling:
            chosen.append((sample, tokens))
            if len(chosen) == wanted:
                print(
                    f"chose {wanted} article(s) after rendering {seen} of {len(samples)}; "
                    f"the longest that fits is {chosen[0][0].article.word_count} words "
                    f"and a {chosen[0][1]}-token call-1 prompt",
                    flush=True,
                )
                return chosen
    raise RuntimeError(f"only {len(chosen)} of {wanted} articles fit under {prompt_ceiling}")


def finish(
    readings: Sequence[Reading],
    out: Path | None,
    *,
    weights: Path,
    digest: str,
    system_tokens: int | None,
    server: dict[str, Any],
) -> int:
    """The summary, the machine-readable copy, and the exit code.

    The exit code is about the instrument and not about the design. The three
    causes always sum, so what can fail is whether the cache reached where the
    two rendered prompts say it had to, and whether the steady state is one.
    """
    print()
    print("=" * 100)
    print(
        f"{'item':<28}{'words':>7}{'prompt':>8}{'total':>8}"
        f"{'article':>9}{'template':>10}{'trailing':>10}"
    )
    for reading in readings:
        print(
            f"{reading.label:<28}{reading.article_words:>7}{reading.call_one_prompt:>8}"
            f"{reading.spend.total:>8}{reading.spend.article_changed:>9}"
            f"{reading.spend.template_broke:>10}{reading.spend.trailing_turn:>10}"
        )
    print("`prompt` is call 1's own prompt, so two rows with equal words can still differ")

    steady = list(readings[1:])
    cold = []
    if steady:
        print()
        print("Item 1 is a cold cache slot, so the steady state is item 2 onward:")
        for reading in steady:
            reused = reading.one.cached_tokens
            print(
                f"  {reading.label}: call 1 reused {reused} of its "
                f"{reading.one.prompt_tokens}-token prompt, and call 2 reused "
                f"{reading.two.cached_tokens} of its {reading.two.prompt_tokens}"
            )
            if system_tokens is not None and reused < system_tokens:
                cold.append(reading.label)
        if system_tokens is not None:
            print(
                f"  call 1's system turn is {system_tokens} tokens and is the same bytes on "
                "every item, so a later item reusing fewer than that is the finding"
            )

    print()
    print(f"weights {weights.name} sha256={digest}")
    payload = {
        "taken_at": time.strftime("%Y-%m-%d"),
        "weights": weights.name,
        "sha256": digest,
        "server": server,
        "call_one_system_tokens": system_tokens,
        "items": [reading.as_json() for reading in readings],
    }
    text = json.dumps(payload, default=str, indent=2)
    if out is not None:
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print(text)

    failed = [
        f"{reading.label}: {what}" for reading in readings for what in reading.checks.failures()
    ]
    failed += [f"{label}: call 1 did not reuse the shared system turn" for label in cold]
    if failed:
        print("INSTRUMENT BROKEN:", file=sys.stderr)
        for line in failed:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    # Not spelled `--port`. `test_summarize` holds one function as the only
    # place in `backend/` that writes a llama-server flag as a quoted literal,
    # and it reads the source rather than the argv, so an option of ours sharing
    # the name would put this file in that set.
    parser.add_argument("--server-port", type=int, default=8099)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--template-article", type=Path, default=ARTICLE)
    parser.add_argument("--items", type=int, default=2)
    parser.add_argument("--startup-seconds", type=float, default=600.0)
    parser.add_argument("--request-minutes", type=float, default=45.0)
    parser.add_argument(
        "--decode-cap",
        type=int,
        default=16,
        help=(
            "Stop each capped decode after this many tokens. Every cause here is a "
            "prefill fact that lands before a token is decoded, so a cap answers the "
            "same question in minutes instead of hours - except the template cause, "
            "which is call 1's reply length plus the divergence, and that is what the "
            "extra uncapped item is for. Zero uses the real budgets."
        ),
    )
    parser.add_argument(
        "--uncapped-item",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run one more item with call 1 on its real output budget.",
    )
    parser.add_argument(
        "--at-cap",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Run one more item on an article BUILT to extract.truncation_cap_tokens out "
            "of corpus prose, because the corpus cannot supply one: its longest body is "
            "what the cap allowed when it was harvested. Off by default, and the reason "
            "is the clock rather than the question - that prompt is 14,306 tokens, which "
            "is about 45 minutes of prefill at the 5.4 tokens a second this machine read "
            "at on 2026-09-12. The run prints the same article's prompt size against the "
            "ceiling either way, which is what settles whether it fits."
        ),
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--server-log",
        type=Path,
        default=None,
        help=(
            "Where to keep the server's own output. `log_verbosity` is 4 in config, so "
            "this is the only place the attention state and a failed load say anything."
        ),
    )
    args = parser.parse_args(argv)

    settings = config.load(REPO_ROOT / "config")
    app = settings.app
    model = app.models.summarize
    try:
        digest = refuse_undeclared_weights(args.weights, app)
    except WrongWeightsError as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2
    print(f"weights verified: {model.file} sha256={digest}", flush=True)

    template = Article.from_json(args.template_article.read_text(encoding="utf-8"))
    samples = corpus_samples(args.corpus, template)
    wanted = args.items + (1 if args.uncapped_item else 0)

    argv_line = server_argv(
        binary=args.binary,
        weights=args.weights,
        model=model,
        inference=model.inference,
        port=args.server_port,
    )
    print(" ".join(argv_line), flush=True)
    handle = args.server_log.open("wb") if args.server_log else None
    server = subprocess.Popen(
        argv_line, stdout=handle or subprocess.DEVNULL, stderr=subprocess.STDOUT
    )
    readings: list[Reading] = []
    described: dict[str, Any] = {}
    system_tokens: int | None = None
    try:
        wait_for_health(args.server_port, deadline_seconds=args.startup_seconds)
        base = f"http://127.0.0.1:{args.server_port}"
        endpoint = completion_url(base)
        timeout = args.request_minutes * 60.0
        tokenizer = Tokenizer(base=base, timeout=60.0)
        described = describe(endpoint, digest=digest)

        # What one item needs after call 1's prompt: call 1's decode, the
        # trailing turn and call 2's decode. Call 2's prompt is call 1's plus
        # those, so one ceiling on call 1's prompt covers both calls. The decode
        # cap is a clock knob and has no place in a context budget, so the
        # budget reads the real one whatever the cap is.
        #
        # **Two counts, and they are not the same question.** The budget wants
        # the turn as it is rendered, markers and all. The report wants the
        # question's own text, because the difference between the two IS the
        # marker floor row #3e cannot go below - and measuring the report with
        # the rendered number makes that floor come out negative.
        markers = turn_markers()
        question = call_two_user_turn(app.summarize)
        rendered_turn = tokenizer.count(markers.turn("user", question))
        question_tokens = tokenizer.tokenize(question)
        if rendered_turn is None or question_tokens is None:
            raise RuntimeError("the server would not tokenise call 2's question")
        trailing = len(question_tokens)
        system_tokens = tokenizer.count(
            markers.turn("system", call_one_system_prompt(app.summarize))
        )
        call_one_decode = model.inference.max_output_tokens
        call_two_decode = call_two_output_tokens(app.summarize)
        ceiling = model.inference.n_ctx - (call_one_decode + call_two_decode + rendered_turn)
        print(
            f"call 2's question is {trailing} tokens of text and {rendered_turn} as a "
            f"rendered turn; with {call_one_decode} for call 1's decode and "
            f"{call_two_decode} for call 2's, call 1's prompt may reach {ceiling} of "
            f"{model.inference.n_ctx} in production",
            flush=True,
        )

        chosen = (
            pick_samples(
                samples, app=app, tokenizer=tokenizer, wanted=wanted, prompt_ceiling=ceiling
            )
            if wanted
            else []
        )
        # Always rendered, never always run. Without this the harness prints
        # "the longest that fits", which reads as "the longest there is" - and
        # what it selected around is the case it exists to measure. Rendering
        # costs seconds; running it costs about 45 minutes of prefill.
        built = sample_at_the_cap(samples, cap_tokens=app.extract.truncation_cap_tokens)
        at_cap_tokens = tokenizer.count(
            str(
                build_call_one_request(
                    built.article,
                    element_table(built.article, config=app.elements),
                    model_id=model.id,
                    inference=model.inference,
                    prompt_config=app.summarize,
                )["prompt"]
            )
        )
        print(
            f"an article AT the cap is {built.article.word_count} words and a "
            f"{at_cap_tokens}-token call-1 prompt, against the {ceiling}-token ceiling "
            f"above - the corpus cannot supply one, so this arm is BUILT",
            flush=True,
        )
        if args.at_cap:
            chosen.append((built, at_cap_tokens or 0))

        for index, (sample, prompt_tokens) in enumerate(chosen, start=1):
            built_arm = args.at_cap and index == len(chosen)
            uncapped = built_arm or (args.uncapped_item and index == wanted)
            label = f"item {index}"
            if built_arm:
                label += " - at the cap, BUILT"
            elif uncapped:
                label += " - call 1 uncapped"
            print()
            print(
                f"--- {label}: {sample.article.word_count} words, {prompt_tokens} prompt "
                f"tokens, url_key={sample.url_key}",
                flush=True,
            )
            readings.append(
                run_item(
                    sample,
                    label=label,
                    app=app,
                    endpoint=endpoint,
                    tokenizer=tokenizer,
                    timeout=timeout,
                    call_one_cap=0 if uncapped else args.decode_cap,
                    call_two_cap=args.decode_cap,
                    question_tokens=trailing,
                )
            )
    finally:
        server.terminate()
        server.wait(timeout=60)
        if handle is not None:
            handle.close()

    return finish(
        readings,
        args.out,
        weights=args.weights,
        digest=digest,
        system_tokens=system_tokens,
        server=described,
    )


if __name__ == "__main__":
    sys.exit(main())
