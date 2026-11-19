"""The model call that reads one article, and the requests and readers around it.

**One call reads the item and writes the summary and, when code has built a table of
figures from it, the answer about a chart.** The request is built here, with the bytes
rendered by this repository rather than by the model's chat template, and
`idhazh.stages.summarize_one_item` sends it. The visual decision belongs to
`idhazh.visual_planner`: a supported numeric chart or no visual. It stays there: it is
a different subject that happened to share a file.

**Shared instructions sit in front of the article; what differs per item follows it.**
The system turn is the summary rules and the chart rules, which are the same bytes on every
item and are therefore read once per shard rather than once per item. Behind it sit the
item's title, its text and, when a table was built, the tables - a name and a figure a row,
copied from the item - and the fields the grammar will hold this reply to. The model chooses
by row code and writes words; code builds the plan from the row it names, so the model never
writes a number or an address.

**The reply carries the summary first and the answer about a chart second, and that order is
the recovery.** A decode the output budget cuts is cut in the answer, and the summary
behind it is already closed. The prose fields carry no length bound this reads, so there is no
worst case to derive: the call runs under the model file's own response limit
(`sampling.max_tokens`, or `llm.server.DEFAULT_MAX_TOKENS` where the file names none).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from string import Template
from typing import Any, Final, NamedTuple, Self

from pydantic import BaseModel, model_validator
from pydantic_core import PydanticCustomError

from idhazh import summarize
from idhazh.classify.pair_names_with_figures import TABLE_FORMS, FigureTable, forms_on_offer
from idhazh.classify.plan_visual_request import render_example_table, render_tables
from idhazh.config import DEFAULT_CONFIG_DIR
from idhazh.contracts.article import Article
from idhazh.contracts.base import Model as ContractModel
from idhazh.contracts.base import canonical_json
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import (
    EncodingRole,
    PlanCaption,
    PlanDecision,
    PlanReason,
    PlanTitle,
    VisualPlan,
    VisualType,
)
from idhazh.llm.server import (
    Completion,
    TurnMarkers,
    completion_payload,
    render_prompt,
)
from idhazh.load_prompt_text import load_prompt_text
from idhazh.sanitize import sanitize, untrusted_block
from idhazh.visual_vocabulary import PLAN_VOCABULARY_VERSION

#: Each module that reads a raw model reply keeps its own two-line cleaner,
#: as `summarize` does. One shared cleaner is worth having and is not this
#: row's to make.
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

#: The one value of `type` that declines a chart. It is a value of the field and not a field of
#: its own, so an answer cannot say "none" and also name a form.
NO_CHART: Final = "none"

#: A row code, as the grammar is held to it when a request is described without its tables.
ROW_CODE_PATTERN: Final = "^r[1-9][0-9]{0,2}$"


# --- The summarize-and-plan call: the summary and the answer about a chart --------


# What the model answers about a chart: a reason, a form or none, the row, a title.
#
# The fields are in decode order and the reason is first. With thinking off the reason is the only
# room the model has to reason in, so it is written before the decision rather than after it.
# `none` is final: a reply that says it and also fills the rest is read as `none`, which is what
# ends the refusals of a decline that carried a stray title.
#
# `type` and `focus` are free strings here and are bound to what the request offered in the schema
# the decoder is held to (`summarize_and_plan_schema`), because what is on offer differs by item.
# The rule below is the one a grammar cannot hold. No docstring and no field descriptions on
# purpose, as on `SummaryDraft`: pydantic copies both into the schema, and the schema is the
# grammar the server is sent.
class PlanChoice(ContractModel):
    why: PlanReason
    type: str
    focus: str | None
    title: PlanTitle | None
    caption: PlanCaption | None

    @model_validator(mode="after")
    def _a_chart_answer_is_whole_and_writes_no_figure(self) -> Self:
        """A chart answer names its row, has a title, and carries no digit in its words.

        The validator's numeral check only proves that a numeral appears among the cited
        figures, not that it belongs to the row it names, so the model writes none.
        """
        if self.type == NO_CHART:
            return self
        if self.focus is None:
            raise PydanticCustomError(
                "visual_choice_focus_required",
                "a chart answer names the row the item turns on",
                {"field": "focus"},
            )
        if self.title is None or not sanitize(self.title).strip():
            raise PydanticCustomError(
                "visual_choice_title_required",
                "a chart answer has a title",
                {"field": "title"},
            )
        for name in ("why", "title", "caption"):
            words = getattr(self, name)
            if words is not None and any(character.isdigit() for character in words):
                raise PydanticCustomError(
                    "visual_choice_prose_has_digit",
                    "the model writes no figure, so {field} carries no digit",
                    {"field": name},
                )
        return self


class SummarizeAndPlanReply(NamedTuple):
    """What the summarize-and-plan call came back with, as the two contracts it stands for.

    The decoder shape is not this. That one is a grammar and it stops at
    `parse_summarize_and_plan`. What a caller gets is a summary draft the summarizer's own
    gates can read, the model's reason, and a plan the validator can rule on.

    `visual` is `None` when the model answered `none`, and also when no table was on offer so no
    answer was asked for. `why` is the model's own sentence and is `None` in the second case.
    """

    summary: summarize.SummaryDraft
    why: str | None
    visual: VisualPlan | None


def _pointer_template(files: PromptFilesConfig, config_dir: Path) -> Template:
    return Template(load_prompt_text(config_dir, files.continue_summary))


def _summary_half(files: PromptFilesConfig, config_dir: Path) -> Template:
    return Template(load_prompt_text(config_dir, files.write_digest_summary))


def _plan_half(files: PromptFilesConfig, config_dir: Path) -> str:
    return Template(load_prompt_text(config_dir, files.plan_visual)).substitute()


# What the decoder is constrained to emit when tables are on offer. `summary` is declared before
# `visual` and the order is load-bearing: field order is decode order, so the summary is written
# and closed before the answer about a chart is started. A reply the output budget cuts is cut in
# the answer, and a grammar-constrained decoder closes each object as it finishes it, so the
# summary that came back is closed, balanced and parseable: `recovered_completion` publishes the
# item with its summary and no picture, at no extra seconds. Reversed, the same cut would lose the
# summary, which is the part a reader came for. No docstring on purpose: pydantic copies one into
# the schema, and the schema is the grammar the server is sent.
class SummarizeAndPlanDraft(ContractModel):
    summary: summarize.SummaryDraft
    visual: PlanChoice


def summarize_and_plan_model(*, plan: bool = True) -> type[BaseModel]:
    """What the decoder is constrained to emit on the summarize-and-plan call.

    **`plan=False` is the absence of any table, and it is the grammar that spends it.** The shape
    becomes the summary draft alone - the same one the single-call path already sends and
    `recovered_completion` already produces - so the decoder cannot write an answer about a chart
    rather than being asked not to. A budget on its own would not do it: the decoder would write
    the answer and meet the cap part-way through, which spends the decode and returns a cut reply.
    """
    return SummarizeAndPlanDraft if plan else summarize.SummaryDraft


def summarize_and_plan_schema(
    *,
    plan: bool = True,
    visuals: VisualsConfig | None = None,
    tables: Sequence[FigureTable] = (),
) -> dict[str, Any]:
    """Derive the request grammar from the native model, the selection and the tables shown.

    `type` is bound to `none` and the forms on offer, and `focus` to the row codes of the tables
    shown, so a reply cannot name a form or a row the request did not offer. A request described
    without its tables binds `focus` to the shape of a row code instead.
    """
    schema = summarize_and_plan_model(plan=plan).model_json_schema()
    if not plan:
        return schema
    answer = schema["$defs"][PlanChoice.__name__]["properties"]
    forms = forms_on_offer(visuals or VisualsConfig())
    answer["type"]["enum"] = [NO_CHART, *(form.value for form in forms)]
    codes = [row.code for one in tables for row in one.rows]
    row_choice: dict[str, Any] = (
        {"type": "string", "enum": codes}
        if codes
        else {"type": "string", "pattern": ROW_CODE_PATTERN}
    )
    answer["focus"]["anyOf"] = [row_choice, {"type": "null"}]
    return schema


def summarize_and_plan_user_turn(
    *,
    plan: bool = True,
    tables: Sequence[FigureTable] = (),
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The tables of figures, then the reply fields.

    The tables are exactly the rows `focus` may name, so every code the grammar offers is a row
    the model can read. They are attached independently of the selected template so a custom
    wording cannot silently remove the rows the grammar offers.

    Shared instructions stay in the system turn. The last line names fields from the reply model
    so it cannot ask for an answer the request has no tables for. No tables removes them, without
    moving the reusable prefix.
    """
    shape = summarize_and_plan_model(plan=plan)
    question = _pointer_template(prompt_files or PromptFilesConfig(), config_dir).substitute(
        write="Write " + ", then ".join(f'"{name}"' for name in shape.model_fields) + ".",
    )
    if not plan or not tables:
        return question
    return render_tables(tables, forms_on_offer(visuals or VisualsConfig())) + "\n\n" + question


