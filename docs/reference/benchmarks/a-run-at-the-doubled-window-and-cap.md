# A production run at the doubled window and the doubled cap

**Last Updated**: 2026-09-18
What one dispatched run cost with `n_ctx` at 16,384 and
`extract.truncation_cap_tokens` at 10,000, against a scheduled run of the same
day at the settings then in force.

**The run:** `2026-09-09-34379502244`, `workflow_dispatch`, 4 shards,
faithfulness on, commit `0d49b61f`, 16:53:05Z to 18:35:48Z. Wall clock
**1h42m43s**. `n_ctx` 16,384, `flash_attention: "on"`, `log_verbosity` 4,
`extract.truncation_cap_tokens` 10,000. Model `Qwen3.5-9B-Q4_K_M`, 8.95 B
parameters, llama.cpp build 10598 (`56db501e7`). 846 memory samples.

**The baseline:** `2026-09-09-34323771996`, scheduled, same day, 07:25:34Z to
09:10:39Z, wall clock **1h45m05s**, 4 shards, `n_ctx` 8,192, cap 5,000,
`log_verbosity` 3, 601 samples.

**Hardware:** stock GitHub-hosted `ubuntu-latest`, 4 vCPU, no GPU, `MemTotal`
15.61 GiB. **The two runs drew different processors**, and that turns out to
matter more than anything in `config/`: the priced run got AMD EPYC 9V74 on
shards 0 and 2 and AMD EPYC 7763 on 1 and 3; the baseline got Intel Xeon
Platinum 8573C on 0 and 3 and EPYC 9V74 on 1 and 2.

**Two deviations, stated rather than buried.** The article sets differ - the
`date` input would overwrite a published day, so it was not used - therefore
**no summary-quality comparison may be drawn from this pair**. And this run
carries three changes at once, the window, the pinned attention flag and the
article cap. Memory, KV size, attention and prefill rate are runtime properties
and are unaffected by either deviation.

**The fingerprint moved, which is what says the config reached the run.**
`22f44b21c1bdf4cd104c4a41e5f27c7bb62dc67020f61c7ee2ac7e4533641c24`, first seen
at 16:59:26Z, replacing `30d96862...`. `n_ctx` 8,192 to 16,384,
`truncation_cap_tokens` 5,000 to 10,000, `flash_attention` `runtime-default` to
`on`. Every other digested field is unchanged, so the stamp moved for exactly
the three settings this run was dispatched to price.

### MemAvailable went up by 1.21 GiB, and the runner is why

| | priced, `n_ctx` 16,384 | baseline, `n_ctx` 8,192 |
| --- | --- | --- |
| `MemAvailable` low-water mark | **6.84 GiB** | **5.63 GiB** |
| per-shard lows | 6.84, 7.36, 7.44, 7.46 | 5.63, 5.95, 7.64, 7.84 |
| tightest instant | shard 3, 18:01:44Z | shard 0, 08:01:32Z |
| samples | 846 | 601 |

**ESCALATE trigger 1 asks for 1.0 GiB and the run left 6.84. It is 6.8 times the
bar and does not fire.**

**More free memory at twice the window is not a saving, it is a different
runner.** The baseline's two tight shards were the Intel Xeon 8573C ones, whose
`Committed_AS` peaked at 12.68 and 12.31 GiB against 10.37 to 10.66 GiB for the
same job on EPYC. The priced run drew no Intel shard at all. So 5.63 GiB is a
property of the processor a shard landed on, not of the window.

**Matched on the same processor, the cost appears and it is the projected
size.** On EPYC 9V74, `Committed_AS` peak went from 10.52 GiB (2 shards,
baseline) to **10.84 GiB** (2 shards, priced): **+0.32 GiB**, against +0.25 GiB
projected for the KV cache, with the remainder from the longer prompts the cap
raise admits. That is the like-for-like reading and it is the one to quote.

**What was not measured: the doubled window on an Intel Xeon 8573C shard.** The
KV buffer is a fixed 512 MiB whatever the processor, so the arithmetic carries -
5.63 - 0.25 leaves 5.38 GiB, 5.4 times the bar - but no run has yet observed it.

### The cap cut nothing, and the rate it was priced at did not move

**Zero of 75 items ran past the 10,000-token cut point** of 7,692 words. The
baseline cut 2 of 75 at its 3,846-word point. The prediction was about one cut
item a day across roughly six runs a day, which is about 0.17 for a single
70-item run - **zero is what that predicts, not evidence against it.** The
8.5-minute cost of a cut item is therefore still untested by a cut item.

**Its ingredient is re-confirmed, and doubling the window cost nothing per
token.** Matched on EPYC 9V74, uncached prefill ran at a median **9.86 tokens a
second** at 16,384 against **9.97** at 8,192 - down 1.1 percent, which is inside
the run-to-run spread. Whole-month median 9.85 over 4,187 timed rows, min 8.25,
max 44.71.

**The processor sorts the prefill rate four times harder than any setting
does.** On the baseline, the Intel Xeon 8573C shards ran at a median **41.00
tokens a second** against 9.86 on EPYC 9V74 - **4.2 times faster on the same
work**. Which runner class a shard draws is the largest single term in its wall
clock, and nothing in `config/` touches it. Every per-shard timing on this page
carries that lottery inside it.

| prefill, uncached tokens a second | n | min | median | max |
| --- | --- | --- | --- | --- |
| priced, EPYC 9V74 | 35 | 9.79 | **9.86** | 9.98 |
| priced, EPYC 7763 | 35 | 9.43 | 9.76 | 9.84 |
| baseline, EPYC 9V74 | 38 | 9.70 | **9.97** | 14.60 |
| baseline, Intel Xeon 8573C | 35 | 33.34 | **41.00** | 43.94 |

### The window raise was load-bearing on the first run, and nothing predicted that

**One item reached 8,741 input tokens** - 5,937 words, `ai` vertical, not cut
because 5,937 is under the 7,692-word point. It is the largest prompt in the
whole 4,187-row month shard and the only one over 8,192. **Under the previous
8,192 window it would not have fitted.** Under the previous 5,000-token cap it
would have been cut to 3,846 words and never grown that large. So the window
raise and the cap raise are load-bearing **as a pair**, and the pair was
exercised on the day it landed rather than at some later margin. That item cost
927 s of prefill and 1,003 s in total.

Largest KV occupancy on the run, `n_tokens_max`, was **9,082 of 16,384 cells -
55 percent**. So the busiest single request used just over half the new window.

## See also

- [../measurements.md](../measurements.md) - the figure this record puts in force, beside every other producer figure.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, which is why every number here carries its conditions.
