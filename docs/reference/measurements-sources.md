# Source Measurements

**Last Updated**: 2026-09-10

What our sources actually give us, and what the rules around them cost: how many
configured feeds resolve, what the `robots.txt` policy recovered, what the robots
parser costs as a dependency, and why an extracted item fails.

This is the third of three measurement pages and the only one about the world
outside the pipeline. [measurements.md](measurements.md) holds the producer - the
model, the runner, memory and throughput. [measurements-site.md](measurements-site.md)
holds what the reader downloads. A person arrives holding one of the three and
never two.

Both rules from [measurements.md](measurements.md) bind here unchanged: a figure
is either measured, with its date and spread, or it is listed as unmeasured; and
**a second belongs to the box that took it, where a count does not.** Where a
figure was taken off a developer machine and a runner disagreed with it, both are
kept and the runner's is the one that decides - the robots policy is the worked
example, and the developer reading over-counted by two in the direction predicted.

**Measured** on a developer machine (2026-08-21) by running
the real plan stage against the ratified `ai` list - a better check than a
bespoke script, because it exercises the code that will do it daily.

| Quantity | Value |
| --- | --- |
| Feeds configured | 36 |
| Resolved on the first pass | 26 |
| Recovered by finding the real feed URL | 5 |
| **Live after correction** | **31, against a floor of 25** |
| Retired: `robots.txt` forbids or is unreadable | 4 |
| Retired: the publisher declares no feed at all | 1 |

Two of the retirements are permanent by the host's own instruction rather than
defects to fix. One publisher (`ai.meta.com`) is a JavaScript application that
declares no feed on any path, which is a category the plan did not anticipate:
a source can be real, active and unreachable by RSS.

Two figures from the same runs, both single observations and both a laptop
rather than a runner: **one feed read takes roughly 0.5-4 s including its
`robots.txt`**, and a whole 36-feed plan pass finishes in **under a minute**.
That matters only as a shape: the planning step loads no weights, so fanning out
afterwards is what costs, not deciding the day.

**Summarization, Qwen3-4B-Q4_K_M, 4 threads, off the runner, 2026-08-21, n=1:** a
2,557-token article took **89 s** end to end for 179 output tokens. One
observation on a laptop, recorded because it is the first real per-article
number this project has; it is not a runner figure and may not be used as one.

## What the robots policy cost

### On the runner (authoritative)

**Measured 2026-08-23** on `ubuntu-latest`, by running the same day twice: run
1 (`32624081323`) on the old policy, run 2 (`32634191910`) on the new one, same
date, same config, same feed list. Comparing two real plan passes is a better
check than any script, because it exercises exactly what runs daily.

| Quantity | Before | After |
| --- | --- | --- |
| Feeds read | 115 | **132** |
| Feeds refused | 31 | **14** |
| Items published | 8 | 9 |
| Eval rows written | 0 | **9** |

**17 feeds recovered.** The 14 that still refuse are the check on the change:
the policy keeps refusing when a host serves a file that says no, and keeps
refusing when nobody answers at all.

The published count moved by only one because the daily cap, not the feed
count, decides how many items a reader gets. What a wider pool buys is
**choice**: 17 items are now selected from a larger candidate set, so the
ranking has more to rank. Feed count is an input to quality, not to volume.

The eval-row column measures a different fault fixed in the same commit: the
scorer had been disabled on every scheduled run, so the ledger had never once
been written by automation. Nine rows is the first time it has.

### On a developer machine (kept for the IP contrast)

**Measured 2026-08-23**, n=1 per feed, against the 26 feeds
run 1 recorded as `robots_denied`, driving the real fetcher.

| Outcome after the change | Feeds |
| --- | --- |
| **Recovered** | **19** |
| Still refused - a served `robots.txt` disallows the path | 2 |
| Still refused - the article itself answered HTTP 403 | 4 |
| Still refused - the host reset the `robots.txt` connection | 1 |

Ten of the nineteen serve no `robots.txt` at all and answered 404. Reading
"no such file" as a refusal was a rule we invented and the host never wrote,
and it was silently costing the digest most of its `business-economy` and
`world` candidates.

This page predicted the runner would recover fewer than 19 because a developer
IP is not a runner IP, and several of the 403s were a WAF answering a
datacentre address. The runner recovered 17. **The laptop over-counted by two,
in the direction predicted** - which is the reason the runner table sits above
this one and the laptop table is kept only for the contrast.

## What the robots parser costs, 2026-09-02

