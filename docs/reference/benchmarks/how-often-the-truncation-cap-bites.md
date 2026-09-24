# How often the truncation cap bites

**Last Updated**: 2026-09-18
How many published items the extractor's truncation cap actually cut, counted
over one month shard of the item-health ledger.

**Input:** `state/item-health/2026-09.csv`, one month shard, 4,556 rows covering
2026-09-01 to 2026-09-09. The 4,117 of them at the `publish` stage carry the
whole per-item record. One file, named here, because a walk over every shard
costs more every month for an answer one month already gives (Guardrail #12).
**Hardware:** the stock GitHub-hosted `ubuntu-latest` runners those rows were
written on - 4 vCPU, no GPU. Nothing here was taken on a laptop. **Weights:**
`Qwen3.5-9B-Q4_K_M`, sha256 `03b74727...b7e8`, which has been the configured
summarizer since 2026-08-27 and so served every row on this shard. Every token
count below is that vocabulary's and no other.

**The cap cut 36 of 4,117 published items, which is 0.87 percent.** At a cap of
5,000 tokens the cut point is `int(5000 / 1.3)` = 3,846 words, and those 36 rows
sit exactly on it. Nine of them - 0.22 percent - ran past 7,692 words and would
still be cut at a cap of 10,000. The cut articles ran 3,864 to 11,399 words
before the cut, median 5,089.

**So the new headroom is reached about four times a day and is fully spent about
once.** The shard covers 9 days at about 457 published items a day.

| | at cap 5,000 | at cap 10,000 |
| --- | --- | --- |
| Items cut | 36 of 4,117 (0.87 percent) | 9 of 4,117 (0.22 percent) |
| Extra prefill tokens a cut item | - | 23 to 5,000, median 1,616 |
| Extra prefill tokens over the 9 days | - | 78,489 |

**The often-quoted "largest prompt ever seen is 5,516 tokens" is withdrawn.** It
was measured under the 5,000-token cap, so it says what the cap allowed rather
than how long an article runs, and it is stale as well: the largest
`input_tokens` on this shard is **7,093**. Neither figure is evidence about
article length. `source_words_before_cap` is, because it counts the body before
the cut, and that is what the rows above use.

### What a prompt costs, and what the cap raise adds to it

**The prompt is 997 tokens plus 1.306 a word.** Least squares over the same
4,117 rows, `input_tokens` against `source_words`. The constant reads off the
data twice: the shortest items on the shard are 3 words each and measured 980 to
985 tokens. So 997 tokens is the system prompt, the fence and the instructions -
everything before a word of the article arrives.

**997 and the 1.585 below are the two figures on this page that a gate reads, so
they are pinned in code rather than only written here.** They are
`PROMPT_OVERHEAD_TOKENS` and `WORST_TOKENS_A_WORD` in
[../../../backend/idhazh/measured.py](../../../backend/idhazh/measured.py), each
carrying the weights above as its `subject`, and that module refuses either one
the day the active model file names different weights.

**1.306 tokens a word is the median, and the spread is what the window has to
cover.** Over the 36 rows the cap cut, where the word count is fixed at 3,846,
`input_tokens` ran 5,582 to 7,093. Take off the 997-token constant and the
article itself measured **4,585 to 6,096 tokens - 1.192 to 1.585 tokens a
word**. `extract.truncate_to_tokens` spends the cap as
`int(cap / TOKENS_PER_WORD)` words, at a rate taken from the configured weights
and currently 1.3628, so an article that tokenizes harder than that rate
overruns the budget its own cap gave it. **The worst one overruns by 16.3
percent**: the 20,000 cap in force when this was taken cuts at 14,675 words, which at 1.585
tokens a word is 23,259 tokens. The ratio is a property of the prose and not of
the cap, which is why what is recorded is the ratio and what follows it is the
overrun at whatever cap is committed.

**Worst case at the 20,000 cap in force when this was taken, against the 65,536
window beside it:**

| | tokens | share of 65,536 |
| --- | --- | --- |
| Typical article (1.306 a word) | 997 + 19,165 + 900 = **21,062** | 32 percent |
| Worst article this shard produced (1.585 a word) | 997 + 23,259 + 900 = **25,156** | 38 percent |

**The cap and the window are one decision**, and the worked example is the pair
that could not have shipped apart: at the 8,192 window in force on 2026-09-08 a
10,000-token cap sizes at 172 percent of the window.
`test_the_longest_article_the_cap_allows_still_fits_the_window` in
[../../../backend/tests/contracts/](../../../backend/tests/contracts/)
reads both sides from `config/` and fails on any later pair that does not fit.
**It sizes the single call, which is the path being retired** - the two-call
pair sizes at 71,239 of the 81,920 window the cap's rise to 30,000 called for
([../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md)).

### What the wall clock pays

**Prefill runs at a median 9.85 tokens a second** over the 4,117 timed rows, the
slowest row at 8.25 and the fastest at 44.71. That is the same figure the
2026-08-23 sweep took on the configured model at 4,850 tokens
([../models/qwen3.5-9b-q4km.md](../models/qwen3.5-9b-q4km.md)), re-derived from nine
days of real items, which is the strongest corroboration on this page.

**So 5,000 more prefill tokens is 8.5 minutes, and 10.1 at the slowest rate.**
That is the whole cost of the raise, and it lands on the item that was cut.

**Against what a summarize call costs today:** the median, the 95th percentile
and the longest are on the model's own page
([../models/qwen3.5-9b-q4km.md](../models/qwen3.5-9b-q4km.md)), taken over these same
4,117 rows. So the worst item roughly doubles: the longest call on record becomes
about 1,311 s. `run.shard_size` is 5
and `run.shard_timeout_minutes` is 200, so a shard of five worst-case items goes
from about 67 minutes to about 109 - still inside the timeout, and a shard where
all five items are cut is unlikely at a cut rate of 0.87 percent.

**What is not measured:** what the extra text does to summary quality. **Row 4
has now run at the new fingerprint and still cannot answer it**, because the
`date` input would overwrite a published day, so the priced run summarized
different articles from its baseline and no quality comparison may be drawn from
the pair ([what the doubled window and the doubled cap
cost](../pipeline-cost.md#what-the-doubled-window-and-the-doubled-cap-cost-measured-2026-09-09)).
One run of eval rows now exists on the far side of the boundary. What settles
the question is a second run at this same fingerprint over a frozen article set,
against rows written at the same fingerprint - not against anything older, since
the model read different text.

## See also

- [../pipeline-cost.md](../pipeline-cost.md) - the figure this record puts in force, beside every other producer figure.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, which is why every number here carries its conditions.
