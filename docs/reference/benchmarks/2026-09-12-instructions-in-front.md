# Moving the instructions in front of the article, 2026-09-12

**Last Updated**: 2026-09-12

Frozen. This is one run on one day; it is not updated when a later run
disagrees. A later run gets its own record.

Call 2's question used to sit in a user turn behind the article. It is
byte-identical on every item, but the text in front of it is not, so a prefix
cache cannot reach it and every token of it was read again on every item, for
ever - **687 tokens, measured the same day** in
[`2026-09-12-two-call-re-read.md`](2026-09-12-two-call-re-read.md). This run is
the before and after of moving both jobs into the system turn, in front of the
article, and leaving three lines behind
([`../../../TODO/20260905-11-two-call-planner-plan.md`](../../../TODO/20260905-11-two-call-planner-plan.md)
row #3e).

It answers two questions, and the second is the one that made the row risky.
**What did the move cost and save, in tokens?** And **did it change what call 1
says about the article?**

## Conditions

| | |
| --- | --- |
| Weights | `Qwen3.5-9B-Q4_K_M.gguf`, sha256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` - the file `models.summarize` declares |
| Runtime | `llama-server` from `backend/bin/`, started by `server_argv` from `config/` |
| Token counts | The running server's own `/tokenize`. **Both arms were tokenised in one server session**, so the before and the after are read by one instrument |
| The before arm | Reconstructed from the prompt files at `242a701c`, the commit this row was cut from, rather than quoted from an earlier run |
| Box | A developer laptop with three other agents working on it, not a runner. **Every token count here is a property of the prompts and the tokenizer and holds anywhere. No seconds are measured here at all** - the seconds below are token counts priced at the read rate in [`../../architecture/summarize/throughput.md`](../../architecture/summarize/throughput.md), 9.85 tokens a second, median, measured 2026-09-09 on GitHub-hosted `ubuntu-latest` |
| Runs | **One, and no spread.** Nothing here is a distribution |

## What moved, and what it cost

Per prompt file, because the row's oracle requires the difference to be printed
rather than absorbed: a row that "saves" 650 tokens by dropping an instruction
instead of moving it passes any threshold and fails this at once.

| Prompt text, tokens | before | after | delta |
| --- | ---: | ---: | ---: |
| `label_article_elements.txt` | 1,358 | 1,383 | +25 |
| `summarize_and_plan_visual.txt` | 273 | 244 | -29 |
| `plan_visual.txt` | 415 | 429 | +14 |
| `write_about_the_item.txt`, new | 0 | 37 | +37 |
| **total instruction text** | **2,046** | **2,093** | **+47** |

**The instructions are the same set and 47 tokens longer.** Every one of the 47
is nameable: a two-job opening on the elements half and the scoping of its
number ban (+25); two conditioning clauses on the plan half and one positional
word repointed (+14); the pointer itself (+37); against which the summary half
gave up the four band numbers and its positional preamble (-29), and about 20
tokens of duplicated injection rule were dropped because
`label_article_elements.txt` states the same rule in fuller form and now states
it in the same turn.

## Where those tokens sit, which is the whole point

| Rendered turns, tokens | before | after | delta |
| --- | ---: | ---: | ---: |
| in front of the article, read once a shard | 1,363 | 2,060 | +697 |
| behind it, read on every item for ever | 692 | 42 | **-650** |
| both | 2,055 | 2,102 | +47 |

**650 tokens come off every item.** At 9.85 tokens a second that is **66.0
seconds an item and 22.0 minutes of a 20-item shard**. The 697 the system turn
took on is paid once a shard, because that turn is byte-identical on every item
and the server's prefix cache answers for it from item 2 onward - measured on
this model in [`2026-09-12-two-call-re-read.md`](2026-09-12-two-call-re-read.md),
where items 2 and 3 each reused 1,362 tokens with no work. So a 20-item shard is
**20.8 minutes better off, net**.

**The floor, and what is left above it.** The row may not go below the rendered
turn carrying the four band numbers the article's own length picked, and nothing
else: **F is 14 tokens**. The residual `after - F` is **28 tokens**, which is the
pointer's words. Before the move the same residual was **678**. Stated the way
the row asks for it: `692 -> 42, floor 14, pointer 28`.

## It buys the article no room, and takes 47 tokens away from it

This corrects a claim that stood in two rows of plan 11 until this run.

| Call-1 prompt budget, tokens | before | after |
| --- | ---: | ---: |
| ceiling: `n_ctx` less both decode budgets less the trailing turn | 10,098 | 10,748 |
| of which the system turn takes | 1,363 | 2,060 |
| **left for the article, its addresses and its table** | **8,735** | **8,688** |

**The ceiling widened by 650 and that is not the question.** It bounds call 1's
whole prompt, and the 697 tokens that moved now sit inside it. The longest
article the window admits is therefore **47 tokens shorter**, not 597 longer, and
row #3f's 3,714-token overflow at the truncation cap is 47 tokens worse rather
than 14 percent closed.

## Did it change what call 1 says?

This is the arm that made the row risky, and it is the reason the row was not
just a diff. Call 1's entire output is addresses into the article, so it is the
call least able to absorb instructions it cannot act on - and it now carries the
summariser's and the planner's.

**Every number below is a deterministic count over the model's own output.** No
model grades anything (`CLAUDE.md` section 0a). Anchoring is span equality
against the article's own bytes; the own-words rate is a set membership test.

**Method.** Six real corpus articles were selected, 154 to 354 words, taken as
the first six by `url_key` in that band - a fixed set chosen by a rule rather
than by a reading - and **three of them ran** before the box was needed back.
Each is sent through call 1 twice, once with the system turn at `242a701c` and
once with the system turn as this row leaves it, with call 1's real 900-token
output budget both times.

**Three pairs ran and two are clean**, because the third exposed a defect in the
BEFORE arm that has nothing to do with this row - see the section below. The
clean result is over the two articles both arms answered in full.

| Over 2 articles both arms answered | before | after |
| --- | ---: | ---: |
| labels | 1 | 1 |
| labels naming an id the pass minted | 1 | 1 |
| figures proposed | 1 | 1 |
| named-thing groups | 8 | 7 |
| place groups | 5 | 2 |
| quotes | 2 | 2 |
| claims | 0 | 0 |
| keyphrases | 15 | 13 |
| lede sentences | 2 | 2 |

| Rate | before | after |
| --- | --- | --- |
| anchoring, pointed elements | 23/31, **74.2 percent** | 18/21, **85.7 percent** |
| anchoring, proposed figures | 1/1 | 1/1 |
| **own words** | 14/16, **87.5 percent** | 13/14, **92.9 percent** |

**No dilution is visible, and what moved moved the right way.** The after arm
proposes a little less - 7 named-thing groups against 8, 13 keyphrases against
15, and 2 place groups against 5 - and a **higher share of what it does propose
resolves to characters in the article**: 85.7 percent against 74.2. The
own-words rate, the arm that watches the four free-text channels nothing
downstream re-resolves, went up rather than down. Every count that feeds the
picture is identical: the same labels, all on ids the pass minted, the same
proposed figure, the same quotes, claims and lede sentences.

**Two articles is a small set and the honest reading is a bound, not a zero.**
With no regression seen in two, the rule of three puts the rate below about 78
percent at 95 percent confidence, which is almost no constraint. What makes the
run worth having anyway is the shape of the failure it looks for: a prompt the
model reads on every item would show up as a systematic shift, not a rare event,
and the shift that did appear is in the safe direction on both rates.

**The arms were run one article at a time through both layouts**, so a run cut
short by box load leaves whole pairs rather than one whole arm; and eight
threads were used rather than the configured four, because every number here is
a count and the thread count only moves the clock. Both arms ran at the same
setting. The whole run took 36 minutes for three articles, at 2.3 to 3.5 tokens
a second of decode with three other agents working on the box.

## A defect this run found, and it is not this row's

**Call 1's reply can exceed its own output budget on an ordinary article, and
when it does the item is lost with no recovery.** On the third article - 346
words, the BEFORE layout, so the base commit and not this change - call 1 decoded
**900 tokens, hit `models.summarize.inference.max_output_tokens` exactly, and
stopped with `finish_reason = length`**. The reply was cut mid-string and
`classify.calls.parse_call_one` raised `Invalid JSON: EOF while parsing a string
at line 1 column 2805`.

Nothing rescues it. Call 2 has `recovered_completion`, which spends the
summary-before-plan field order to salvage a cut reply; **call 1 has no
equivalent**, because its reply is one flat object with no half a caller could
use. And the budget is not derived from call 1's own grammar the way call 2's is
from `call_two_output_tokens` - it is the role's `max_output_tokens`, which was
sized for a summary.

The arithmetic says it is not a freak: `CallOneReply` admits 16 labels, 4
proposals, 6 entity groups and 6 place groups of 4 mentions each, 8 quotes, 8
claims, 8 keyphrases and 2 lede addresses. A dense article filling even half of
that passes 900 tokens. **This is the same family as plan 11 row #3f** - a bound
that is not derived from the shape it bounds - and it belongs to a row of its
own rather than to this one.


## What this run does not settle

- **It says nothing about seconds on a runner.** Every figure above is a token
  count or a count of model output. The two rates it is priced at are somebody
  else's measurements, named where they are used.
- **The article set is short.** 154 to 354 words against a truncation cap of
  10,000 tokens. The token arithmetic does not depend on article length at all -
  the trailing turn and the system turn are the same bytes whatever the article
  is - but what call 1 proposes on a 4,000-word article is unmeasured here.
- **Two clean articles is a very small set**, and a clean result is a bound
  rather than a zero: the rule of three puts the regression rate below about 78
  percent at 95 percent confidence, which is almost no constraint. The run was
  stopped at three pairs because the box carries three other agents and a pair
  cost 12 minutes. **Re-run it wider when the box is quiet**; the harness is one
  scratch script and the article set is chosen by a rule, so it reproduces.
- **Nothing dispatches these calls yet**, so no published summary has been
  written under either layout. The first real reading is the first daily run
  after plan 11 row #5b lands.

## See also

- [`2026-09-12-two-call-re-read.md`](2026-09-12-two-call-re-read.md) - the run
  that found the 687 tokens this one removes.
- [`../../architecture/summarize/prompt.md`](../../architecture/summarize/prompt.md) -
  the living doc that owns the prompt layout.
- [`../../architecture/summarize/throughput.md`](../../architecture/summarize/throughput.md) -
  the 9.85 tokens a second every second here is priced at.