`protego==0.6.2` replaced `urllib.robotparser` because the standard library
reads one committed file two ways across the interpreter range
`pyproject.toml` declares - Python 3.12 takes the first matching group and the
first matching rule, Python 3.14 merges repeated groups and applies
longest-match. See
[the trust boundary](../architecture/sources/trust-boundary.md). This is what
that dependency costs (Rule #8, Rule #10).

### On the runner (authoritative)

**Measured 2026-09-02** on `ubuntu-latest` (Linux 6.17.0-1022-azure x86_64,
4 vCPU, 16,766,414,848 bytes of RAM), CPython 3.12.14, in a throwaway workflow
on a branch cut from `main` - so the baseline is `pip install -e ".[dev]"` with
no protego in it. Run `33668824024`; the branch was deleted once the log was
read.

| Quantity | Value |
| --- | --- |
| Install seconds | 0.661, 0.449, 0.454 (n=3, mean **0.521**, spread **0.212**) |
| Installed bytes | 422,890,458 -> 422,943,750, so **+53,292** |
| Installed files | 10,317 -> 10,334, so **+17** |
| `pip list --format=freeze` | one line added, `Protego==0.6.2`; none removed, no version moved |

Sample 1 includes the wheel download and samples 2 and 3 read pip's local
cache, which is what the 0.212 s spread on a 0.521 s mean is. Half a second
against the 15 minutes the `gates` job is allowed is not a number any design
turns on; it is here because Rule #8 asks what a dependency costs.

### Against the figure the plan recorded

The plan recorded a **10,296-byte wheel** from the package index and left the
installed size unmeasured. Installed, it is **53,292 bytes - 5.18 times the
wheel**. That ratio is what unpacking a zip and byte-compiling it costs, not a
dependency that turned out bigger than it looked: the Python source alone is
**19,709 bytes over five modules, 1.91 times the wheel**, and the rest is
30,496 bytes of bytecode pip generates and 9,142 bytes of packaging metadata
(counted per file on the developer box, below).

In absolute terms it is **7.3 percent of PyYAML's 728,341 installed bytes** and
**0.15 percent of shellcheck-py's 34,782,285**, both of which are already
dependencies nobody has argued about.

**The installed figure is the baseline, and the wheel figure is not.** Owner
ruling, 2026-09-02, on reading the two numbers above: `protego` is inside the
budget, and every future size comparison for this dependency is made against
**53,292 installed bytes and 0.521 s to install**. A wheel is a zip, so the
unpacked source, the bytecode pip generates and the packaging metadata are three
different things - a comparison anchored on the 10,296-byte wheel understates
what the runner actually holds by 5.18 times, and would let a package grow five
fold before anything read as a change.

**Beneficiary:** one reading of `robots.txt` on every interpreter the project
supports. That is the control Rule #11 rests on, and it may not have an answer
that depends on which runner picked up the job.

### On a developer machine (kept for the contrast)

**Measured 2026-09-02** (CPython 3.14.2) by summing
`site-packages` before and after: 356,807,900 -> 356,867,247 bytes over
11,027 -> 11,044 files, so **+59,347 bytes over 17 files**. That is 6,055 bytes
over the runner's figure, and the cp314 bytecode is where it goes. Installing
it took 5.02 s here (n=1, with the test suite on the same box), so read that as
an upper bound and the runner's 0.521 s as the number.

`protego` ships `py.typed`, so `mypy --strict` needs no `ignore_missing_imports`
entry for it - measured by running the gate with the package installed and no
override: 0 errors over 141 source files.

## Why the other items failed

**Measured 2026-08-23** on a developer machine, by
re-fetching all 9 failures of run 1 and comparing what the extractor returned
against the prose actually present in the markup.

| Items | Source | Extracted | Cause |
| --- | --- | --- | --- |
| 2 | GitHub release tag | 51, 162 words | The page is a list of binary names. The largest prose block in the markup is GitHub's own "You signed in with another tab" furniture |
| 2 | NBER paper page | 128, 178 words | The extractor returned **the abstract, correctly**. The paper is a PDF |
| 1 | Marginal Revolution | 229 words | The post is 277 words. The extractor got 83% of it |
| 2 | Japan Times | 86, 111 words | Metered paywall |
| 2 | IAEA | never fetched | HTTP 403 at the WAF |

Fetches took **0.45-0.80 s**, and no item failed on a timeout or a retry
budget. Two hypotheses are ruled out by this table: the sources are not slow,
and they are not JavaScript shells hiding their text from the extractor.

**The extractor is behaving correctly.** The 250-word floor is rejecting
short-form sources that were extracted properly - a release tag, an abstract,
a short blog post. That makes the low count a **source-selection** result
rather than an extraction defect, and it is why raising the floor's pass rate
belongs in `config/sources.json` and not in `extract.py`.

## Lead coverage newline boundary

**Measured 2026-08-23** on a developer machine (Windows, Python 3.12.12), by
extracting the 17 committed `tests/fixtures/short-sources/` HTML fixtures with
`to_article`, comparing the old capitalised-run expression against the fixed
metric, and scoring five hand-written `publish_brief` summaries through
`score.band` at `hhem = 0.95`. Spread is not available because this is a
deterministic string metric.

| Check | Before | After |
| --- | --- | --- |
| Fixtures with a glued newline entity | 6 of 17 | 0 of 17 |
| Extractable fixtures in the pass | 15 of 17 | 15 of 17 |
| Hand-written `publish_brief` rows moved by the fixed metric | 1 of 5 | 0 remaining wrongly capped |

The glued entities were: `ai2\nglenn matlin`,
`published\nus president donald trump`, `student researcher\nwe`,
`xcframework\nlinux`, `gender-specific parental investment\nwe`, and
`biodiversity loss\nwe`.

| Fixture | Coverage before | Band before | Coverage after | Band after |
| --- | --- | --- | --- | --- |
| `llama-cpp-releases-01` | 0.625000 | high | 0.636364 | high |
| `llama-cpp-releases-02` | 0.857143 | high | 0.857143 | high |
| `marginal-revolution-01` | 1.000000 | high | 1.000000 | high |
| `nber-new-01` | 0.833333 | high | 1.000000 | high |
| `nber-new-02` | 0.000000 | medium | 0.500000 | high |

The committed `state/scores.csv` had 156 rows, but no source-text or summary-text
columns. The stored `coverage` column cannot be recomputed honestly from that
ledger alone, so this pass reports 0 computable re-bands rather than inventing a
movement count.

## See also

- [measurements.md](measurements.md) - the producer: the model, the runner, memory and throughput.
- [measurements-site.md](measurements-site.md) - what the reader downloads.
- [../archive/measurements-2026-08.md](../archive/measurements-2026-08.md) - finished experiments and superseded levels.
- [../architecture/sources/health.md](../architecture/sources/health.md) - the feed ledger and the quarantine rule these figures feed.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - the robots rule the parser enforces.
- [../concepts/config.md](../concepts/config.md) - the source list and its floors.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #8 (a dependency names its cost) and Rule #10 (measured, not estimated).
