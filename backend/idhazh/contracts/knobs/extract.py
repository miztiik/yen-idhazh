"""How much of an article is read, and how many elements its passes may keep."""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import Model


class ExtractConfig(Model):
    truncation_cap_tokens: int = Field(
        default=2500,
        ge=256,
        description="A performance lever, not only a safety cap: prefill degrades with length.",
    )
    min_source_words: int = Field(
        default=60,
        ge=1,
        description=(
            "Below this the item publishes through the brief tier. It is derived in "
            "AppConfig from summarize.bands[0].target_words_min divided by "
            "evaluation.brief_compression_ceiling."
        ),
    )
    prose_sentence_min: int = Field(
        default=3,
        ge=1,
        description="Sentences of prose needed before a page stops carrying the not_prose signal.",
    )
    prose_sentence_words_min: int = Field(
        default=8,
        ge=1,
        description="Words a sentence needs before it counts as prose for the shape signal.",
    )
    prose_line_count_min: int = Field(
        default=12,
        ge=1,
        description="Lines needed before the line-shape guard runs.",
    )
    prose_line_ratio_min: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum share of lines that must look like prose on a line-heavy page.",
    )
    reject_not_prose: bool = Field(
        default=False,
        description="If true, a not_prose signal rejects the item. Default records and publishes.",
    )
    reject_too_short: bool = Field(
        default=False,
        description=(
            "If true, a too_short signal rejects the item. Default records and "
            "publishes, which is Owner override O3. **A feed a curator declared "
            "`abstract` is never rejected by this, whatever it is set to.** That "
            "feed publishes abstracts because a person said so, and abstracts are "
            "short by definition - rejecting one would delete a source on the "
            "strength of the property it was registered for. The signal is still "
            "recorded on its row either way: the item IS short, and the census "
            "says so. What the form changes is the consequence, never the fact."
        ),
    )
    reject_boilerplate: bool = Field(
        default=False,
        description=(
            "If true, a boilerplate signal rejects the item. Default records and publishes."
        ),
    )
    boilerplate_ratio_max: float = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description="Share of an item's lines also seen on sibling items from the same host.",
    )
    paywall_markers: list[str] = Field(
        default_factory=lambda: [
            "isaccessibleforfree\":false",
            "isaccessibleforfree\": false",
            "subscribe to continue reading",
            "register or subscribe to continue",
        ],
        min_length=1,
        description=(
            "Fallback markers used only when publisher JSON-LD does not declare the paywall."
        ),
    )
    max_body_bytes: int = Field(default=2_000_000, ge=1024)
    max_retries: int = Field(default=3, ge=0)
    backoff_initial_seconds: float = Field(default=1.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    request_timeout_seconds: float = Field(default=20.0, gt=0.0)
    user_agent: str = Field(default="yen-idhazh/1.0 (+https://github.com/miztiik/yen-idhazh)")


class ElementsConfig(Model):
    """How many candidate elements one article's passes may keep.

    A bound on work, never a judgement about which figures matter. The
    candidate pass keeps every quantity the number pattern matched, in the
    order the article wrote them, and this is the only thing that removes any
    of them - so `ElementTable.candidates_found` ships beside the table and
    says what the pass matched before this cap applied.
    """

    max_per_article: int = Field(
        default=256,
        ge=1,
        description=(
            "Candidate elements kept per article. Sized against the truncation cap "
            "rather than guessed: at 10000 tokens an article body holds about 7,692 "
            "words, and the densest committed page fixture carries 9.2 quantities per "
            "1000 characters, which is about 420 over a body that long (measured "
            "2026-09-08 on tests/fixtures/pages and tests/fixtures/canaries). It is 16 "
            "times visuals.max_facts because that one is a menu a small model reads by "
            "index and this one is a fact table nothing has to read at once. The cap "
            "was above that estimate until extract.truncation_cap_tokens doubled on "
            "2026-09-09 and now sits below it, so the densest long article keeps the "
            "first 256 quantities in article order and ElementTable.candidates_found "
            "says how many the pass matched. That is a bound on work behaving as one, "
            "not a silent loss: news prose front-loads, and the planner reads at most "
            "visuals.max_facts of the table by index."
        ),
    )
