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

**Method.** Eight real corpus articles, 154 to 354 words, taken as the first
eight by `url_key` in that band - a fixed set chosen by a rule rather than by a
reading. Each is sent through call 1 twice, once with the system turn at
`242a701c` and once with the system turn as this row leaves it, with call 1's
real 900-token output budget both times. The arms are run one after the other
rather than interleaved: every number is a count at temperature 0, so box load
cannot move it, and grouped, each arm prefills its own system turn once instead
of on every call. **Eight threads rather than the configured four**, because the
answer is a set of counts and the thread count only moves the clock; both arms
ran at the same setting and the comparison is between them, never against a
runner figure.

**The arm is running as this record is written, and its table lands in the next
commit on this branch.** Said here rather than left blank because a record whose
method is written and whose result is not is a record somebody may read as a
result of nothing.

## What this run does not settle

- **It says nothing about seconds on a runner.** Every figure above is a token
  count or a count of model output. The two rates it is priced at are somebody
  else's measurements, named where they are used.
- **The article set is short.** 154 to 354 words against a truncation cap of
  10,000 tokens. The token arithmetic does not depend on article length at all -
  the trailing turn and the system turn are the same bytes whatever the article
  is - but what call 1 proposes on a 4,000-word article is unmeasured here.
- **Eight articles is a small set**, and a clean result is a bound rather than a
  zero: with no regression seen in eight, the rule of three puts the rate below
  about 31 percent at 95 percent confidence. That is weak, and it is the honest
  reading. What makes it worth having anyway is that the failure it looks for is
  a systematic one - a prompt the model reads on every item - not a rare event.
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
