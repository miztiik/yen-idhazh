"""Say where every token call 2 had to read again went.

Row 3's first reading printed `FLOOR BROKEN - 4 tokens` while 670 tokens an item
burned with no reading at all. The floor was a boolean watching the smaller of
two wastes, and its alarm fired on the good case - which teaches its reader to
discount it on the bad one. **A number that is not decomposed is a number nobody
can act on**, so this reports three numbers that sum to the total instead.

**The three causes, and each one belongs to somebody.**

- **The article changed.** Call 1 on a new item reads a new article. Irreducible:
  no prompt layout removes it, and it is the cost the design exists to pay.
- **The chat template broke the prefix.** Call 2 replays call 1's turns as
  history and the template renders them differently, so everything behind the
  divergence prefills again - the divergence itself is a handful of tokens and
  what sits behind it is call 1's whole reply.
- **The trailing turn sits behind the article.** Call 2's question is the same
  bytes on every item, but the article in front of it is not, so a prefix cache
  cannot reach it and every token of it is read again, for ever.

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
    call_two_output_tokens,
    call_two_user_turn,
)
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.corpus import ChatRole, CorpusRow
from idhazh.elements import element_table
from idhazh.extract import approx_tokens
from idhazh.llm.server import Completion, post, server_argv
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


# --- A real article, from the corpus -----------------------------------------


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
    (`CLAUDE.md` section 0a), so it is the only place a real article near the
    truncation cap can come from. Everything except the text, the title and the
    counts derived from them is the committed fixture's: none of it reaches a
    prompt, and inventing values would only add ways to fail validation.
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
    """The running server's own template and tokenizer, over its own HTTP.

    Asking the server rather than reasoning about the template is the whole
    difference between a reading and an argument: the template is the model's,
    the tokenizer is the model's, and both move when the model does. A server
    that will not answer yields nothing rather than a guess, and the caller says
    the diagnostic was unread (`CLAUDE.md` section 1a).
    """

    base: str
    timeout: float

    def render(self, messages: Sequence[Any]) -> str | None:
        """The exact prompt string this message array would become."""
        try:
            body = _json_post(
                f"{self.base}/apply-template", {"messages": list(messages)}, timeout=self.timeout
            )
        except (urllib.error.URLError, OSError, ValueError):
            return None
        prompt = body.get("prompt")
        return prompt if isinstance(prompt, str) else None

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

    def count(self, messages: Sequence[Any]) -> int | None:
        rendered = self.render(messages)
        tokens = self.tokenize(rendered) if rendered is not None else None
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

    `boundary` is how far a perfect cache could reach into call 2's prompt: call
    1's whole prompt plus the reply it generated, both of which the slot already
    held. What call 2 cached short of that is the template breaking the prefix;
    what call 2 carries beyond it is the trailing turn, which is new bytes and
    always prefills.

    The identity that makes this a decomposition rather than three plausible
    numbers: `article_changed` is call 1's own re-prefill and the other two sum
    to call 2's, so the three sum to every token the server prefilled for this
    item. The `max` covers a cache that reached past call 1's reply, which is
    not what happens today and would be very good news.
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


#: The label, the field and the row that owns removing it. One list, so the
#: printed table and the JSON cannot drift apart.
CAUSES: Final = (
    ("the article changed", "article_changed", "irreducible"),
    ("the chat template broke the prefix", "template_broke", "row #3c"),
    ("the trailing turn sits behind the article", "trailing_turn", "row #3e"),
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


def report_spend(spend: Spend, measured: int) -> None:
    """Print the split and say whether it adds up. That is the oracle."""
    print()
    print(f"  {'where the re-prefilled tokens went':<46}{'tokens':>8}{'share':>8}  owner")
    for label, field, owner in CAUSES:
        value = getattr(spend, field)
        share = (100.0 * value / spend.total) if spend.total else 0.0
        print(f"    {label:<44}{value:>8}{share:>7.1f}%  {owner}")
    print(f"    {'total':<44}{spend.total:>8}{100.0 if spend.total else 0.0:>7.1f}%")
    verdict = "SUMS" if spend.total == measured else "DOES NOT SUM"
    print(f"  {verdict}: the two calls re-prefilled {measured}, the three causes {spend.total}")


# --- The run -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reading:
    """One item, both calls, and where its re-prefilled tokens went."""

    label: str
    url_key: str
    article_words: int
    one: Completion
    two: Completion
    spend: Spend
    broke_at: int | None
    call_one_rendered: int | None
    divergence: str | None

    @property
    def sums(self) -> bool:
        return self.spend.total == prefilled(self.one, self.two)

    def as_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "url_key": self.url_key,
            "article_words": self.article_words,
            "call_one": asdict(self.one),
            "call_two": asdict(self.two),
            "spend": asdict(self.spend),
            "re_prefilled": prefilled(self.one, self.two),
            "sums": self.sums,
            "call_one_rendered_tokens": self.call_one_rendered,
            "prefix_broke_at": self.broke_at,
            "divergence": self.divergence,
        }


def prefix_break(
    first: dict[str, Any], second: dict[str, Any], tokenizer: Tokenizer
) -> tuple[int | None, int | None, str | None]:
    """Where the two rendered prompts stop agreeing, and what call 1 had there.

    The live `cached_tokens` says how far the cache reached. This says WHY it
    stopped there, in this model's own tokens, so the answer moves when the
    template does instead of restating what one template did in 2026.
    """
    one_prompt = tokenizer.render(first["messages"])
    two_prompt = tokenizer.render(second["messages"])
    if one_prompt is None or two_prompt is None:
        print("  the server would not render a prompt, so the break point is unread")
        return None, None, None
    one_tokens = tokenizer.tokenize(one_prompt)
    two_tokens = tokenizer.tokenize(two_prompt)
    if one_tokens is None or two_tokens is None:
        print("  the server would not tokenise a prompt, so the break point is unread")
        return None, None, None
    at = common_prefix(one_tokens, two_tokens)
    tail = tokenizer.detokenize(one_tokens[at:])
    print(
        f"  rendered: call 1 is {len(one_tokens)} tokens, call 2 is {len(two_tokens)},"
        f" and they diverge at token {at} -"
        f" call 1 carries {len(one_tokens) - at} token(s) the replay drops"
    )
    if tail is not None:
        print(f"  what call 1 has there, verbatim: {tail!r}")
    return at, len(one_tokens), tail


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
) -> Reading:
    article = sample.article
    model = app.models.summarize
    table = element_table(article, config=app.elements)
    first = build_call_one_request(article, table, model_id=model.id, inference=model.inference)
    if call_one_cap:
        first["max_tokens"] = call_one_cap
    one = post(first, endpoint=endpoint, timeout=timeout)
    report_call("call 1", one)

    second = build_call_two_request(
        first, one.content, source_words=article.band_source_words, brief=article.brief
    )
    if call_two_cap:
        second["max_tokens"] = call_two_cap
    two = post(second, endpoint=endpoint, timeout=timeout)
    report_call("call 2", two)

    at, rendered, tail = prefix_break(first, second, tokenizer)
    spend = decompose(one, two)
    report_spend(spend, prefilled(one, two))
    return Reading(
        label=label,
        url_key=sample.url_key,
        article_words=article.word_count,
        one=one,
        two=two,
        spend=spend,
        broke_at=at,
        call_one_rendered=rendered,
        divergence=tail,
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
    prompt is rendered and tokenised by the server that will answer it, so
    "fits" is a fact rather than a words-to-tokens rule of thumb.
    """
    model = app.models.summarize
    chosen: list[tuple[Sample, int]] = []
    for seen, sample in enumerate(samples, start=1):
        table = element_table(sample.article, config=app.elements)
        request = build_call_one_request(
            sample.article, table, model_id=model.id, inference=model.inference
        )
        tokens = tokenizer.count(request["messages"])
        if tokens is None:
            raise RuntimeError(
                "the server would not render or tokenise a prompt, so no article can be "
                "chosen by measurement - check /apply-template and /tokenize"
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


def finish(readings: Sequence[Reading], out: Path | None, *, weights: Path, digest: str) -> int:
    """The summary, the machine-readable copy, and the exit code.

    The exit code is about the instrument and not about the design: a
    decomposition whose parts do not add up is a guess with three decimal
    places, and that is the one thing this may fail on.
    """
    print()
    print("=" * 92)
    head = f"{'item':<28}{'words':>7}{'total':>8}{'article':>9}{'template':>10}{'trailing':>10}"
    print(head)
    for reading in readings:
        print(
            f"{reading.label:<28}{reading.article_words:>7}{reading.spend.total:>8}"
            f"{reading.spend.article_changed:>9}{reading.spend.template_broke:>10}"
            f"{reading.spend.trailing_turn:>10}"
        )
    if len(readings) > 1:
        print()
        print("Item 1 is a cold cache slot, so the steady state is item 2 onward:")
        for reading in readings[1:]:
            print(
                f"  {reading.label}: call 1 reused {reading.one.cached_tokens} of its "
                f"{reading.one.prompt_tokens}-token prompt, and call 2 reused "
                f"{reading.two.cached_tokens} of its {reading.two.prompt_tokens}"
            )
    print()
    print(f"weights {weights.name} sha256={digest}")
    payload = {"weights": weights.name, "sha256": digest, "items": [r.as_json() for r in readings]}
    text = json.dumps(payload, default=str, indent=2)
    if out is not None:
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print(text)
    broken = [reading.label for reading in readings if not reading.sums]
    if broken:
        print(f"INSTRUMENT BROKEN: the causes do not sum on {', '.join(broken)}", file=sys.stderr)
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
    parser.add_argument("--out", type=Path, default=None)
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
    server = subprocess.Popen(argv_line, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    readings: list[Reading] = []
    try:
        wait_for_health(args.server_port, deadline_seconds=args.startup_seconds)
        base = f"http://127.0.0.1:{args.server_port}"
        endpoint = f"{base}/v1/chat/completions"
        timeout = args.request_minutes * 60.0
        tokenizer = Tokenizer(base=base, timeout=60.0)

        # What one item needs after call 1's prompt: call 1's decode, the
        # trailing turn and call 2's decode. Call 2's prompt is call 1's plus
        # those, so one ceiling on call 1's prompt covers both calls. The
        # trailing turn is tokenised rather than guessed - it is also the
        # answer to "how big is call 2's question really".
        question = call_two_user_turn(app.summarize)
        trailing = tokenizer.count([{"role": "user", "content": question}])
        if trailing is None:
            raise RuntimeError("the server would not tokenise call 2's question")
        call_one_decode = model.inference.max_output_tokens
        call_two_decode = args.decode_cap or call_two_output_tokens(app.summarize)
        reserve = call_one_decode + call_two_decode + trailing
        ceiling = model.inference.n_ctx - reserve
        print(
            f"call 2's question renders to {trailing} tokens as its own turn; with "
            f"{call_one_decode} for call 1's decode and {call_two_decode} for call 2's, "
            f"call 1's prompt may reach {ceiling} of {model.inference.n_ctx}",
            flush=True,
        )

        chosen = pick_samples(
            samples, app=app, tokenizer=tokenizer, wanted=wanted, prompt_ceiling=ceiling
        )
        for index, (sample, prompt_tokens) in enumerate(chosen, start=1):
            uncapped = args.uncapped_item and index == wanted
            label = f"item {index}" + (" - call 1 uncapped" if uncapped else "")
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
                )
            )
    finally:
        server.terminate()
        server.wait(timeout=60)

    return finish(readings, args.out, weights=args.weights, digest=digest)


if __name__ == "__main__":
    sys.exit(main())
