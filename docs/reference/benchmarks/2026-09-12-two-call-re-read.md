# Where call 2's re-read tokens go, 2026-09-12

**Last Updated**: 2026-09-12

Frozen. This is one run on one day; it is not updated when a later run
disagrees. A later run gets its own record.

The two-call summariser sends call 2 with call 1's whole message array in front
of it, so most of call 2's prompt should be answered from the server's prefix
cache. The one earlier reading printed `FLOOR BROKEN - 4 tokens` and was taken on
the retired 8B. This run replaces it on the configured weights and splits every
token the server prefilled into three causes, so the two rows that exist to
remove two of them can be priced against their own numbers
([`../../../TODO/20260905-11-two-call-planner-plan.md`](../../../TODO/20260905-11-two-call-planner-plan.md)
rows #3c and #3e).

## Conditions

| | |
| --- | --- |
| Instrument | `backend/utilities/measure_two_calls.py`, `--decode-cap 16 --items 2` |
| Weights | `Qwen3.5-9B-Q4_K_M.gguf`, sha256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` - the file `models.summarize` declares, hashed by the harness before the server started |
| Runtime | `llama-server` build **b10444-5f754ea0e**, Clang 20.1.8, Windows x86_64 |
| Chat template | sha256 `7f0e529032c25183bcd66c7f238da2d377f43be754a94e2725a58c4e16d2ed67`, 7,816 characters, read off the server's own `/props` - a template ships with a build as well as with weights |
| Server flags | From `server_argv` and `config/` alone: `--ctx-size 16384 --no-context-shift --batch-size 512 --ubatch-size 512 --threads 4 -np 1 -fa on -lv 4 --metrics`. The log confirms `flash_attn = enabled` |
| Token counts | The server's own `/apply-template` and `/tokenize`, with `enable_thinking: false` - the flag every real request carries |
| Box | A developer laptop, not a runner. Every token count below is a property of the template and the tokenizer; the milliseconds are this machine |
| Runs | **One, and no spread.** Nothing here is a distribution |

## Method

Two arms, because the committed corpus cannot supply the article this reading
was asked for.

**The corpus arm is the corpus's longest article.** `corpus/corpus.jsonl` holds
1,444 rows spanning 2026-08-23 to 2026-09-10, and its longest body is **3,846
words** - exactly `int(5000 / 1.3)`, because `extract.truncation_cap_tokens` was
5,000 until it doubled to 10,000 on 2026-09-09T21:30. So the archive's worst
case is a fossil of a retired setting and reaches **50.0 percent of the current
cap**. Three rows sit at that ceiling, dated 2026-08-23, 2026-08-27 and
2026-09-03.

**The cap arm is BUILT, it is never called a real article, and it is a rendering
measurement rather than a run.** Corpus bodies are joined longest first and cut
by `truncate_to_tokens` itself, so the arm is the cap's worst case by
construction and follows the cap the next time it moves. Real prose, so the
tokenizer sees real vocabulary and real punctuation; the length is the only part
that is ours. `CLAUDE.md` section 13 rules this: where the awkward shape is the
point, the shape is built, because a built one carries the case the archive has
never produced (Guardrail #12). Both its prompts were rendered and tokenised by
the same server, with no decode - `--at-cap` takes it live, and the reason it is
off by default is the clock rather than the question: that prompt is 14,306
tokens, which is about 45 minutes of prefill at the 5.4 tokens a second this
machine read at.

**The split.** For one item, every token the server prefilled is
`(call 1's prompt - what call 1 cached) + (call 2's prompt - what call 2
cached)`. It divides three ways:

| Cause | What it is | Whose |
| --- | --- | --- |
| the article changed | call 1's own re-prefill: a new article has to be read | irreducible |
| the chat template broke the prefix | what call 1 left in the slot, less what call 2 reused | row #3c |
| the trailing turn sits behind the article | what call 2 carries beyond anything the slot held | row #3e |

**The sum is an identity and is not the oracle.** The two call-2 causes always
come to `call 2's prompt - what call 2 cached`, whatever the numbers are, so a
check that they add up cannot fail. What the run checks per item is that call
1's rendered prompt is the length the server charged for, that the cache stopped
exactly where the two rendered prompts diverge, that the trailing turn is not
negative, and that what call 2 replays is as long as what call 1 wrote.

**A decode cap of 16 distorts exactly one cause.** The article cause and the
trailing turn are prefill facts and are cap-invariant. The template cause is the
divergence plus call 1's whole reply behind it, so it shrinks with the cap -
which is why one item runs call 1 on its real 900-token budget.

## The corpus arm

Three items on one slot, adjacent, in one process.

| | call 1 prompt | call 1 cached | call 1 decoded | call 2 prompt | call 2 cached |
| --- | --- | --- | --- | --- | --- |
| item 1, cold slot | 7,419 | 0 | 16 | 8,132 | 7,415 |
| item 2, steady state | 8,211 | **1,362** | 16 | 8,924 | 8,207 |
| item 3, call 1 uncapped | 6,168 | **1,362** | **96** | 6,960 | 6,164 |

Item 3's call 1 stopped because it was finished, not because it ran out of
budget, so **96 tokens is call 1's real reply length** on a 3,430-word article.
The three articles are all near the corpus ceiling and their prompts still differ
by 2,043 tokens, because sentence addressing and the candidate table are not a
function of the word count.

### Where the re-prefilled tokens went

| | words | call 1 prompt | the article changed | the template broke the prefix | the trailing turn | total |
| --- | --- | --- | --- | --- | --- | --- |
| item 1, cold slot | 3,846 | 7,419 | 7,419 | 20 | 697 | 8,136 |
| item 2, steady state | 3,846 | 8,211 | 6,849 | **20** | **697** | 7,566 |
| item 3, call 1 uncapped | 3,430 | 6,168 | 4,806 | **100** | **696** | 5,602 |

Every row sums to what the two calls re-prefilled, and the four per-item checks
held on all three: call 1's rendered prompt was the length the server charged
for, the cache stopped exactly where the two rendered prompts diverge, the
trailing turn was positive, and what call 2 replayed was as long as what call 1
wrote.

## What the reading settles

**The four-token template gap is there on Qwen3.5.** On every item the cache
stopped four tokens short of call 1's prompt, and the harness detokenised what
call 1 carries at the break: `'<think>\n\n</think>\n\n'`, verbatim, all three
times. Row #3c's throughput argument survives the model change.

**The template cause is four tokens plus call 1's whole reply, and that is
measured rather than argued.** At a 16-token decode cap it is 20; at call 1's
real 96-token reply it is 100. **So row #3c is worth 100 tokens an item, which
is 10.2 seconds at 9.85 tokens a second, about 3.4 minutes of a 20-item shard.**
The plan carried 209, which was four plus the retired 8B's 205-token reply.

**Call 2's question is the larger waste by a factor of seven.** The trailing
cause is 697, 697 and 696 tokens - of which **687 is the question's own text**
and the rest is the chat-template header around the turn, which no row moves.
**687 tokens is 69.7 seconds an item, about 23.2 minutes of a 20-item shard.**

**The steady state is one, and nobody had seen it before.** Items 2 and 3 each
reused **1,362 tokens** of their call-1 prompt with no work - call 1's system
turn, which is byte-identical on every item - and the server erased the previous
item's copy of call 2's question as invalidated. Row #3d decision 3's alarm does
not fire.

**What the two-call design costs over a single call is 797 tokens an item**, the
template cause plus the trailing turn at call 1's real reply length. At 9.85
tokens a second that is **80.9 seconds an item, about 27 minutes of a 20-item
shard.** Rows #3c and #3e remove 787 of the 797; what is left is chat-template
header, a pointer and the band numbers row #3e keeps.

## What a cap-length article costs the window

Both prompts rendered and tokenised, no decode:

| Term | Tokens | Where it comes from |
| --- | --- | --- |
| call 1's prompt | 14,306 | rendered and tokenised by this server |
| plus call 1's output budget | 15,206 | `max_output_tokens` is 900 |
| call 2's prompt, 400-token stand-in reply | 15,404 | rendered and tokenised the same way |
| plus the reply call 2's grammar may write | **20,098** | `call_two_output_tokens()` is 4,694 |
| `n_ctx` | 16,384 | `config/idhazh.json` |
| **over by** | **3,714** | 23 percent more than the window holds |

Call 2 has **980 tokens of room for a reply whose grammar can emit 4,694.**
`SUPPRESSED_BUDGET_TOKENS` is 905, so at the cap the only shape that fits is the
one with the picture already suppressed - 16,309 of 16,384, a margin of **75
tokens, 0.46 percent.**

`backend/tests/test_contracts.py::test_the_longest_article_the_cap_allows_still_fits_the_window`
sizes the single-call sequence at 14,088 and passes. Nothing sizes the two-call
sequence. With `--no-context-shift` the overflow is not an error: the decode
stops at the wall, `classify.calls.recovered_completion` salvages the summary,
the item publishes with `decision = none`, and no counter says the window was
the reason. That is plan 11 row #3f.

## The fixed parts, measured

| | Characters | Tokens |
| --- | --- | --- |
| call 1's system prompt (`label_article_elements.txt`) | 4,891 | **1,358** |
| call 2's question (`call_two_user_turn`) | 2,555 | **687** |

687 is the number row #3e exists to remove. The plan carried "about 670", which
was an estimate, and it is withdrawn. At the measured 9.85 tokens a second
([`../../architecture/summarize/throughput.md`](../../architecture/summarize/throughput.md))
687 tokens is **69.7 seconds an item, about 23.2 minutes of a 20-item shard.**
The same turn renders to 698 tokens with its chat-template headers, and the
difference between the two is the floor no prompt edit goes below.

**A share of what.** 687 tokens is 9.3 percent of the corpus arm's 7,419-token
prompt and 4.8 percent of the cap arm's 14,306. Same waste, two numbers a reader
would take for two different problems, so no share appears on this page without
the article length in the same sentence.

## What it does not settle

- **Nothing about a runner.** The milliseconds are a developer laptop with other
  work on it and are an order-of-magnitude check
  ([`../measurements.md`](../measurements.md)). The token counts name the runtime
  and the date and do travel.
- **Nothing about a distribution.** One run, no spread, three articles.
- **Nothing about what the replies said.** Only item 3's call 1 ran to a stop;
  every other decode was cut at 16 tokens.
- **Nothing live at the cap.** The cap arm was rendered, not run, so call 1's
  reply length on a cap-length article is unmeasured - and with a denser
  candidate table it may be longer than 96, which would make the template cause
  larger there than the 100 measured here. `--at-cap` settles it in one run, and
  it costs about 45 minutes of prefill on this box.
- **Nothing about how often a long article arrives.** The cap arm says what one
  would cost, never how many there are.

## See also

- [`../../architecture/summarize/throughput.md`](../../architecture/summarize/throughput.md) - the rate this reading is priced against, and the figure now in force.
- [`../../architecture/summarize/prompt.md`](../../architecture/summarize/prompt.md) - why call 2 appends to call 1's message array.
- [`../../../TODO/20260905-11-two-call-planner-plan.md`](../../../TODO/20260905-11-two-call-planner-plan.md) - rows #3c, #3e and #3f, which this reading prices.
- [`2026-09-11-day-window-read.md`](2026-09-11-day-window-read.md) - the record that created this directory.
