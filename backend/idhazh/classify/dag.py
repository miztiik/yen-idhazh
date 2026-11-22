"""Does one article's model call fit the context window?

**One call reads the article and writes the summary and, when source readings are
available, the answer about a chart.** The window has to hold that request whole: the
instructions and the article, and then the longest reply
the model file lets it write. The check runs before the call is sent, because
`--no-context-shift` means a decode that runs into the wall stops on an ordinary HTTP 200,
`recovered_completion` salvages the summary, and the item publishes with no picture and
`window_exhausted` recorded beside it. That is the seatbelt working for one item; a whole
shard reading that way is a window nobody sized. Refusing an article up front is still the
better answer, because the whole decode is paid for before that reason can be written.

**The prompt term is an estimate, and it is built to sit above the real prompt.**
The readings in `idhazh.measured` were taken on the longest prompt this
project has sent: it carried instructions that no longer exist and every sentence of
the article behind an address. The one call's prompt is those parts without those
instructions and without the addresses, so the readings bound it from above. The cost
is paid by an article that would have fitted: it is refused when it needs the margin the
estimate adds. Use `request_tokens` with the configured tokenizer's complete prompt count
to diagnose the actual request.

**The optional chart addendum is counted a token a byte.** Its UTF-8 size gives
a conservative allowance without reading the tokenizer. An item that only fits
without the addendum still gets its summary.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from idhazh.contracts.article import Article
from idhazh.extract import TOKENS_PER_WORD
from idhazh.llm.server import response_limit, window
from idhazh.measured import (
    DIGEST_PROMPT_BODY_TOKENS_A_WORD,
    DIGEST_PROMPT_SCAFFOLD_TOKENS,
)

_SCAFFOLD_TOKENS: Final = int(DIGEST_PROMPT_SCAFFOLD_TOKENS.value)
_BODY_TOKENS_A_WORD: Final = DIGEST_PROMPT_BODY_TOKENS_A_WORD.value


def response_tokens(request: Mapping[str, object]) -> int:
    """Read the effective response limit from an actual native completion request."""
    keys = [name for name in ("max_tokens", "n_predict") if name in request]
    if len(keys) != 1:
        raise ValueError("a completion request has exactly one response-token limit")
    limit = request[keys[0]]
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("a completion request's response-token limit is a positive integer")
    return limit


def request_tokens(request: Mapping[str, object], *, prompt_tokens: int) -> int:
    """The complete tokenized prompt, including replay and evidence, plus its response."""
    if prompt_tokens < 0:
        raise ValueError("a tokenized prompt count cannot be negative")
    return prompt_tokens + response_tokens(request)


def prompt_tokens(article_tokens: int, *, addendum_bytes: int = 0) -> int:
    """What the call's prompt costs for an article of this size, in tokens.

    Three terms rather than one, and each reads something.

    - the scaffold is fixed, and moves when a prompt file is edited;
    - the per-word rate covers the article, and moves when prose tokenizes
      harder than any build so far;
    - the optional chart instructions and readings are counted in UTF-8 bytes.

    `article_tokens` is spent back to words at `extract.TOKENS_PER_WORD`,
    because that is the unit the cap is enforced in and the rate above is a rate
    per word. Every constant is a reading in `idhazh.measured` carrying its
    hardware, its date and its spread (Guardrail #10).
    """
    words = int(article_tokens / TOKENS_PER_WORD)
    return _SCAFFOLD_TOKENS + int(words * _BODY_TOKENS_A_WORD) + addendum_bytes


def call_tokens(
    article_tokens: int,
    *,
    addendum_bytes: int = 0,
    sampling: Mapping[str, Any],
) -> int:
    """The prompt estimate plus the longest reply the model file lets the call write.

    The reply has no length bound of its own, since its prose fields carry none that
    this reads, so the most it can write is the model file's response limit:
    `sampling.max_tokens`, or `DEFAULT_MAX_TOKENS` where the file names none. The
    window has to hold that whether or not a plan is asked for.

    It is a sizing rather than a guarantee, and the reason is stated where each
    term is: `DIGEST_PROMPT_BODY_TOKENS_A_WORD` is the top of an eight-build spread
    rather than a bound. The seatbelt behind it is `recovered_completion`.
    """
    return prompt_tokens(article_tokens, addendum_bytes=addendum_bytes) + response_limit(sampling)


def fits_the_window(
    article: Article,
    server: Mapping[str, Any],
    *,
    addendum_bytes: int = 0,
    sampling: Mapping[str, Any],
) -> bool:
    """Whether the early estimate admits this article before the call is sent.

    It is not a measured complete-request capacity check.

    **Refusing here costs the item and admitting it costs the picture.** An
    article that does not fit is not clipped or degraded: it lands as
    `FailureCode.CONTEXT_EXCEEDED` with a row in the census. The alternative is
    the silent one - the decode runs into the end of the window, stops on an
    ordinary HTTP 200, and the item publishes looking finished with its visual
    quietly missing.

    `addendum_bytes` is the UTF-8 length of the optional chart instructions and readings.
    """
    return (
        call_tokens(article.token_count, addendum_bytes=addendum_bytes, sampling=sampling)
        <= window(server)
    )