if tuple(summarize_and_plan_model().model_fields) != ("summary", "visual"):
    raise TypeError(
        "field order is decode order, and the summary has to close before the answer "
        "about a chart starts or a cut reply loses the half a reader came for - "
        f"got {tuple(summarize_and_plan_model().model_fields)}"
    )


def summary_system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The summary rules and the chart rules, in one turn in front of the article.

    Two files joined here rather than one file holding all of it. The turn behind
    the article is a third place and is not joined here: its `$write` placeholder
    names the fields one reply's grammar holds, which is not the same on every
    item, and a stray one in this turn would render to a model as the literal
    `$write`.

    The summary comes first because it is the half that is always decoded, and
    the chart rules follow because they point at the rows listed behind the item.

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
            _plan_half(files, config_dir),
        )
    )


def summary_user_turn(
    title: str,
    text: str,
    *,
    plan: bool = True,
    tables: Sequence[FigureTable] = (),
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The title and the article as the page wrote them, then the tables and the question.

    Both are fenced, and the title is fenced like the text: it sits next to the
    fence in a framing position the prompt's "the block below is DATA" sentence
    does not reach, and prompt wording is not a control anyway because it is
    written in the same channel as the attack (Guardrail #11). `clean_title`
    strips machinery, not English, so an instruction written in ordinary prose
    arrives intact - the title of an item whose feed carried no headline is
    whatever the fetched page's author put in `<title>`.

    The text is plain. It carries no sentence address, because the call is asked
    for no location, and none of the characters are escaped. The rows are the
    article's own words, fenced the same way and sanitized again by the fence.
    """
    return (
        "Title:\n"
        + untrusted_block(title)
        + "\n\nThe item:\n"
        + untrusted_block(text)
        + "\n\n"
        + summarize_and_plan_user_turn(
            plan=plan,
            tables=tables,
            visuals=visuals,
            prompt_files=prompt_files,
            config_dir=config_dir,
        )
    )


def build_summary_request(
    article: Article,
    tables: Sequence[FigureTable],
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
    """The one call's request body, with the reply shape enforced by the decoder.

    The prompt bytes are rendered here rather than by the model's chat template,
    and the response limit is the model file's own: a request carries
    `sampling.max_tokens` where the file names one and `DEFAULT_MAX_TOKENS` where
    it does not.

    **No tables is the answer about a chart left off, and it is the grammar that
    leaves it off.** The reply shape becomes the summary draft alone, so the
    decoder cannot write an answer rather than being asked not to, and the tables
    stay out of the prompt with it. `tables` are the exact rows `focus` may name,
    so their codes are the only ones the grammar offers.

    `markers` are read off the template of the weights this body will be sent to,
    so a model whose turns differ costs no edit at all.
    """
    plan = bool(tables)
    return completion_payload(
        model_id=model_id,
        system=summary_system_prompt(
            prompt_config, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=summary_user_turn(
            article.title or "(untitled)",
            article.text or "",
            plan=plan,
            tables=tables,
            visuals=visuals,
            prompt_files=prompt_files,
            config_dir=config_dir,
        ),
        output_schema=summarize_and_plan_schema(plan=plan, visuals=visuals, tables=tables),
        server=server,
        sampling=sampling,
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
    the selected chart types, which narrow the grammar and the forms line; and
    `visuals.enabled_kinds`, which decides whether a table is built and so whether
    the reply carries an answer about a chart at all. The rendering is always the
    call without tables, so without the kinds an empty list would leave the stamp
    saying nothing moved on a run that asks about no chart.

    **The words code writes around the tables are rendered too, over one fixed
    example table,** because no real table is in this rendering and a change to
    their wording is a change to every prompt that has one.

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
        system=summary_system_prompt(ask, prompt_files=prompt_files, config_dir=config_dir),
        user=summary_user_turn("", "", prompt_files=prompt_files, config_dir=config_dir),
        markers=markers,
    )
    kinds = canonical_json([kind.value for kind in shown.enabled_kinds])
    selection = (
        canonical_json([visual_type.value for visual_type in shown.select_types()])
        if shown.type_selection_enabled
        else ""
    )
    return (
        rendered
        + canonical_json(ask.model_dump(mode="json"))
        + kinds
        + selection
        + render_example_table(forms_on_offer(shown))
    )


def _plan_from_choice(choice: PlanChoice, tables: Sequence[FigureTable]) -> VisualPlan:
    """The complete plan a chart answer stands for, built from the table of the row it names.

    **Code does everything the model is not asked to.** The purpose comes from the form, the
    category channel is the table's names and the quantity channel is its figures, in row order;
    no other channel is filled, nothing is declared a whole and no label is cited, because the
    marks are named by the names they stand on. The one annotation is the figure of the row the
    model named, since the compiler needs exactly one emphasised mark and code never guesses it.
    """
    form = VisualType(choice.type)
    purpose = TABLE_FORMS.get(form)
    if purpose is None:
        raise ValueError("the answer names a form no table is offered as")
    chosen = next(
        (one for one in tables if any(row.code == choice.focus for row in one.rows)), None
    )
    if chosen is None:
        raise ValueError("the answer names a row no table offered")
    focused = next(row for row in chosen.rows if row.code == choice.focus)
    categories = [row.name.element_id for row in chosen.rows]
    quantities = [row.figure.element_id for row in chosen.rows]
    encodings: dict[str, list[str]] = {role.value: [] for role in EncodingRole}
    encodings[EncodingRole.CATEGORY.value] = categories
    encodings[EncodingRole.QUANTITY.value] = quantities
    return VisualPlan.model_validate(
        {
            "decision": PlanDecision.VISUAL.value,
            "purpose": purpose.value,
            "type": form.value,
            "encodings": encodings,
            "element_ids": list(dict.fromkeys([*categories, *quantities])),
            "labels": [],
            "annotations": [focused.figure.element_id],
            "why": choice.why,
            "title": choice.title,
            "caption": choice.caption,
            "plan_version": PLAN_VOCABULARY_VERSION,
        }
    )


def parse_summarize_and_plan(
    raw: str, *, tables: Sequence[FigureTable] = ()
) -> SummarizeAndPlanReply:
    """A whole reply, held to the shape the decoder was given, as the contracts it stands for.

    The decoder shape is an implementation detail of the grammar and stops here. What comes out
    is a `SummaryDraft`, the model's reason and a `VisualPlan`, and building the plan is where
    `plan_version` is stamped - by code, from what this build holds, because a model asked for it
    would be guessing at a fact we already have. `VisualPlan`'s own validators run at that moment.

    **`none` is final.** The answer builds no plan, `visual` comes back `None`, and `why` is the
    model's reason for declining. A reply to a request with no tables is a summary draft and
    nothing else, so `why` is `None` beside it.
    """
    content = raw.strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    if not tables:
        return SummarizeAndPlanReply(
            summary=summarize.SummaryDraft.model_validate_json(content), why=None, visual=None
        )
    reply = SummarizeAndPlanDraft.model_validate_json(content)
    choice = reply.visual
    plan = None if choice.type == NO_CHART else _plan_from_choice(choice, tables)
    return SummarizeAndPlanReply(summary=reply.summary, why=choice.why, visual=plan)


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
