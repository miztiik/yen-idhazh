"""Does one article's model call fit the context window?

**One call reads the article and writes the summary and, when code builds a table of
figures, the answer about a chart.** The window has to hold that request whole: the
prompt, which is the instructions, the article and the tables, and then the longest reply
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

**The tables are counted a token a byte.** A token spans at least one byte of the UTF-8 text
the tokenizer reads, so the bytes of the text the model is shown are a ceiling that needs no
reading of the tokenizer - a count in characters would not be one, because a rare character
can cost several byte-level tokens. The tables are optional: the stage reads the item without
them when they would not fit, and refuses it only when the article alone does not.
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


def prompt_tokens(article_tokens: int, *, table_bytes: int) -> int:
    """What the call's prompt costs for an article of this size, in tokens.

    Three terms rather than one, and each reads something.

    - the scaffold is fixed, and moves when a prompt file is edited;
    - the per-word rate covers the article, and moves when prose tokenizes
      harder than any build so far;
    - the tables are the UTF-8 bytes of the text the model is shown of them.

    `article_tokens` is spent back to words at `extract.TOKENS_PER_WORD`,
    because that is the unit the cap is enforced in and the rate above is a rate
    per word. Every constant is a reading in `idhazh.measured` carrying its
    hardware, its date and its spread (Guardrail #10).
    """
    words = int(article_tokens / TOKENS_PER_WORD)
    return _SCAFFOLD_TOKENS + int(words * _BODY_TOKENS_A_WORD) + table_bytes


def call_tokens(
    article_tokens: int,
    *,
    table_bytes: int,
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
    return prompt_tokens(article_tokens, table_bytes=table_bytes) + response_limit(sampling)


def fits_the_window(
    article: Article,
    server: Mapping[str, Any],
    *,
    table_bytes: int,
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

    `table_bytes` is the UTF-8 length of the text the model is shown of the tables
    for a live item, and `0` for the article alone.
    """
    return (
        call_tokens(article.token_count, table_bytes=table_bytes, sampling=sampling)
        <= window(server)
    )
