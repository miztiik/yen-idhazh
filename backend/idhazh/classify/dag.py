"""The calls one article takes, declared once as data and walked rather than written out.

**Two nodes, and the number is decided here rather than a row at a time.** The
label call returns the element table and every label and score. The
summarize-and-plan call returns the summary and the visual plan. A third node is
not a design this file can express by accident: `NODES` is checked against
`NODE_COUNT` on import, and the check names what has to happen before the number
moves.

**The reason the list is a list at all is the token budget.** The window has to
hold the longest single request the sequence ever makes, and on this path that
is the last one - the summarize-and-plan prompt is the label prompt plus the
label call's whole reply, so every node's decode budget is paid inside the next
node's prompt. A sequence assembled a row at a time is a budget nobody ever
checks whole, and the failure
reads as an ordinary day: `--no-context-shift` means a decode that runs into the
wall stops on an ordinary HTTP 200, `recovered_completion` salvages the summary,
and the item publishes with no picture and `window_exhausted` recorded beside it.
One item reading that way is the seatbelt working; a whole shard reading that way
is a sequence nobody sized. `sequence_tokens` is that sum, in one place, read by
the production gate and by the contract test together.

**Item-major is a correctness rule, not a layout taste.**
the summarize entry pins `n_parallel` to 1, so the server holds one
prefix-cache slot. Every label call first and every summarize-and-plan call afterwards would evict
the prefix before it was reused, on every item, with nothing in any log to say
so. `walk` runs every node of one item before the next item's first node, and
the order is this module's tuple rather than the order somebody wrote two
statements in.

**Nothing here decides what publishes.** A node returns labels and prose; which
items run is deterministic code elsewhere. That is this module's shape and no
longer a rule - `CLAUDE.md` section 1a lifted the ban on a model verdict
reaching a publish decision.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any, Final, NamedTuple

from idhazh.classify import calls
from idhazh.contracts.article import Article
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.extract import TOKENS_PER_WORD
from idhazh.llm.server import window
from idhazh.measured import (
    LABEL_BODY_TOKENS_A_WORD,
    LABEL_MENU_TOKENS_A_ROW,
    LABEL_SCAFFOLD_TOKENS,
    SUMMARIZE_AND_PLAN_SEAM_TOKENS,
)

_SCAFFOLD_TOKENS: Final = int(LABEL_SCAFFOLD_TOKENS.value)
_BODY_TOKENS_A_WORD: Final = LABEL_BODY_TOKENS_A_WORD.value
_MENU_TOKENS_A_ROW: Final = LABEL_MENU_TOKENS_A_ROW.value
_SEAM_TOKENS: Final = int(SUMMARIZE_AND_PLAN_SEAM_TOKENS.value)


class CallName(StrEnum):
    """What each node of the sequence is for.

    The member names the job rather than the position, so a reader of a ledger
    row or a span attribute does not have to know the order to know what ran.
    `contracts.call_cost.CallKind` carries the same two names for the same two
    calls, because the ledger and the walk have to agree about what a call was.
    """

    LABEL = "label"
    SUMMARIZE_AND_PLAN = "summarize_and_plan"


class CallNode(NamedTuple):
    """One call in the sequence, with the decode budget its own grammar derives.

    `output_tokens` is a callable rather than a number because both budgets are
    re-derived on import from the reply shapes' own bounds - move a `maxItems`
    and the budget moves with it, without anybody remembering to. A node that
    carried a literal would be the one term of this sum that went stale quietly.
    """

    name: CallName
    output_tokens: Callable[[SummarizeConfig], int]


def _label_output_tokens(_ask: SummarizeConfig) -> int:
    """The label budget takes no prompt config; the wrapper keeps the node shape one shape."""
    return calls.label_budget_tokens()


def _summary_output_tokens(ask: SummarizeConfig) -> int:
    """The summarize-and-plan call at its widest, which is with the plan asked for.

    The suppressed shape is smaller, so sizing the window on the wider one is
    the conservative read and it does not depend on how often the visual gate
    opens. What the gate saves is a decode, and it is measured where it is spent
    (`docs/architecture/publishing/visuals.md`), not here.

    `ask.asks_for_a_visual_plan` is true in production and is the one case of the
    pipeline test workflow that turns it off, beside an empty
    `visuals.enabled_kinds`. The two move together: sizing for a plan that is
    never asked for reserves room for a decode that never happens, and refuses
    articles that would have fitted.
    """
    return calls.summarize_and_plan_budget_tokens(ask, plan=ask.asks_for_a_visual_plan)


#: The sequence, in order. **This tuple is the contract.** Adding to it is a
#: design change a person signs off, never a quiet edit: a labelling change adds
#: a field to the label call's reply shape, not a node here. A third call would
#: be paid twice over - once as its own decode and again inside every prompt
#: behind it - and `sequence_tokens` is where that shows up.
NODES: Final[tuple[CallNode, ...]] = (
    CallNode(CallName.LABEL, _label_output_tokens),
    CallNode(CallName.SUMMARIZE_AND_PLAN, _summary_output_tokens),
)

#: Written down as well as computed, the same way both output budgets are. A
#: number that only exists as `len(...)` is a number nobody re-derives, and the
#: sequence could then grow without anybody seeing what it cost.
NODE_COUNT: Final = 2

if len(NODES) != NODE_COUNT:
    raise TypeError(
        "the call sequence changed length and nothing priced it - it now has "
        f"{len(NODES)} nodes against a recorded {NODE_COUNT}. Every node's reply is "
        "paid twice, once as its own decode and once inside the next node's prompt, so "
        "re-run `sequence_tokens` against --ctx-size on the summarize entry before "
        "moving this number."
    )

if tuple(node.name for node in NODES) != (CallName.LABEL, CallName.SUMMARIZE_AND_PLAN):
    raise TypeError(
        "the labelling call has to close before the summary opens - everything the "
        "summarize-and-plan call points at is defined by the label call's reply, and "
        "its prompt is the label call's prompt "
        f"plus that reply. Got {tuple(node.name.value for node in NODES)}."
    )


def output_tokens(prompt_config: SummarizeConfig | None = None) -> int:
    """Every node's decode budget, added up.

    Not the window's answer on its own: the budgets are what the sequence
    DECODES, and `sequence_tokens` is what it has to HOLD. They differ by the
    prompt in front of them and by the seams between the turns.
    """
    ask = prompt_config or SummarizeConfig()
    return sum(node.output_tokens(ask) for node in NODES)


def first_prompt_tokens(article_tokens: int, *, menu_rows: int) -> int:
    """What the label call's prompt costs for an article of this size, in tokens.

    Three terms rather than one, and each reads something.

    - the scaffold is fixed, and moves when a prompt file is edited;
    - the per-word rate covers the article and the `[sNN] ` address in front of
      every sentence, and moves when prose tokenizes harder than any build so
      far;
    - the menu is one row per element the extractor cut, so **the one config
      knob that is not the cap or the window still moves this sum.**

    `article_tokens` is spent back to words at `extract.TOKENS_PER_WORD`,
    because that is the unit the cap is enforced in and the rate above is a rate
    per word. Every constant is a reading in `idhazh.measured` carrying its
    hardware, its date and its spread (Guardrail #10).
    """
    words = int(article_tokens / TOKENS_PER_WORD)
    return (
        _SCAFFOLD_TOKENS
        + int(words * _BODY_TOKENS_A_WORD)
        + int(menu_rows * _MENU_TOKENS_A_ROW)
    )


def sequence_tokens(
    article_tokens: int,
    *,
    menu_rows: int,
    prompt_config: SummarizeConfig | None = None,
) -> int:
    """Everything the window has to hold at once, over the whole sequence.

    **The peak is the last node's request, not the sum of two independent
    calls.** The summarize-and-plan call opens with the label prompt and replays the
    label reply,
    so what the window holds at the end is the label call's prompt, plus every decode
    budget behind it, plus one seam per turn boundary. Walking `NODES` is what
    makes that true of the sequence rather than of the two statements somebody
    wrote - add a node and this number grows by that node's budget and a seam,
    here, without anybody editing this line.

    It is a sizing rather than a guarantee, and the reason is stated where each
    term is: both decode budgets are ceilings over reply shapes whose prose
    rails are character rails, and `LABEL_BODY_TOKENS_A_WORD` is the top of
    an eight-build spread rather than a bound. The seatbelt behind it is
    `recovered_completion`; the brake is the budgets themselves.
    """
    ask = prompt_config or SummarizeConfig()
    held = first_prompt_tokens(article_tokens, menu_rows=menu_rows)
    for index, node in enumerate(NODES):
        held += node.output_tokens(ask)
        if index:
            held += _SEAM_TOKENS
    return held


def fits_the_window(
    article: Article,
    server: Mapping[str, Any],
    *,
    menu_rows: int,
    prompt_config: SummarizeConfig | None = None,
) -> bool:
    """Whether this article's whole sequence fits, asked before the label call is sent.

    **`summarize.fits_context` is the other one and it is not this one.** That
    function sizes the single call the qualification harness sends: one system
    turn, one article, one reply. This one sizes the two-call path the digest
    runs. Two paths render different prompts, so one derivation would be wrong
    about one of them, and the wrong one would be wrong in the expensive
    direction - the two-call sequence is 2.8 times the single call's, because
    the label call's reply is paid twice and the candidate menu is paid once.

    **Refusing here costs the item and admitting it costs the picture.** An
    article that does not fit is not clipped or degraded: it lands as
    `FailureCode.CONTEXT_EXCEEDED` with a row in the census. The alternative is
    the silent one - the decode runs into the end of the window, stops on an
    ordinary HTTP 200, and the item publishes looking finished with its visual
    quietly missing.

    `menu_rows` is the real element count for a live item and
    `elements.max_per_article` for the worst case a contract test sizes. Passing
    the cap for a live item would refuse articles that fit.
    """
    return (
        sequence_tokens(
            article.token_count, menu_rows=menu_rows, prompt_config=prompt_config
        )
        <= window(server)
    )


def worst_menu_rows(elements: ElementsConfig | None = None) -> int:
    """The saturated menu, for sizing rather than for a live item.

    `elements.max_per_article` rather than a measured density, because the cap
    is what a saturated menu costs and the census says a cap-length article
    reaches it - the working is beside `LABEL_MENU_TOKENS_A_ROW`.
    """
    return (elements or ElementsConfig()).max_per_article


def walk[Stop](ask: Callable[[CallNode], Stop | None]) -> Stop | None:
    """One item's calls, in the order `NODES` declares and in no other.

    `ask` runs one node and returns nothing when the item may go on, or the
    answer that ends it when it may not. The walk stops at the first node that
    ends the item, because every node after the first reads the reply of the one
    before: the summarize-and-plan call's prompt replays the label call's reply verbatim, and a
    reply that did not parse has not been held to a schema, so sending it would put
    unchecked model text into a prompt on the argument that it is probably fine
    (Guardrail #11).

    **This drives one item, and that is the whole of the item-major rule.** The
    caller loops over items around this call; there is no form of this function
    that runs one node across many items, and that absence is deliberate - the
    server holds one prefix-cache slot, so call-major would evict the prefix
    before it was reused on every item and nothing would say so.
    """
    for node in NODES:
        stop = ask(node)
        if stop is not None:
            return stop
    return None
