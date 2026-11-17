"""The model call that reads one article, and the requests and readers around it.

**One call reads the item and writes the summary and, when code finds a chart
reachable, the visual plan.** The request is built here, with the bytes rendered by
this repository rather than by the model's chat template, and
`idhazh.stages.summarize_one_item` sends it. The visual decision belongs to
`idhazh.visual_planner`: a supported numeric chart or no visual. It stays there: it is
a different subject that happened to share a file.

**Shared instructions sit in front of the article; what differs per item follows it.**
The system turn is the summary rules, the plan rules and the type guide, which is the
same bytes on every item and is therefore read once per shard rather than once per item.
Behind it sit the item's title, its text and, when a plan is asked for, the menu of
source elements code found in it - the figures and dates its patterns matched, and the
names and places the text-analysis service labelled - and the fields the grammar will
hold this reply to. The model never sees a sentence address, because it is asked for
no location: it chooses elements by the ids code minted and writes words.

**The reply carries the summary first and the plan second, and that order is the
recovery.** A decode the output budget cuts is cut in the plan, and the summary
behind it is already closed. The two prose fields carry no length bound, so there is no
worst case to derive: the call runs under the model file's own response limit
(`sampling.max_tokens`, or `llm.server.DEFAULT_MAX_TOKENS` where the file names none).
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import lru_cache
from math import ceil
from pathlib import Path
from string import Template
from typing import Annotated, Any, Final, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, create_model

from idhazh import summarize
from idhazh.classify.label_request import (
    SENTENCE_ID_PREFIX,
    bind_label_reference_choices,
)
from idhazh.classify.label_request import (
    sentence_id as sentence_id,
)
from idhazh.classify.plan_visual_request import (
    bind_reference_choices,
    planning_menu,
    type_role_guide,
)
from idhazh.classify.read_label_reply import read_label_reply
from idhazh.config import DEFAULT_CONFIG_DIR
from idhazh.contracts.article import Article
from idhazh.contracts.base import Model as ContractModel
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.element import (
    Element,
    ElementKind,
    ElementTable,
    Extractor,
    derive_element_id,
)
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import CODE_STAMPED_FIELDS, VisualPlan, widest_json_characters
from idhazh.contracts.visual_type import VisualType
from idhazh.elements import NUMBER, SpanDriftError, read_quantity, sentence_starts, settle
from idhazh.llm.server import (
    Completion,
    TurnMarkers,
    completion_payload,
    continued_completion_payload,
    render_prompt,
)
from idhazh.load_prompt_text import load_prompt_text
from idhazh.sanitize import untrusted_block
from idhazh.visual_vocabulary import PLAN_VOCABULARY_VERSION

#: Each module that reads a raw model reply keeps its own two-line cleaner,
#: as `summarize` does. One shared cleaner is worth having and is not this
#: row's to make.
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_LABEL_JSON = TypeAdapter(dict[str, Any])


# --- The label call: the model reads the article and points at it --------------------
#
# No stage dispatches this section any more: the names and places in a table come from
# the text-analysis service. Only the measurement utility and its tests read it.
#
# One sentence governs the whole section: code finds and cuts every character a
# reader will see, and the model points at where to cut and says what the cut
# means. Everything the reply may contain is either an address code minted, a
# word from a closed list, or words the model is only allowed to describe with -
# never a figure, a position or a count.

#: The date-stamp of this labelling pass, written onto every element it judges.
#: It is `Element.ledger_version`, so a later run can tell which pass assigned a
#: judgement and re-label under a newer one without guessing. Bump it when the
#: label vocabulary or the meaning of a band changes, not when the prompt is
#: reworded - a reworded prompt still assigns the same fields.
LABEL_PASS_VERSION: Final = "2026-11-15"

#: Structural bounds on a decoder shape, in the same place and for the same
#: reason `VisualDraft` carries its own: a `maxItems` is a hard grammar stop, so
#: it bounds the reply before a byte of it is written rather than after. These
#: are not the tunables Guardrail #6 sends to `config/` - moving one changes what the
#: decoder can emit at all, which is a contract change and not an operator's
#: dial, and a grammar is fixed before a request is built. The per-article
#: proposal cap decision 3 asks for is `PROPOSED_MAX`.
#:
#: `LABELS_MAX` is the count `visuals.max_facts` already names, for the reason
#: that knob gives: a long indexed menu is lost-in-the-middle for a model
#: picking by address. It is not the size of the table - a dense article can
#: hold 256 candidates and the labels are for choosing between them, not for
#: covering them, so twice a full chart's width is enough to choose with. What
#: a maximal reply costs in output tokens, and what budget it needs, is
#: `label_budget_tokens` below - so moving one of these is moving the budget.
LABELS_MAX: Final = 16
PROPOSED_MAX: Final = 4
#: One typed collection retains the combined capacity of the former two lists.
NAMED_MAX: Final = 12
MENTIONS_MAX: Final = 4
#: The most elements one reply can add to a table by pointing at the article:
#: the mention list filled to its bound. It is arithmetic rather than a knob, so it
#: cannot drift away from what the grammar can emit.
ANCHORED_MAX: Final = NAMED_MAX * MENTIONS_MAX
#: An address is `quantity-118-123` or `s7`. Nothing legitimate is longer, and a
#: reply that pads one has written a string no lookup will find.
ADDRESS_MAX: Final = 48
#: Words, not sentences. A `measure` is what a figure measures and a `surface`
#: is the few words a figure was written in; either one running long is a reply
#: copying the article rather than pointing into it.
PHRASE_MAX: Final = 60

Address = Annotated[str, StringConstraints(min_length=1, max_length=ADDRESS_MAX)]
Phrase = Annotated[str, StringConstraints(min_length=1, max_length=PHRASE_MAX)]

#: These identify the prompt's text encoding, not a configurable output format.
SENTENCE_PRESENTATION: Final = "The item, one JSON string per addressed sentence:"
#: JSON already escapes ASCII controls; these also split physical lines.
_SENTENCE_LINE_CONTROLS: Final = str.maketrans(
    {"\x85": r"\u0085", "\u2028": r"\u2028", "\u2029": r"\u2029"}
)


class Citation(BaseModel):
    """Exact source words whose unique article location is computed by code."""

    model_config = ConfigDict(extra="forbid")

    surface: Phrase


class ElementLabel(BaseModel):
    """The meaning and named subject of one source quantity, decoded after its address."""

    model_config = ConfigDict(extra="forbid")

    element_id: Address
    measure: str = Field(max_length=PHRASE_MAX)
    entity: str = Field(max_length=PHRASE_MAX)


class NamedMentions(BaseModel):
    """One chart-relevant named thing and its source mentions.

    Mentions anchor before the kind and group name are interpreted. Only source
    spans supply display words. The name resolves known aliases, never supplies
    a display label or mints an identity.
    """

    model_config = ConfigDict(extra="forbid")

    mentions: list[Citation] = Field(max_length=MENTIONS_MAX)
    kind: Literal["entity", "place"]
    name: Phrase


class LabelReply(BaseModel):
    """Current quantity labels and source phrases, closed to unknown keys.

    Code resolves values, units and locations from the article. The decoder
    authors no sentence ids, numeric fields or offsets. Named mentions identify
    source words and known subjects, never reader-facing tags.
    """

    model_config = ConfigDict(extra="forbid")

    labels: list[ElementLabel] = Field(max_length=LABELS_MAX)
    proposed: list[Citation] = Field(max_length=PROPOSED_MAX)
    named_mentions: list[NamedMentions] = Field(max_length=NAMED_MAX)

class ParsedCitation(BaseModel):
    """Validated source words with optional historical sentence-local context."""

    model_config = ConfigDict(extra="forbid")

    surface: Phrase
    legacy_sentence_id: Address | None = Field(default=None, exclude=True)


class ParsedNamedMentions(BaseModel):
    """Validated source citations and their named chart subject."""

    model_config = ConfigDict(extra="forbid")

    mentions: list[ParsedCitation]
    kind: Literal["entity", "place"]
    name: Phrase


class ParsedLabelReply(BaseModel):
    """Validated current or historical evidence, never a request grammar."""

    model_config = ConfigDict(extra="forbid")

    labels: list[ElementLabel]
    proposed: list[ParsedCitation]
    named_mentions: list[ParsedNamedMentions]


def label_schema() -> dict[str, Any]:
    return LabelReply.model_json_schema()


#: The one reading of how densely a real label-call reply tokenises, kept as the two
#: numbers it was read from rather than as a decimal, so nobody takes 3.12 for a
#: tuned value. The reply that made this budget necessary decoded exactly 900
#: tokens and `parse_label` failed at character 2,805 of it - measured
#: 2026-09-12 on `Qwen3.5-9B-Q4_K_M` under grammar-constrained decoding, one
#: reply, no spread
#: (`docs/reference/benchmarks/instructions-in-front.md`).
MEASURED_REPLY_CHARACTERS: Final = 2805
MEASURED_REPLY_TOKENS: Final = 900
#: **An estimate, and it is labelled one** (Guardrail #10). It is taken from a
#: reply that was filling its lists, which is the composition the character
#: ceiling below describes, so it is the right sample to extrapolate a ceiling
#: from even at one reading. What overturns it: decode twenty corpus articles
#: through the label call at a budget no reply reaches, record characters and tokens per
#: reply, and take the LOWEST ratio. Under this figure the constant moves; under
#: about 1.55 the design moves, because that is where the derived budget stops
#: fitting the window the two calls share.
CHARS_PER_OUTPUT_TOKEN: Final = MEASURED_REPLY_CHARACTERS / MEASURED_REPLY_TOKENS


def label_budget_tokens() -> int:
    """The label call's output budget, derived from the reply shape's own bounds.

    **Not picked, and not the summariser role's number.** Every array in
    `LabelReply` carries a `maxItems` and every decoded string a `maxLength`,
    so the longest reply the grammar admits is arithmetic over the bounds, and
    the arithmetic runs again on every import - move a bound and this number
    moves with it, without anybody remembering to. Until 2026-09-13 the budget
    was the summariser role's own, sized for a summary and knowing nothing about
    this shape, and one ordinary 346-word article lost its whole item to it.
    That role-level number is gone entirely since 2026-09-21, so this arithmetic
    is the only thing that bounds the call.

    **The ceiling is converted at the one measured density**, which
    is what `CHARS_PER_OUTPUT_TOKEN` holds and what makes this a sizing rather
    than a guarantee: the budget is the brake, and a budget large enough to be an
    unbreakable ceiling would leave no window for the article it is reading.
    The label call's seatbelt is that a cut is reported as a cut, typed, rather
    than raised as a JSON error several frames from the cause
    (`FailureCode.LABELS_TRUNCATED`).

    The current three-field schema is the only input to that width. Historical
    observations are read-only compatibility and consume no current output or
    context allowance.
    """
    return ceil(widest_json_characters(label_schema()) / CHARS_PER_OUTPUT_TOKEN)


#: The budget the committed bounds produce, written down as well as computed: a
#: number that only exists inside a function is a number nobody re-derives, and
#: a bound can then move without anybody seeing what it cost.
LABEL_BUDGET_TOKENS: Final = 2738

if label_budget_tokens() != LABEL_BUDGET_TOKENS:
    raise TypeError(
        "a bound moved and the label call's output budget did not follow it - the reply shape "
        f"now needs {label_budget_tokens()} tokens against a recorded "
        f"{LABEL_BUDGET_TOKENS}; re-derive it in `label_budget_tokens`"
    )


def label_system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """Both jobs, in one turn, in front of the article.

    Three files joined here rather than one file holding all of it. The turn
    behind the article is a fourth, and it is not joined here: its `$write`
    placeholder names the fields one reply's grammar holds, which is not the same
    on every item, and a stray one in this turn would render to a model as the
    literal `$write`. Kept apart, one test states the whole invariant - the
    rendered system prompt carries no `$`, and the moved template's placeholder
    set is exactly the config-level names.

    Elements, then the summary, then the plan, because everything the plan half
    points at - an address, the table - is defined in the elements half, so the
    definition comes before the use.

    **It takes no article and never will.** That is what makes it the same bytes
    on every item, which is the whole basis of the prefix cache: one cache slot
    at `n_parallel = 1`, so a system turn that varied per item would evict the
    article on every alternation and cost far more than it saved.
    """
    ask = prompt_config or SummarizeConfig()
    files = prompt_files or PromptFilesConfig()
    return "\n".join(
        (
            Template(load_prompt_text(config_dir, files.generate_labels)).substitute(),
            _summary_half(files, config_dir).substitute(
                max_verbatim_words=ask.max_verbatim_words,
            ),
            _plan_half(files, config_dir, visuals or VisualsConfig()),
        )
    )


def sentence_number(address: str) -> int | None:
    """The sentence an address names, or nothing when it names none."""
    if not address.startswith(SENTENCE_ID_PREFIX):
        return None
    digits = address[len(SENTENCE_ID_PREFIX) :]
    return int(digits) if digits.isdigit() else None


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Where every sentence of the article starts and ends.

    Built from `elements.sentence_starts`, so the sentence a proposal names and
    the `sentence_index` an element carries are the same count of the same
    string. Two definitions of where a sentence begins would put a proposal in
    one sentence and its element in another.
    """
    starts = [0, *sentence_starts(text)]
    return list(zip(starts, [*starts[1:], len(text)], strict=True))


