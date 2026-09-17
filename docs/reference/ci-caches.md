# CI Caches and Artifact Storage

**Last Updated**: 2026-09-17
Every cache this repository keeps, what it holds, who reads it, and the bar a
new one has to clear - plus the artifact total. Read this before adding either:
the cache allowance is shared, and the entry a careless addition evicts is the
one the daily pipeline needs.

**Neither number on this page can fail a run.** The 10 GB cache allowance is
GitHub's to enforce, and it enforces it by eviction rather than by refusal. The
500 MB artifact figure is a private-repository quota, and this repository is
public. `CLAUDE.md` Guardrail #2 says what crossing each one does. The behaviour
behind the cache - an entry unread for 7 days is deleted, and a restore is paid
once per job rather than once per run - is in
[ci-environment.md](ci-environment.md#platform-limits-that-shape-the-workflows).
This page is the inventory and the rule.

## The budget, measured

Read with `gh api repos/miztiik/yen-idhazh/actions/cache/usage` and
`.../actions/caches` on **2026-09-17**. `n = 1` - a cache listing is a state, not
a sample, so there is no spread. Bytes are the reading; a GB below is
1,073,741,824 bytes and a MB is 1,048,576.

| | Bytes | GB | Of the 10 GB allowance |
| --- | ---: | ---: | ---: |
| All 7 entries | 17,175,463,744 | 16.0 | **160%** |
| The three model weight entries alone | 16,317,054,735 | 15.20 | 152% |
| Everything else (pip, npm, browser) | 858,409,009 | 0.80 | 8% |

**The cache holds 6.0 GB more than the allowance, and GitHub settles that by
evicting rather than by refusing a save.** Two of the three model entries are the
transient `bench-` entries the four dispatches of 2026-09-16 left behind, 6.19 GB
and 3.78 GB. Nothing restores either after its own dispatch, so both give their
bytes back once they are the least recently used. The third, 5.23 GB, is the
summariser `digest.yml` restores on every run.

## Artifacts, measured

Read with `gh api repos/miztiik/yen-idhazh/actions/artifacts --paginate` on
**2026-09-17**, counting only artifacts that have not expired. Same rule: a
listing is a state, not a sample, so `n = 1` and there is no spread.

| | Bytes | MB | Count | Of the 500 MB private-repository quota |
| --- | ---: | ---: | ---: | ---: |
| Every live artifact | 1,113,878,190 | 1,062.3 | 612 | **212%** |
| `github-pages` deployment artifacts alone | 1,050,902,892 | 1,002.2 | 30 | 200% |
| Everything the pipeline and the gates upload | 62,975,298 | 60.1 | 582 | 12% |

**That quota does not apply here, and 94 percent of the live total is one
artifact name.** GitHub Actions usage is free for public repositories on
standard runners, so the 500 MB figure meters nothing against this repository.
Each `github-pages` deployment artifact measures 33.2 to 33.5 MB, and 30 of them
are live. No pipeline step chooses to write these; the Pages deployment does.

**Everything this repository's own workflows upload is 60.1 MB, which is 12
percent of that quota.** The bench is a rounding error inside that: 24 dispatches
hold 2,202,221 bytes between them, and the four dispatches of 2026-09-16 averaged
158,962 bytes each - **0.15 MB a dispatch, which is 0.014 percent of the live
total.**

## What being over the allowance actually costs

**Nothing on this page fails a run, and neither number needs an owner decision.**

**The cache is over its allowance, and GitHub settles that itself.** It saves the
new entry, then evicts by oldest last-access until the total is under, and it
deletes anything untouched for 7 days regardless. The only cost is a miss on the
next restore. The summariser entry and the two transient `bench-` entries sit in
one queue ordered by last access, and on 2026-09-17 the `bench-` entries were the
two oldest - last read 2026-09-16T12:11Z and 2026-09-16T11:10Z, against the
summariser's 2026-09-16T21:28Z - so eviction reaches both of them first.

**One consequence is worth naming.** If the digest does not run for 7 days, or if
enough newer entries are created while its entry sits idle, the 5.23 GB
summariser entry goes and the next digest run re-fetches the 5.29 GB weights file
from Hugging Face and rebuilds the runtime, on the publishing path. So a bench
dispatch cannot slow CI down by overflowing the cache, and it can slow the digest
down in that one way.

**Artifacts have no eviction mechanism to name either.** They expire on their
retention window rather than on pressure, so nothing here is at risk of being
deleted early. The reason to keep the total small is that a person reading a run
should find the artifact they want.

## The inventory

| Cache | Key | Filled by | Read by | Size |
| --- | --- | --- | --- | --- |
| Summariser weights and runtime | `llm-<file>-<revision>-<llama.cpp build>-v4` | `digest.yml` `work` | every `work` shard of every run | 5.23 GB |
| Candidate weights and runtime | `qualify-<candidate sha256>-<llama.cpp build>` | `validate.yml` `qualify` | the other shards of the same run | transient, none live |
| Bench weights and runtime | `bench-<candidate sha256>-<llama.cpp build>` | `measure.yml` `llm` | the `runtime` job of the same dispatch | transient, 6.19 GB and 3.78 GB live |
| pip download cache, 3.12 | `setup-python` default, hashed from `pyproject.toml` | any 3.12 job | `gates`, `site`, `browser`, `robots`, every `digest.yml` job, `measure.yml` `corpus` and `runtime`, `drift.yml`, `prune.yml`, `validate.yml`, `backfill.yml` | 203 MB |
| pip download cache, 3.14 | same scheme, 3.14 | `robots` | `robots` | 183 MB |
| npm download cache | `setup-node` default, hashed from `frontend/package-lock.json` | any job running `npm ci` | `site`, `browser`, `whole-day`, `pages.yml`, `digest.yml` `assemble`, `backfill.yml` | 164 MB |
| Browser binaries | `playwright-<os>-<playwright version>` | `ci.yml` `browser` and `whole-day` | both, on every pull request that buys the browser half | 269 MB |

Every size is from the 2026-09-17 listing above. **The visual planner entry is no
longer here, and its going is the eviction rule working.** `Qwen3-4B-Q4_K_M.gguf`
served that job until plan 11 row #6 retired it on 2026-09-13, nothing restored
the entry afterwards, and GitHub deleted the 2.27 GB. The same rule aimed at the
summariser entry is the risk named above.

The weights key and why it carries a revision and a build are in
[ci-model-runtime.md](ci-model-runtime.md#the-inference-runtime-is-pinned-and-the-cache-key-says-which-build).

## The rule: a cache earns its bytes by being read more often than it is written

An entry unread for 7 days is deleted. So the question is not "would a hit be
faster" - a hit is always faster. The question is **how often the job runs**,
and it has three answers.

**Runs daily or on every change: cache it.** The entry is touched constantly,
never ages out, and the restore is paid once per job against a download paid
once per job. Every entry in the table above except one is here.

**Runs a few times a month: do not fill an entry of its own.** Measured over the
30 days to 2026-09-17, grouped by workflow file so a renamed display name does
not split a count: `ci.yml` ran 2,362 times, `pages.yml` 988 and `digest.yml`
128, while `measure.yml` ran 26 times (newest 09-16), `prune.yml` 18, `drift.yml`
4 (newest 09-13), `validate.yml` 4 (newest 08-26) and `backfill.yml` not at all.
A cache on a workflow at that rate is cold on every dispatch: it
pays the save on the way out and the entry expires before anybody comes back
for it. It also crowds the entries the daily jobs need to keep warm. **Such a job
may still share a key a daily job keeps warm** - which is what `measure.yml`
`corpus` does, naming the same interpreter and the same `pyproject.toml` the
daily jobs name, so it hits on run one and fills nothing.

**Runs rarely but fans out inside one run: cache it anyway.** `validate.yml`
`qualify` is one case and `measure.yml`'s bench is the other. Both are
dispatched a handful of times a month, so neither ever hits from a previous run
- but `qualify`'s matrix means the first shard downloads the candidate weights
and every other shard of that same run restores them, and the bench's raw case
downloads the candidate so its server case can restore it a step later. The
reader is the sibling job, not the next week. Both entries age out unread within
the week and give their bytes back, which is why two 5 GB entries on top of the
daily ones do not have to fit under the 10 GB allowance at once: GitHub evicts
the least recently used rather than failing the save.

## What is deliberately not cached

**The `--with-deps` half of the browser install.** `npx playwright install
--with-deps chromium` measured 24.9 s (n=8, min 22 s, max 34 s, spread 12 s) on
`ubuntu-latest` across four CI runs on 2026-09-12. Read from the step log of run
34678620051, about 15 s of that is `apt-get`, and every package it actually
downloads is a font: Japanese, Chinese, Thai, Cyrillic and Unifont, plus the
X font utilities. The runner image already has the shared libraries. A cache
cannot hold an `apt-get`, so the install step stays and stays unconditional -
what the cache removes is the other 9 s, the 184.3 MB of Chromium, 114.7 MB of
headless shell and 2.3 MB of FFmpeg.

**Dropping the fonts would save more than the cache does, and it is not done
because nobody has measured it.** The digest publishes English, so on the face
of it none of those fonts is used. But `layout-overflow.spec.ts` measures text
against its container, and a missing font changes what fontconfig substitutes
and therefore what the browser measures. The failure that risks is a check that
goes on passing in CI while disagreeing with a developer box, which is worse
than 15 s. An unmeasured number may not justify a design (Guardrail #10), so this
stays as it is until somebody runs the case.

**`measure.yml` `image`'s CPU-only torch install.** It installs from a separate
package index and shares no dependency file with anything else, so it would need
a key and roughly 250 MB of its own. The job is dispatched a few times a month.
By the rule above, that entry would expire unread every time.

**A second browser entry.** `browser` and `whole-day` start together, so neither
can warm the other; they share one key and the hit comes from the previous run
on `main`. Two keys would double the bytes and halve nothing.

**Anything a build produces.** `npm run build` output is not cached. It is
rebuilt from committed data in about 20 s, and a stale build tree is the one
failure this project cannot afford to debug: `frontend/build` is a single
directory that the real build and the canary build both write, which is already
why the whole-day check needs its own job.

## Design rationale

**The cache was written up as a ceiling until 2026-09-17, and it never was one.**
Guardrail #2 listed 10 GB of cache beside the 6 h job timeout and closed on a
boundary clause, so an agent reading it took all seven numbers for the same kind
of thing and quoted "it busts the 10 GB cache" as a reason a design could not
ship. This page inherited the framing and called the over-allowance state a
breach.

GitHub's dependency-caching reference, read 2026-09-17, says otherwise. There is
no limit on the number of caches; the total size per repository is limited, 10 GB
by default, and that default can be raised by an organization or repository
administrator. Past the limit GitHub "will save the new cache but will begin
evicting caches until the total size is less than the repository limit", oldest
last-access first, and it removes any entry "that have not been accessed in over
7 days" whatever the total is. The named failure mode is cache thrashing -
entries created and deleted at a high frequency - not a refused save. GitHub's
Actions billing page, read the same day, says usage is free for public
repositories on standard runners, and that a repository owner is charged for
cache "only if the repository cache storage limit has been configured higher than
the included usage". Nobody has configured this one higher.

**The distinction matters because it changes what an agent is allowed to say.**
A number that fails a run ends an argument. A number that costs a re-download is
a cost to price against what the design buys. Guardrail #2 now states the
consequence beside each figure and rules that a figure quoted without it is a
half-quote, which is CLAUDE.md section 1 applied to the guardrail's own numbers.
The same pass retired the 500 MB artifact figure as a limit here: it is a
private-repository quota, and this repository is public. Two earlier passes had
already found half of this and neither reached Guardrail #2 - the pipeline plan
struck the artifact figure on 2026-08-20, and an owner ruled on 2026-09-12 that
the cache ceiling is managed by the platform rather than defended by this
project.

**The browser cache was added on 2026-09-12, and the number that decided it was
not the download.** The download is 9 s of a 25 s step, twice a run, against a
`browser` job that measured 200 s on a pull request and 367 s on `main` (run
34678620051 and run 34678820720, 2026-09-12). That is 4 percent of the wait on a
pull request - worth taking, not worth much.

What decided it was eviction pressure. Every extra entry moves an entry somebody
needs closer to being the least recently used, so the design had to be one key
rather than two, keyed on something that moves rarely rather than on
a lockfile hash. **Keying on `hashFiles('frontend/package-lock.json')` was the
obvious thing and it is the wrong thing**: that hash moves when any of the
eighteen frontend dependencies moves, so a Tailwind patch release would throw
away 300 MB of browser and refetch it. Playwright pins one browser build per
release, so its own version is what the restored bytes actually depend on. The
version is read once, in `scope`, and both jobs key on that output - the same
shape `digest.yml` uses for the weights key, and for the same reason: a key
written out twice drifts, and a drifted key misses silently for ever.

**Two contract tests hold it**, in `backend/tests/workflows/`. One finds
every job in the repository that installs a browser - found, not listed, so a
new job that downloads Chromium on every run cannot slip past - and asserts they
share one key, one path, and a restore ahead of the install. The other resolves
the reader's own expression against the committed lockfile, because a renamed
package or a moved lockfile makes the key a constant prefix and nothing goes
red; CI just gets slower and stays slower.

**What this does not do.** It does not shorten the two things that actually set
the wait: the browser suite at 103 s on a pull request and 259 s on `main`, and
the backend suite at 81 s. Those are tests doing work, not downloads, and they
are the place to look next.

## See also

- [github-actions.md](github-actions.md) - the workflows, their triggers, the weights cache key, and the platform behaviour behind these numbers.
- [measurements.md](measurements.md) - the instrument log, including the cache reading taken across the 2026-08-27 model swap.
- [benchmarks/what-a-bench-dispatch-costs.md](benchmarks/what-a-bench-dispatch-costs.md) - what a cache restore is worth against the 188.5 minutes a bench dispatch takes.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - which gates run where, and what CI is authoritative for.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2, which says what crossing each runner number does, and Guardrail #10 (measured, not estimated).
