"""Assign closed-vocabulary tags to an item, deterministically and with no model.

The rule is one sentence, and it is the whole design: **a tag is assigned when
one of its curated terms appears in the item's words as a whole-word phrase,
case-folded. Nothing is derived from the tag's id or its display name.**

That last clause is the load-bearing half. Deriving terms from the id was
measured on 2026-08-26 over 1889 published items and moves lens coverage from
8.8 percent to 88.2 percent, because `ai` sits inside `said`, `remains` and
`chair`. One unstated choice moved the answer tenfold and turned a filter into
noise, so the terms are curated in `config/taxonomy.json` and this module
derives none of them.

Two properties follow from the vocabulary being a mapping keyed by an enum:

- A hostile page can win itself a tag we already publish. It can never invent
  one, and no tag ever reaches a prompt (Rule #11). The matcher reads text that
  has already crossed the trust boundary at `sanitize`.
- The same text always produces the same tags, so a re-run cannot reorder or
  re-label a day.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final

from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

_WORD: Final = re.compile(r"[a-z0-9]+")


def normalise(text: str) -> str:
    """Case-fold to space-separated words, padded so a term match is whole-word.

    Padding is what makes `in` a whole-word test: ` ai ` is not inside ` said `,
    where the bare substring `ai` is. Punctuation and hyphens are dropped on
    both sides, so `ai-roi`, `AI/ROI` and `AI ROI` are one term.
    """
    return f" {' '.join(_WORD.findall(text.lower()))} "


def terms_of(phrases: Sequence[str]) -> tuple[str, ...]:
    """The normalised, non-empty terms of one tag. A term of no words matches nothing."""
    return tuple(term for phrase in phrases if (term := normalise(phrase)) != " ")


def tags[Tag: str](vocabulary: Mapping[Tag, Sequence[str]], *parts: str | None) -> list[Tag]:
    """Every tag whose vocabulary has a term in `parts`, in id order.

    Sorted rather than in match order: the published list is part of the payload
    and must not depend on which sentence happened to mention the term first.
    """
    haystack = normalise(" ".join(part for part in parts if part))
    return sorted(
        tag for tag, phrases in vocabulary.items() if any(t in haystack for t in terms_of(phrases))
    )


def tagged(article: Article, *, taxonomy: Taxonomy, watchlist: Watchlist) -> Article:
    """The same article, carrying the lenses, events and entities its own words earn.

    Article in, article out, so this is testable on a file and orderable in the
    worker loop without knowing anything else about it. It runs on the extract
    payload, which means after `sanitize` - the tagger never reads raw fetched
    bytes.

    A failed article keeps its empty lists. It has no text, it never reaches a
    reader, and a tag on it would only be a tag on a feed title.

    Deliberately not a fingerprint input. A tag does not change a summary, so
    adding the vocabulary to the stamp would re-summarize every past item to
    produce identical words ([docs/architecture/contracts/determinism.md]).
    A vocabulary edit therefore re-tags what runs next and leaves the past
    alone, which is the same rule the rest of the config follows.
    """
    if article.status is not ArticleStatus.OK:
        return article
    return article.model_copy(
        update={
            "lenses": tags(taxonomy.lens_terms(), article.title, article.text),
            "events": tags(taxonomy.event_terms(), article.title, article.text),
            "entities": tags(watchlist.entity_terms(), article.title, article.text),
        }
    )