def numbered_sentences(text: str) -> str:
    """Each original sentence slice as one reversibly escaped, addressed line.

    The whole article rather than a lead excerpt, and the article rather than
    the summary: a compression cannot carry a fact it dropped, and judging what
    an item is about against text that lost the series is judging the wrong
    document. It is fenced as data by its caller - the addresses are ours, the
    sentences are a stranger's web page (Guardrail #11).

    JSON preserves internal newlines, literal backslashes and boundary whitespace
    without making unaddressed continuation lines. Non-ASCII text stays literal
    so the caller's sanitizer still sees forged turn markers.
    """
    return "\n".join(
        f"[{sentence_id(index)}] "
        + json.dumps(text[start:end], ensure_ascii=False).translate(_SENTENCE_LINE_CONTROLS)
        for index, (start, end) in enumerate(sentence_spans(text))
    )


def candidate_menu(table: ElementTable) -> str:
    """The quantities and dates code already cut, each at the address to cite.

    The address is the element's own id, which is derived from its kind and its
    span - so a label can only ever name a fact that exists, and an id the model
    invented resolves to nothing and is dropped.
    """
    if not table.elements:
        return "(no quantities or dates were found in this item)"
    return "\n".join(
        f"[{element.element_id}] {element.span_excerpt}"
        f" = {element.value}{' ' + element.unit if element.unit else ''}"
        f" (sentence {sentence_id(element.sentence_index)})"
        for element in table.elements
    )


