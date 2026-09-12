# CI Caches

**Last Updated**: 2026-09-12

Every cache this repository keeps, what it holds, who reads it, and the bar a
new one has to clear. Read this before adding one: the ceiling is shared, it is
nearly full, and the entry a careless addition evicts is the one the daily
pipeline needs.

`CLAUDE.md` Rule #2 states the 10 GB ceiling. The eviction behaviour behind it -
an entry unread for 7 days is deleted, and a restore is paid once per job rather
than once per run - is in
[github-actions.md](github-actions.md#platform-limits-that-shape-the-workflows).
This page is the inventory and the rule.

## The budget, measured

Read with `gh api repos/miztiik/yen-idhazh/actions/cache/usage` and
`.../actions/caches` on 2026-09-12. `n=1` - a cache listing is a state, not a
sample, so there is no spread.

| | Bytes | Of the 10 GB ceiling |
| --- | --- | --- |
| All 9 entries | 8.61 GB | 86% |
| The two model weight entries alone | 7.50 GB | 75% |
| Everything else (pip, npm) | 1.11 GB | 11% |

**Three quarters of the ceiling is two files of model weights, and both are
live.** `Qwen3.5-9B-Q4_K_M.gguf` is the summariser and `Qwen3-4B-Q4_K_M.gguf`
is the visual planner, both named in `config/idhazh.json`, both restored by the
daily pipeline. Neither is stale and neither can be deleted.

So the headroom for anything new is about 1.4 GB, and an addition that pushes
past 10 GB does not fail loudly. GitHub evicts the least recently used entry -
which, on a quiet weekend, can be a 5 GB weights entry the next digest run then
refetches from Hugging Face. **A cache that overflows the ceiling costs the
pipeline far more than it ever saved CI.**

## The inventory

| Cache | Key | Filled by | Read by | Size |
| --- | --- | --- | --- | --- |
| Summariser weights and runtime | `llm-<file>-<revision>-<llama.cpp build>-v4` | `digest.yml` `work` | every `work` shard of every run | 5.23 GB |
| Visual planner weights and runtime | same scheme | `digest.yml` `visuals` | `visuals`, every run | 2.27 GB |
| Candidate weights and runtime | `qualify-<candidate sha256>-<llama.cpp build>` | `validate.yml` `qualify` | the other shards of the same run | transient |
| pip download cache, 3.12 | `setup-python` default, hashed from `pyproject.toml` | any 3.12 job | `gates`, `site`, `browser`, `robots`, every `digest.yml` job, `measure.yml` `corpus` and `runtime`, `drift.yml`, `prune.yml`, `validate.yml`, `backfill.yml` | 173 MB |
| pip download cache, 3.14 | same scheme, 3.14 | `robots` | `robots` | 152 MB |
| npm download cache | `setup-node` default, hashed from `frontend/package-lock.json` | any job running `npm ci` | `site`, `browser`, `whole-day`, `pages.yml`, `digest.yml` `assemble`, `backfill.yml` | 164 MB |
| Browser binaries | `playwright-<os>-<playwright version>` | `ci.yml` `browser` and `whole-day` | both, on every pull request that buys the browser half | about 300 MB |

The weights key and why it carries a revision and a build are in
[github-actions.md](github-actions.md#the-inference-runtime-is-pinned-and-the-cache-key-says-which-build).

## The rule: a cache earns its bytes by being read more often than it is written

An entry unread for 7 days is deleted. So the question is not "would a hit be
faster" - a hit is always faster. The question is **how often the job runs**,
and it has three answers.

**Runs daily or on every change: cache it.** The entry is touched constantly,
never ages out, and the restore is paid once per job against a download paid
once per job. Every entry in the table above except one is here.

**Runs a few times a month: do not fill an entry of its own.** Measured over
the 30 days to 2026-09-12: `ci.yml`, `digest.yml` and `pages.yml` ran more than
100 times each, while `measure.yml` ran 8 times with its newest run on 08-25,
`validate.yml` 4 times (newest 08-26), `drift.yml` 3 times and `backfill.yml`
not at all. A cache on a workflow at that rate is cold on every dispatch: it
pays the save on the way out and the entry expires before anybody comes back
for it. It also spends ceiling that the daily jobs need. **Such a job may still
share a key a daily job keeps warm** - which is what `measure.yml` `corpus`
does, naming the same interpreter and the same `pyproject.toml` the daily jobs
name, so it hits on run one and fills nothing.

**Runs rarely but fans out inside one run: cache it anyway.** `validate.yml`
`qualify` is the case. It is dispatched a handful of times a month, so it never
hits from a previous run - but its matrix means the first shard downloads the
candidate weights and every other shard of that same run restores them. The
reader is the sibling job, not the next week.

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
than 15 s. An unmeasured number may not justify a design (Rule #10), so this
stays as it is until somebody runs the arm.

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

**The browser cache was added on 2026-09-12, and the number that decided it was
not the download.** The download is 9 s of a 25 s step, twice a run, against a
`browser` job that measured 200 s on a pull request and 367 s on `main` (run
34678620051 and run 34678820720, 2026-09-12). That is 4 percent of the wait on a
pull request - worth taking, not worth much.

What decided it was the ceiling. At 8.61 GB of 10 GB, the repository could
afford roughly one more entry of this size and no more, so the design had to
be one key rather than two, keyed on something that moves rarely rather than on
a lockfile hash. **Keying on `hashFiles('frontend/package-lock.json')` was the
obvious thing and it is the wrong thing**: that hash moves when any of the
eighteen frontend dependencies moves, so a Tailwind patch release would throw
away 300 MB of browser and refetch it. Playwright pins one browser build per
release, so its own version is what the restored bytes actually depend on. The
version is read once, in `scope`, and both jobs key on that output - the same
shape `digest.yml` uses for the weights key, and for the same reason: a key
written out twice drifts, and a drifted key misses silently for ever.

**Two contract tests hold it**, in `backend/tests/test_workflows.py`. One finds
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

- [github-actions.md](github-actions.md) - the workflows, their triggers, the weights cache key, and the platform limits behind the ceiling.
- [measurements.md](measurements.md) - the instrument log, including the cache reading taken across the 2026-08-27 model swap.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - which gates run where, and what CI is authoritative for.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #2 (the runner budget, including the 10 GB ceiling) and Rule #10 (measured, not estimated).