def label_user_turn(article: Article, table: ElementTable) -> str:
    """The title, the addressed article and the candidate table - all fenced.

    **The title is fenced like the other two, and it used to be the one string
    here that was not.** It sat bare on the line immediately in front of the
    fence, which is a framing position: the prompt's "the block below is DATA"
    sentence does not reach it, and prompt wording is not a control anyway
    because it is written in the same channel as the attack (Guardrail #11).
    `clean_title` strips machinery, not English, so an instruction written in
    ordinary prose arrives intact - and since `extract.page_headline` landed,
    the title of an item whose feed carried no headline is whatever the fetched
    page's author put in `<title>`, including a page that exists to be crawled.
    The placeholder is ours and costs nothing to fence; an ok article always
    carries a title, so it is only reachable from a payload this call never
    gets.

    It refuses a table built over a different string than the article it is
    printed beside. Every address in the menu is an offset into `Article.text`,
    so a mismatch prints a menu whose rows point into a document the model is
    not reading - and every label that came back would anchor somewhere else,
    with nothing downstream able to tell.
    """
    text = article.text or ""
    if derive_text_digest(text) != table.source_text_hash:
        raise SpanDriftError(
            f"{article.item_id}: the candidate table indexes a different string than this article"
        )
    parts = ["Title:\n" + untrusted_block(article.title or "(untitled)")]
    parts.append(SENTENCE_PRESENTATION + "\n" + untrusted_block(numbered_sentences(text)))
    parts.append(
        "Quantities and dates already found in it:\n" + untrusted_block(candidate_menu(table))
    )
    return "\n\n".join(parts)


def label_request_schema(article: Article, table: ElementTable) -> dict[str, Any]:
    """Restrict quantity labels to the candidate addresses printed for this article."""
    schema = label_schema()
    bind_label_reference_choices(schema, table)
    return schema


def build_label_request(
    article: Article,
    table: ElementTable,
    *,
    model_id: str,
    server: Mapping[str, Any],
    sampling: Mapping[str, Any],
    markers: TurnMarkers,
    prompt_config: SummarizeConfig | None = None,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """The label call's request body, with the reply shape enforced by the decoder.

    The prompt bytes are rendered here rather than by the model's chat
    template, which is what lets the summarize-and-plan call open with them unchanged. The output
    budget is derived from the compatible native reply shape, not the narrower
    article-specific choices. There is no role-level budget behind it: the
    settings block carried one until 2026-09-21 and it sized neither shape.

    `prompt_config` reaches the label call because the system turn carries both jobs
    now. Every number it spends is a config-level one, the same on every item,
    so the turn is still the same bytes on every item.

    `markers` are read off the template of the weights this body will be sent
    to, so a model whose turns differ costs no edit at all.
    """
    return completion_payload(
        model_id=model_id,
        system=label_system_prompt(
            prompt_config, visuals=visuals, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=label_user_turn(article, table),
        output_schema=label_request_schema(article, table),
        server=server,
        sampling=sampling,
        markers=markers,
        max_answer_tokens=label_budget_tokens(),
    )


def parse_label(raw: str) -> ParsedLabelReply:
    content = raw.strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    data = _LABEL_JSON.validate_json(content)
    historical = read_label_reply(data)
    if historical is not None:
        return ParsedLabelReply.model_validate(historical)
    current = LabelReply.model_validate(data)
    return ParsedLabelReply.model_validate(current.model_dump())


def _judgements(
    label: ElementLabel,
    *,
    entity_slugs: Mapping[str, str],
    label_source: str,
) -> dict[str, Any]:
    """The quantity's stated meaning and a known subject, without unused judgments."""
    judged: dict[str, Any] = {}
    if measure := label.measure.strip():
        judged["measure"] = measure
    # The model names an entity in the item's words; the slug it groups under is
    # the watchlist's. An unknown name is a name we do not track yet, not a new
    # entity this pass may mint - the alias ledger is a later row's work.
    if (slug := entity_slugs.get(label.entity.strip().casefold())) is not None:
        judged["entity"] = slug
    if judged:
        judged["label_source"] = label_source
        judged["ledger_version"] = LABEL_PASS_VERSION
    return judged


def apply_labels(
    table: ElementTable,
    reply: ParsedLabelReply,
    *,
    label_source: str,
    entity_slugs: Mapping[str, str] | None = None,
) -> ElementTable:
    """The reply's judgements written onto the candidates they cite.

    **A label citing an address the pass never minted is dropped, and its
    siblings stand.** That is the whole adjudication for this shape: a label
    carries no location of its own, so an id that resolves to nothing leaves
    nothing to anchor and the rejection costs one label rather than the article
    (section 1a, degrade rather than fail).

    The first citation of an address wins. A second one is a second opinion
    about one fact, and taking the last would make the result depend on decode
    order for no stated reason.

    Nothing here is written with `model_copy`, which does not validate: every
    element is rebuilt through the contract, so a judgement the shape refuses
    fails here rather than at whatever reads the table next.
    """
    known = {
        element.element_id for element in table.elements if element.kind is ElementKind.QUANTITY
    }
    judged: dict[str, dict[str, Any]] = {}
    for label in reply.labels:
        if label.element_id not in known or label.element_id in judged:
            continue
        judged[label.element_id] = _judgements(
            label,
            entity_slugs=entity_slugs or {},
            label_source=label_source,
        )
    elements = [
        Element.model_validate(element.model_dump() | judged[element.element_id])
        if element.element_id in judged
        else element
        for element in table.elements
    ]
    return ElementTable.model_validate(table.model_dump() | {"elements": elements})


def _locate(
    text: str, spans: Sequence[tuple[int, int]], citation: ParsedCitation
) -> tuple[int, int] | None:
    """Locate one exact occurrence, retaining historical sentence-local semantics."""
    first, last = 0, len(text)
    if citation.legacy_sentence_id is not None:
        index = sentence_number(citation.legacy_sentence_id)
        if index is None or index >= len(spans):
            return None
        first, last = spans[index]
    surface = citation.surface.strip()
    if not surface:
        return None
    start = text.find(surface, first, last)
    if start < 0 or text.find(surface, start + 1, last) >= 0:
        return None
    return start, start + len(surface)


def proposed_quantities(text: str, reply: ParsedLabelReply) -> list[Element]:
    """The figures the pattern missed, cut out of the article's own bytes.

    The model copies a short phrase; code locates it exactly once and re-reads
    its value and unit using the candidate pass's own number reader. Historical
    citations retain their original sentence scope.

    Three refusals, and each one is ambiguity rather than a near miss:

    - an invalid historical sentence address,
    - a surface that occurs twice in its scope or not at all - the mis-pointing failure
      no span check can see, so ambiguity is refused rather than guessed,
    - a surface holding no readable figure, or holding two. A number spelled out
      in words and a relative change stay refused here, because there is nothing
      for the pattern to parse.

    The first two are `_locate`, which the mention producer shares, because the
    rule is one rule and two copies of it would drift.

    Stamped `Extractor.MODEL`, which is this contract's word for the path
    decision 3 spells `model_proposed`: the model proposed the location and code
    cut the characters at it. The later rows' kinds are model-pointed the same
    way and are not proposals, so the field names the path rather than the shape.
    """
    spans = sentence_spans(text)
    starts = sentence_starts(text)
    found: list[Element] = []
    for citation in reply.proposed:
        located = _locate(text, spans, citation)
        if located is None:
            continue
        offset, limit = located
        readings = [
            (match, reading)
            for match in NUMBER.finditer(text, offset, limit)
            if (reading := read_quantity(match)) is not None
        ]
        if len(readings) != 1:
            continue
        match, reading = readings[0]
        span_start, span_end = match.start(), reading.span_end
        found.append(
            Element(
                element_id=derive_element_id(ElementKind.QUANTITY, span_start, span_end),
                kind=ElementKind.QUANTITY,
                span_start=span_start,
                span_end=span_end,
                span_excerpt=text[span_start:span_end],
                value=reading.value,
                unit=reading.unit,
                sentence_index=bisect_right(starts, span_start),
                extractor=Extractor.MODEL,
            )
        )
    return found


class MentionGroup(NamedTuple):
    """One named thing, and the mentions of it that anchored to the article.

    `elements` is never empty: a group whose every mention was refused is not a
    group, it is a name nobody can point at, and it is dropped (decision 2).
    """

    name: str
    elements: list[Element]


def drawn_label(group: MentionGroup) -> str:
    """What a page may show for a named thing: the longest mention it anchored.

    **Never `name`.** That is invariant 2 of the extraction drawing and it is the
    one an implementer is most likely to lose, because drawing the name is easier
    and looks tidier. The name is model-authored words with no span; a mention is
    the article's own characters at an offset code computed, so it is the only
    one of the two a reader can check against the item.

    The longest, because it is the most informative surviving form - an item that
    wrote "Vestas Wind Systems A/S" once and "Vestas" four times tells a reader
    more with the first. A tie takes the earliest, which is the order the article
    wrote them.
    """
    return max(group.elements, key=lambda one: len(one.span_excerpt)).span_excerpt


def mention_elements(
    text: str,
    groups: Sequence[ParsedNamedMentions],
    *,
    label_source: str,
    entity_slugs: Mapping[str, str],
) -> list[MentionGroup]:
    """Every place the item names a thing, cut out of the item's own bytes.

    **The name is never searched for** (decision 1). An item writes the fullest
    form once and a short form four times, and the fullest form may appear
    nowhere verbatim - so searching for it would reject the thing it was meant to
    find. Each mention is located by `_locate` instead: exactly once in the
    article, or within its validated historical sentence.

    Each surviving mention is one Tier 1 element carrying the article's
    characters. The name is Tier 2 and lands only as `Element.entity`, and only
    when it is a slug this project already tracks - an unknown name is one we do
    not track yet, and minting a slug for it would put two spellings of one
    organisation in two groups for ever.

    Rejection is per mention and then per group, never per article (decision 5):
    a mention that will not anchor drops itself, a group that anchored none of
    its mentions drops itself, and the item's other elements stand.
    """
    spans = sentence_spans(text)
    starts = sentence_starts(text)
    grouped: list[MentionGroup] = []
    for group in groups:
        name = group.name.strip()
        judged: dict[str, Any] = {}
        if (slug := entity_slugs.get(name.casefold())) is not None:
            judged = {
                "entity": slug,
                "label_source": label_source,
                "ledger_version": LABEL_PASS_VERSION,
            }
        found: list[Element] = []
        for citation in group.mentions:
            located = _locate(text, spans, citation)
            if located is None:
                continue
            span_start, span_end = located
            found.append(
                Element(
                    element_id=derive_element_id(ElementKind(group.kind), span_start, span_end),
                    kind=ElementKind(group.kind),
                    span_start=span_start,
                    span_end=span_end,
                    span_excerpt=text[span_start:span_end],
                    value=None,
                    unit=None,
                    sentence_index=bisect_right(starts, span_start),
                    extractor=Extractor.MODEL,
                    **judged,
                )
            )
        if name and found:
            grouped.append(MentionGroup(name=name, elements=found))
    return grouped


def model_anchored(
    text: str,
    reply: ParsedLabelReply,
    *,
    label_source: str,
    entity_slugs: Mapping[str, str],
) -> tuple[list[MentionGroup], list[Element]]:
    """Anchor entity/place mentions in the article using their validated source scope.

    The groups are returned beside the flat list because a
    drawn label is a property of a group and not of one element.
    """
    groups = mention_elements(
        text, reply.named_mentions, label_source=label_source, entity_slugs=entity_slugs
    )
    pointed = [element for group in groups for element in group.elements]
    return groups, pointed


def anchored(
    table: ElementTable,
    text: str,
    reply: ParsedLabelReply,
    *,
    config: ElementsConfig,
    label_source: str,
    entity_slugs: Mapping[str, str] | None = None,
) -> ElementTable:
    """One candidate table, plus what the model recovered and what it said.

    `text` is the `Article.text` the table was built over - the same string its
    spans index. Pass anything else and every offset points somewhere else.

    A proposal that overlaps an element the pass already holds is dropped before
    anything is settled. `proposed` is the recovery for a figure the pattern
    **missed**, so a second reading of a stretch of characters code already read
    is not a recovery; leaving it to `settle` would let the later pass take a
    span off the earlier one on nothing better than which offset came first.

    **The merged table is bounded by `max_per_article` plus the proposal cap
    plus `ANCHORED_MAX`, not by `max_per_article` alone.** The pattern's own
    bound is the thing a recovery is most often needed past: a dense article
    keeps the first 256 figures in article order and the ones after that are
    exactly what nobody can label. Spending the recovery out of the pattern's
    budget would make the escape hatch unreachable on the articles that need it,
    and every addition is bounded by the grammar, so the total is still a stated
    bound on work. Nothing is ever evicted here - the merge only adds.

    Mentions are added after settling the numeric passes. Two mentions claiming
    the same kind and span keep the first. Labels apply only to source quantities.

    `candidates_found` counts every proposal that read as a figure and every
    mention that anchored, including the ones dropped next. It is one
    count per pass taken before the rules that remove, which is what keeps it
    able to say the cap bit and by how much.
    """
    slugs = entity_slugs or {}
    proposals = proposed_quantities(text, reply)
    taken = [(element.span_start, element.span_end) for element in table.elements]
    fresh = [
        element
        for element in proposals
        if not any(start < element.span_end and element.span_start < end for start, end in taken)
    ]
    found = dict(table.candidates_found)
    found[ElementKind.QUANTITY] = found.get(ElementKind.QUANTITY, 0) + len(proposals)
    merged = ElementTable.model_validate(
        table.model_dump()
        | {
            "elements": settle([*table.elements, *fresh])[
                : config.max_per_article + PROPOSED_MAX
            ],
            "candidates_found": found,
        }
    )
    labelled = apply_labels(merged, reply, label_source=label_source, entity_slugs=slugs)

    _, pointed = model_anchored(text, reply, label_source=label_source, entity_slugs=slugs)
    for kind, count in Counter(element.kind for element in pointed).items():
        found[kind] = found.get(kind, 0) + count
    seen = {element.element_id for element in labelled.elements}
    kept = list(labelled.elements)
    for element in pointed:
        if element.element_id in seen:
            continue
        seen.add(element.element_id)
        kept.append(element)
    whole = ElementTable.model_validate(
        labelled.model_dump()
        | {
            "elements": sorted(kept, key=lambda one: one.span_start)[
                : config.max_per_article + PROPOSED_MAX + ANCHORED_MAX
            ],
            "candidates_found": found,
        }
    )
    if (drift := whole.span_drift(text)) is not None:
        raise SpanDriftError(f"the label call cannot re-slice its own output: {drift}")
    return whole


# --- The summarize-and-plan call: the summary and the plan -------------------------


class SummarizeAndPlanReply(NamedTuple):
    """What the summarize-and-plan call came back with, as the two contracts it stands for.

    The decoder shape is not this. That one carries neither of the fields code
    stamps; it exists to be a grammar and it stops at
    `parse_summarize_and_plan`. What a caller gets is a summary draft the summarizer's own
    gates can read and a plan the validator can rule on.

    `visual` is `None` when the reachability gate took the plan fields off the
    request. That is an answer rather than an absence: no plan was asked for, so
    none came back, and the item's `none_reason` is `not_reachable`.
    """

    summary: summarize.SummaryDraft
    visual: VisualPlan | None


def _pointer_template(files: PromptFilesConfig, config_dir: Path) -> Template:
    return Template(load_prompt_text(config_dir, files.continue_summary))


def _summary_half(files: PromptFilesConfig, config_dir: Path) -> Template:
    return Template(load_prompt_text(config_dir, files.write_digest_summary))


def _plan_half(files: PromptFilesConfig, config_dir: Path, visuals: VisualsConfig) -> str:
    return "\n".join(
        (
            Template(load_prompt_text(config_dir, files.plan_visual)).substitute(),
            type_role_guide(visuals),
        )
    )


@lru_cache(maxsize=2)
def _plan_draft_model(legacy_references: bool = False) -> type[BaseModel]:
    """The plan as the decoder meets it: `VisualPlan` without the fields code stamps.

    Derived from `VisualPlan.model_fields` rather than restated, so a field
    added to the contract appears here on the next import and cannot be
    forgotten. Versions and the collected reference set are code-owned.
    Historical raw replies retain their original bounded reference list.

    The contract's own validators are deliberately **not** carried over. This
    shape is the grammar and nothing else; whether a plan that declines also
    left its type null is `VisualPlan`'s rule, and it is asked when the decoded
    body is turned into the contract, which is where a failure names the plan
    rather than the parse.
    """
    fields: dict[str, Any] = {
        name: (info.annotation, info)
        for name, info in VisualPlan.model_fields.items()
        if name not in CODE_STAMPED_FIELDS or (legacy_references and name == "element_ids")
    }
    return create_model("VisualPlanDraft", __base__=ContractModel, **fields)


@lru_cache(maxsize=16)
def _summarize_and_plan_model(
    draft: type[BaseModel], legacy_references: bool = False
) -> type[BaseModel]:
    """Keyed on the summary draft shape, which is a hashable type."""
    return create_model(
        "SummarizeAndPlanReply",
        __base__=ContractModel,
        summary=(draft, Field(description="The reader's summary. Decoded first, and whole.")),
        visual=(
            _plan_draft_model(legacy_references),
            Field(description="The plan for one picture, or none."),
        ),
    )


def summarize_and_plan_model(
    *,
    plan: bool = True,
    legacy_references: bool = False,
) -> type[BaseModel]:
    """What the decoder is constrained to emit on the summarize-and-plan call.

    **`summary` is declared before `visual`, and the order is load-bearing.**
    Field order is decode order, so the summary is written and closed before the
    plan is started. Two things follow from that and neither is cosmetic.

    A reply the output budget cuts is cut in the plan, and a grammar-constrained
    decoder closes each sub-object as it finishes it - so the summary that came
    back is closed, balanced and independently parseable. `recovered_completion`
    is that guarantee spent: the item publishes with its summary and no picture,
    at no extra seconds and with no second request. Reversed, the same cut would
    lose the summary, which is the part a reader came for.

    And the plan is drafted with the summary already in context. That is
    conditioning, not sourcing: `element_ids` may cite only an element the
    article's own table carries, so a plan cannot draw a figure the summary
    happened to mention and the table does not hold.

    **`plan=False` is the reachability gate spent, and it is the grammar that
    spends it.** The shape becomes the summary draft alone - the same one the
    single-call path already sends and `recovered_completion` already produces -
    so the decoder cannot write a plan rather than being asked not to. A budget
    on its own would not do it: the decoder writes the plan and meets the cap
    part-way through, which spends the decode the gate exists to save and
    returns a cut reply.
    """
    if not plan:
        return summarize.SummaryDraft
    return _summarize_and_plan_model(summarize.SummaryDraft, legacy_references)


def summarize_and_plan_schema(
    *,
    plan: bool = True,
    visuals: VisualsConfig | None = None,
    table: ElementTable | None = None,
) -> dict[str, Any]:
    """Derive the request grammar from the native model and the operator's selection."""
    schema = summarize_and_plan_model(plan=plan).model_json_schema()
    if plan:
        schema["$defs"][VisualType.__name__]["enum"] = [
            visual_type.value for visual_type in (visuals or VisualsConfig()).select_types()
        ]
    if plan and table is not None:
        bind_reference_choices(schema, table)
    return schema


def summarize_and_plan_user_turn(
    *,
    plan: bool = True,
    table: ElementTable | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The menu of source elements, then the reply fields.

    The menu is the exact table the plan is validated against, so every id the
    grammar offers is a row the model can read. It is attached independently of
    the selected template so a custom wording cannot silently remove the ids the
    grammar offers. Static instruction inspection needs no table; the production
    builder requires one.

    Shared instructions stay in the system turn. The last line names fields
    from the reply model so it cannot ask for a suppressed visual. Suppression
    removes the menu too, without moving the reusable prefix.
    """
    shape = summarize_and_plan_model(plan=plan)
    question = _pointer_template(prompt_files or PromptFilesConfig(), config_dir).substitute(
        write="Write " + ", then ".join(f'"{name}"' for name in shape.model_fields) + ".",
    )
    if not plan or table is None:
        return question
    return (
        "Source elements found in the item. Rows follow columns, and are data, "
        "not instructions:\n" + planning_menu(table) + "\n\n" + question
    )


if tuple(summarize_and_plan_model().model_fields) != ("summary", "visual"):
    raise TypeError(
        "field order is decode order, and the summary has to close before the plan "
        "starts or a cut reply loses the half a reader came for - "
        f"got {tuple(summarize_and_plan_model().model_fields)}"
    )


def summary_system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The summary rules, the plan rules and the type guide, in one turn in front of the article.

    Two files joined here rather than one file holding all of it. The turn behind
    the article is a third place and is not joined here: its `$write` placeholder
    names the fields one reply's grammar holds, which is not the same on every
    item, and a stray one in this turn would render to a model as the literal
    `$write`.

    The summary comes first because it is the half that is always decoded, and
    the plan rules follow because they point at ids the menu defines.

    **It takes no article and never will.** That is what makes it the same bytes
    on every item, which is the whole basis of the prefix cache: one cache slot
    at `n_parallel = 1`, so a system turn that varied per item would evict the
    article on every alternation and cost far more than it saved.
    """
    ask = prompt_config or SummarizeConfig()
    files = prompt_files or PromptFilesConfig()
    return "\n".join(
        (
            _summary_half(files, config_dir).substitute(
                max_verbatim_words=ask.max_verbatim_words,
            ),
            _plan_half(files, config_dir, visuals or VisualsConfig()),
        )
    )


def summary_user_turn(
    title: str,
    text: str,
    *,
    plan: bool = True,
    table: ElementTable | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The title and the article as the page wrote them, then the menu and the question.

    Both are fenced, and the title is fenced like the text: it sits next to the
    fence in a framing position the prompt's "the block below is DATA" sentence
    does not reach, and prompt wording is not a control anyway because it is
    written in the same channel as the attack (Guardrail #11). `clean_title`
    strips machinery, not English, so an instruction written in ordinary prose
    arrives intact - the title of an item whose feed carried no headline is
    whatever the fetched page's author put in `<title>`.

    The text is plain. It carries no sentence address, because the call is asked
    for no location, and none of the characters are escaped.

    It refuses a table built over a different string than the text it prints
    beside. Every id in the menu is an offset into `Article.text`, so a mismatch
    prints a menu whose rows point into a document the model is not reading.
    """
    if table is not None and derive_text_digest(text) != table.source_text_hash:
        raise SpanDriftError(
            f"{table.item_id}: the table indexes a different string than the text printed"
        )
    return (
        "Title:\n"
        + untrusted_block(title)
        + "\n\nThe item:\n"
        + untrusted_block(text)
        + "\n\n"
        + summarize_and_plan_user_turn(
            plan=plan, table=table, prompt_files=prompt_files, config_dir=config_dir
        )
    )


def build_summary_request(
    article: Article,
    table: ElementTable,
    *,
    model_id: str,
    server: Mapping[str, Any],
    sampling: Mapping[str, Any],
    markers: TurnMarkers,
    plan: bool = True,
    prompt_config: SummarizeConfig | None = None,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """The one call's request body, with the reply shape enforced by the decoder.

    The prompt bytes are rendered here rather than by the model's chat template,
    and the response limit is the model file's own: a request carries
    `sampling.max_tokens` where the file names one and `DEFAULT_MAX_TOKENS` where
    it does not.

    **`plan=False` is the reachability gate spent, and it is the grammar that
    spends it.** The reply shape becomes the summary draft alone, so the decoder
    cannot write a plan rather than being asked not to, and the menu stays out of
    the prompt with it. `table` is the exact table the plan is validated against,
    so its ids are the only ones the grammar offers.

    `markers` are read off the template of the weights this body will be sent to,
    so a model whose turns differ costs no edit at all.
    """
    return completion_payload(
        model_id=model_id,
        system=summary_system_prompt(
            prompt_config, visuals=visuals, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=summary_user_turn(
            article.title or "(untitled)",
            article.text or "",
            plan=plan,
            table=table,
            prompt_files=prompt_files,
            config_dir=config_dir,
        ),
        output_schema=summarize_and_plan_schema(plan=plan, visuals=visuals, table=table),
        server=server,
        sampling=sampling,
        markers=markers,
    )


def build_summarize_and_plan_request(
    first: Mapping[str, Any],
    reply: str,
    table: ElementTable,
    *,
    markers: TurnMarkers,
    plan: bool = True,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """The summarize-and-plan call's request body, built by extending the label call's prompt.

    `first` is the payload the label call was sent and `reply` is what came back, so
    the summarize-and-plan call's prompt is not "the same bytes as" the label call's - it opens with
    the same string object. That is the point of taking them as arguments: a prefix cache
    reuses the longest common prefix of the tokenised prompt, and nothing about
    a broken prefix is loud.

    **The label call's system prompt is reused rather than replaced.** A prompt of the
    summarize-and-plan call's own would end the common prefix at the first turn marker, and the
    whole article would prefill a second time - roughly double the stage's wall clock
    for a wording nobody could measure the benefit of.

    The two calls belong **adjacent, per item**. the summarize entry
    pins `n_parallel` to 1, so the server holds one cache slot: every label call
    first and every summarize-and-plan call after would evict the prefix before it was reused,
    every time, with nothing in any log to say so. Owning the bytes makes a
    mis-ordering more expensive rather than less - what an eviction now costs is
    the prompt and the reply behind it.

    `table` is the exact post-anchoring table used by reachability and validation.
    Its menu and reference choices are request-local; the native plan stays
    unchanged. Suppression removes the menu and the plan grammar after the
    shared prefix, never from that prefix.

    **The reply is held to the model file's response limit and to nothing
    narrower.** `first` carries it as `max_tokens` where the file names one, and
    `continued_completion_payload` sends `DEFAULT_MAX_TOKENS` where it does not.
    """
    return continued_completion_payload(
        first,
        reply=reply,
        user=summarize_and_plan_user_turn(
            plan=plan,
            table=table,
            prompt_files=prompt_files,
            config_dir=config_dir,
        ),
        output_schema=summarize_and_plan_schema(plan=plan, visuals=visuals, table=table),
        markers=markers,
    )


def prompt_inputs(
    prompt_config: SummarizeConfig | None = None,
    *,
    markers: TurnMarkers,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """What the fingerprint hashes to stand for this call's prompt.

    `summarize.prompt_inputs` is the standalone summary's answer to the same
    question and this is the digest call's, for the same reason and with the same
    shape: the bytes that do not vary with the article, plus every setting that
    can change them. A stamp that moved per item could not answer the question
    the stamp exists to answer.

    **The rendering is what makes the turn envelope a digested input.** Since
    the prompt bytes became ours, the markers the server derives decide where
    every turn opens and closes, and nothing else in the stamp reaches them: the
    chat template hashed off `/props` no longer renders these prompts. A model
    whose template differs would move every reply while the fingerprint ledger
    said `unchanged`, which is the state `Observation.DETERMINISM_VIOLATION`
    exists to make visible. Rendering both turns through the same helpers the
    live requests use covers the envelope, the prompt files and the turn order
    together.

    **Three settings ride beside the rendered bytes, because the bytes cannot show
    them.** The summarize block, whose numbers are substituted into the prompt;
    the selected chart types, which narrow the grammar and the type guide; and
    `visuals.enabled_kinds`, which decides whether a plan is asked for at all and
    so whether the reply carries one. The rendering is always the plan-asking
    call, so without the kinds an empty list would leave the stamp saying nothing
    moved on a run that decodes no plan.

    It stops short of two envelope facts all the same, and
    `PipelineInputs.turn_markers_sha256` is where those land: the thinking
    span's closing marker is spliced into a prompt this never renders, and a
    reply opening only reaches these bytes as whichever one the envelope chose.

    The title and the article are rendered as empty strings, which is what leaves
    the result the same on every item.
    """
    ask = prompt_config or SummarizeConfig()
    shown = visuals or VisualsConfig()
    rendered = render_prompt(
        system=summary_system_prompt(
            ask, visuals=shown, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=summary_user_turn("", "", prompt_files=prompt_files, config_dir=config_dir),
        markers=markers,
    )
    kinds = canonical_json([kind.value for kind in shown.enabled_kinds])
    selection = (
        canonical_json([visual_type.value for visual_type in shown.select_types()])
        if shown.type_selection_enabled
        else ""
    )
    return rendered + canonical_json(ask.model_dump(mode="json")) + kinds + selection


def parse_summarize_and_plan(raw: str, *, plan: bool = True) -> SummarizeAndPlanReply:
    """A whole reply, held to the shape the decoder was given, as the two contracts it stands for.

    The decoder shape is an implementation detail of the grammar and stops here.
    What comes out is a `SummaryDraft` and a `VisualPlan`, and building the plan
    is where `version` and `plan_version` are stamped - by code, from what this
    build holds, because a model asked for either would be guessing at a fact we
    already have. `VisualPlan`'s own validators run at that moment, so a plan
    that declines and still names a type fails here, naming the plan.

    A suppressed reply is a summary draft and nothing else, so `visual` comes
    back `None`.
    """
    content = raw.strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    if not plan:
        return SummarizeAndPlanReply(
            summary=summarize.SummaryDraft.model_validate_json(content), visual=None
        )
    data = json.loads(content)
    legacy_references = (
        isinstance(data, dict)
        and isinstance(data.get("visual"), dict)
        and "element_ids" in data["visual"]
    )
    body = summarize_and_plan_model(
        legacy_references=legacy_references
    ).model_validate(data).model_dump(mode="json")
    draft = summarize.SummaryDraft.model_validate(body["summary"])
    if not legacy_references:
        visual = body["visual"]
        groups = [*visual["encodings"].values(), visual["labels"], visual["annotations"]]
        if visual["declared_whole_element_id"] is not None:
            groups.append([visual["declared_whole_element_id"]])
        visual["element_ids"] = list(dict.fromkeys(cited for ids in groups for cited in ids))
    plan_made = VisualPlan.model_validate(
        body["visual"] | {"plan_version": PLAN_VOCABULARY_VERSION}
    )
    return SummarizeAndPlanReply(summary=draft, visual=plan_made)


def _summary_bounds(raw: str) -> tuple[str, int, int] | None:
    """The reply's decoded body and where the closed `summary` object sits in it.

    One walk over the bytes, shared by the two callers that need it: the
    recovery, which wants the object, and the split, which wants the boundary.
    """
    content = raw.strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    key = content.find('"summary"')
    if key < 0:
        return None
    colon = content.find(":", key + len('"summary"'))
    if colon < 0:
        return None
    start = colon + 1
    while start < len(content) and content[start].isspace():
        start += 1
    try:
        body, end = json.JSONDecoder().raw_decode(content, start)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    return json.dumps(body), start, end


def summary_object(raw: str) -> str | None:
    """The closed `summary` object out of a reply that never closed, or nothing.

    `summary` is the first property of the reply shape, so a decode that got far
    enough to be cut got past it: the object is complete, balanced and sitting
    at a known place in the bytes. `json.JSONDecoder().raw_decode` reads exactly
    one value from a position and ignores whatever follows, which is the whole
    of the recovery - no repair, no bracket counting, no second request.

    Nothing is returned when the cut landed inside the summary itself, which is
    the case where there is genuinely nothing to publish.
    """
    found = _summary_bounds(raw)
    return None if found is None else found[0]


class DecodeSplit(NamedTuple):
    """One reply's decode, apportioned between the summary and the picture.

    Four numbers and a flag, because the flag is the honest half: the two halves
    were never timed separately and `is_estimate` is what stops the milliseconds
    being quoted as though they were (Guardrail #10).
    """

    summary_ms: int
    plan_ms: int
    summary_tokens: int
    plan_tokens: int
    is_estimate: bool = True


def split_the_decode(completion: Completion) -> DecodeSplit | None:
    """Apportion the summarize-and-plan call's decode between its two halves.

    **The method is the field order, and the field order is why it works.**
    `summary` is declared before `visual` and field order is decode order, so
    the summary is written and closed before the plan is started - the halves do
    not interleave, and a boundary in the bytes really is a boundary in time.
    What is apportioned is the decode alone: the prefill read the prompt, which
    belongs to neither half.

    The share is the plan half's characters over the whole reply's. Tokens are
    apportioned first and the milliseconds follow the tokens, so the two agree
    by construction rather than by two roundings that happen to match, and each
    pair sums to exactly what the server reported.

    **It is an estimate and it says so.** Timing the boundary exactly needs the
    reply streamed and the `visual` key timestamped, which is a new request path
    and a second timeout policy for a decision this coarse (Carmack,
    2026-09-14). `visual_plan_ms_is_estimate` carries the method onto the row,
    because a number whose method is recorded somewhere else is a number that
    gets quoted without it.

    Nothing comes back where there is no boundary to find: a reply the gate
    narrowed to the summary alone, a cut that landed inside the summary, or a
    decode the server reported as zero tokens.
    """
    found = _summary_bounds(completion.content)
    if found is None or completion.completion_tokens <= 0:
        return None
    _, start, end = found
    whole = len(completion.content.strip())
    summary_chars = max(end - start, 0)
    plan_chars = max(whole - end, 0)
    if summary_chars + plan_chars <= 0:
        return None
    plan_tokens = round(completion.completion_tokens * plan_chars / (summary_chars + plan_chars))
    summary_tokens = completion.completion_tokens - plan_tokens
    plan_ms = round(completion.decode_ms * plan_tokens / completion.completion_tokens)
    return DecodeSplit(
        summary_ms=completion.decode_ms - plan_ms,
        plan_ms=plan_ms,
        summary_tokens=summary_tokens,
        plan_tokens=plan_tokens,
    )


def recovered_completion(completion: Completion) -> Completion | None:
    """The summarize-and-plan reply recast as the single-call reply it contains, or nothing.

    **One path, whatever the decode did.** `summary` is the first property of the
    reply shape, so the summary object is closed, balanced and sitting at the
    same place in the bytes whether the decode ran to the end or stopped in the
    plan behind it. Handing that object to `summarize.to_summary` is what runs
    every publishability check the single call runs - the length verdict, the
    copied-source reject, the address reject and the restatement drop - over one
    implementation rather than two.

    **The repair is what makes a cut reply publishable.** The bytes come back on
    an ordinary HTTP 200 and `to_summary` fails the item on `finish_reason`
    before reading them. They are worth reading: the picture is lost and the
    summary is not, and the summary is the part the digest cannot publish an
    item without. So `finish_reason` becomes `stop` where it was `length` - the
    one field that would otherwise make a later reader think a closed summary
    was cut. A reason this call did not repair is carried through untouched, and
    so are the token counts, because they were really spent.

    Nothing here decides an item is publishable; it only stops one being thrown
    away unread.

    Nothing comes back in the two cases where there is nothing to recast: a cut
    that landed inside the summary itself, which is where there is genuinely
    nothing to publish, and a reply the reachability gate narrowed to the summary
    draft alone (`plan=False`), which is already the single-call shape and whose
    `summary` is a string rather than an object.
    """
    body = summary_object(completion.content)
    if body is None:
        return None
    if not completion.hit_the_budget:
        return replace(completion, content=body)
    return replace(completion, content=body, finish_reason="stop")
