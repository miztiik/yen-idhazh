# Run the Gates

**Last Updated**: 2026-09-05

Set up a machine, then run every check `CLAUDE.md` section 9 asks for before a
merge. This page owns the project's actual gate commands; the neutral PR
lifecycle that calls for them is
[ship-a-pr.md](ship-a-pr.md).

Counts and file numbers below were taken on 2026-08-24 and move as the repo
grows. Treat them as a "did the command do roughly what I expected" check, not
as a target.

## Select local checks and let CI run the full suite

Use the shared launcher from `frontend/`. It requires Node 22.18 or newer and
the existing development environment. Inspect the selection before running it:

```powershell
npm run test:changed -- --list
npm run test:changed
```

The selector includes committed changes against `origin/main`, staged edits,
unstaged edits and untracked files. Use `--base <ref>` for a different base.
Every selected group prints the path and reason that selected it. Shared
contracts, config, styles, layouts and dependencies expand coverage. An unknown
path or an unreadable base selects broader coverage, never an empty pass.
Documentation-only changes run a whitespace check, not either application suite.

| Group | What it checks | Preparation |
| --- | --- | --- |
| `backend` | Named module and integration tests, or the full backend for shared or unknown inputs; ruff and mypy | Existing Python development environment |
| `logic` | Verified build-independent frontend functions | No site build, preview server or Chromium |
| `reader` | Reading pages, layout, filters, themes and read state | Canary build |
| `console` | The operator dashboards | Canary build |
| `archive` | Browsing, calendar and pagination | Canary build |
| `model-search` | On-device search and recovery | Canary build |
| `publishing` | Payloads, projections, canaries and malformed-day handling | Canary build and Python |

For the inner loop, request a group or one existing spec explicitly. Such a
result certifies that selection, not every check the automatic selector chose:

```powershell
npm run test:changed -- --group logic
npm run test:changed -- --group console
npm run test:changed -- --spec archive.spec.ts
npm run test:changed -- --mode real --spec reading-page.spec.ts --spec layout-overflow.spec.ts
```

`--group browser` selects all frontend groups; `--group all` adds the backend.
The `all` selection also includes schema regeneration and the tooling tests.
Choose group flags or spec flags for one invocation, not both. Several spec
flags can select tests from different groups.
A real-build run requires an explicitly supported reading or visual spec, so
canary-dependent console assertions cannot accidentally run against real data.
Keep the section 12 browser smoke for a published-site change.

The launcher checks the dependencies the selection needs before waiting for a
test slot. A logic-only run does not probe Python packages or run pytest. It
uses the existing Python standard-library lock helper for coordination only.
The tooling self-tests run when the test infrastructure changes, or with
`--group all`; they are not added to every frontend run. Browser preparation
still needs the Python producer. The launcher honors `IDHAZH_PYTHON` or
`--python <path>`.
It clears inherited data-root overrides and `PYTEST_ADDOPTS`. A missing or stale
canary build is prepared automatically: canary day, canary site, then selected
browser tests. Build and test share one lock. The logic-only path uses a
checkout-local lock and does not queue behind another checkout's site build.
Both paths require the lock. If it cannot be acquired, the launcher exits 75
without starting the checks. It does not reclaim a live holder's lock based
only on age. The lock helper's legacy unlocked fallback remains available to
direct callers that do not pass `--require-lock`.

Every normal `npm run build` captures its mode, source inputs and build
environment after staging and before compilation. Starting a build invalidates
its previous completion record. Completion verifies the same inputs, then
records static output and SvelteKit preview output outside the published tree.
A source edit during compilation cannot certify the old output. Browser
tests refuse an unrecorded, wrong-mode or stale build. Preview never adopts an
existing server. `PREVIEW_PORT` remains the override for a port collision.

Run records under `backend/var/checks/` hold the source fingerprint, selected
groups and specs, exit status, step durations, test counts and queue/startup
time separately. Logic and browser reports use separate output directories.
A matching completed run is reused.
A caller joining the same active run waits for that attempt, not an old pass.
Only an explicit `--fresh` reruns unchanged completed inputs. A failed or
interrupted run is never reported as success, and collection-only or all-skipped
reports cannot certify a change. Inspect status instead of relaunching:

```powershell
npm run test:changed -- --status
```

The group inventory includes subdirectories and fails when a new spec has no
owner. Its tests also prove
that shared and unknown paths select broader coverage. New dependencies between
areas need a selector regression test, not only a new group label. The selector
lives in `frontend/scripts/test-scope.ts`; the group inventory lives beside it
in `test-groups.ts`. CI uses that same selector for its browser/console choice,
keeps the full backend suite, and runs all frontend groups on `main`.
The selector job and the backend test job declare the same Node version,
because the workflow tests execute that TypeScript selector. The backend job
does not install frontend packages for it; the selector uses Node's built-ins.

For a local contract change, the launcher compares schema files before and
after export. Correct uncommitted generated files can pass; an exporter that
changes them requires review and a new run. CI still compares its clean
checkout against the committed schemas.

## Direct backend checks

**CI is the authoritative arm and it is faster than your machine by between six
and fifteen times.** The `gates` job finishes the whole backend suite in about
90 seconds on a clean runner; the same suite on a developer box shared with
other agents has measured 8 to 45 minutes. It also runs on Linux, on the merge
candidate, alone on a machine - three things a local run cannot reproduce.

So the default before pushing is the three checks that fail fast and cannot be
delegated, because they tell you the branch is wrong before CI has finished
installing:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/test_<the module you changed>.py
```

Then push and read CI. A focused run uses one process to avoid starting every
worker for a small selection. The full-suite defaults are unchanged.
When the change reaches further than one module, the third line can use a mark
selector: `-m contract`, `-m visual`, `-m workflow` or `-m "not slow"`, priced
[below](#run-only-the-tests-a-change-can-break).

**Run the full local suite when you cannot push, or when you are about to merge
and want the answer now.** The commands are below and none of them is going
away. What changed on 2026-08-30 is which one is the default: blocking on a
25-minute local suite before every push, for a change CI clears in 90 seconds,
was the single largest cost in the console-signal plan.

Two exceptions where local is still the only arm. A published-site change needs
the browser smoke in `CLAUDE.md` section 12, which is a real browser on your
machine. And a change to a workflow's own shell needs `shellcheck`, which is
seconds either way.

## Set up the backend environment

Python 3.12, 3.13 or 3.14. CI installs 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -c "import sys; print(sys.version)"
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

**Read that second line before you install.** `python -m venv` takes whatever
`python` resolves to, which is often not the one you meant. `pyproject.toml`
declares `requires-python = ">=3.12,<3.15.0a0"`, so pip refuses an interpreter
outside the range instead of hanging on it -
[../reference/agent-notes.md](../reference/agent-notes.md) has the symptom that
used to show instead, and the escape when the machine has nothing else.

**`uv pip install` does not work here.** It fails with a `HandshakeFailure`
against `files.pythonhosted.org` (observed 2026-08-21). `ensurepip` then `pip`
is the path that works. If `uv` starts working, nothing in the repo depends on
which installer produced the environment.

Five extras are declared. Install only what you need:

| Extra | Pulls | When |
| --- | --- | --- |
| `dev` | `ruff`, `mypy`, `pytest`, `PyYAML`, `shellcheck-py` | always - this is the gate set |
| `measure` | `feedparser`, `trafilatura` | live source sampling; hits the network |
| `bench-image` | `torch`, `diffusers` | image-model benchmarking; multi-gigabyte |
| `faithfulness` | `torch`, `transformers` | the HHEM scorer; multi-gigabyte, and it downgrades `tokenizers` |
| `langfuse` | `langfuse` and six OpenTelemetry distributions | only to send spans to a Langfuse host you named; 32.7 MB and about 4 minutes |

`measure`, `bench-image` and `faithfulness` are heavy, and the first reaches the
network. No test imports any of them, and `langfuse` is imported inside one
function that only runs when `LANGFUSE_HOST` and its key pair are all set. The
local span sink needs none of it.

## Running the gates when the machine is shared

Several agents work in their own worktrees on one box, and each starts its own
gate the moment it is ready. Nothing coordinates them, so the gates fight over
the same cores - and the loser looks like a broken branch rather than a busy
machine. Wrap the three gates measured as CPU-bound so one of them runs at a
time across every worktree:

```powershell
python backend/utilities/gate_lock.py -- python -m pytest
python backend/utilities/gate_lock.py -- npm run build
python backend/utilities/gate_lock.py -- npm run test:browser
```

`ruff`, `mypy`, `svelte-check`, `shellcheck` and `bundle-gate` stay unwrapped:
serialising a gate that finishes in seconds only adds waiting. The tool reads no
configuration and imports nothing from `idhazh`, so any supported Python runs it
from a fresh clone. **CI never takes it** - a runner is one job alone on its own
machine (Rule #2), so nothing about a CI run moves. A caller that has to wait
prints who holds the lock, from which worktree, running what, and for how long,
every 30 seconds. And it cannot fail your gate: a lock whose holder died is
reclaimed, and a caller that waits out `--timeout` runs the gate unlocked rather
than returning an error. What the lock does not save you from is in
[../reference/agent-notes.md](../reference/agent-notes.md).

**Never buy a pass with a raised timeout, an added retry or a relaxed
assertion.** A suite that times out while siblings hold the cores has measured
the box, not the branch. Take the lock, or re-run it alone. Widening the bar
hides the contention and the false red returns at the next fan-out.

### The backend suite can use every core the box has

`-n auto` shards the suite across the machine's processors. It is already the
default in `pyproject.toml`, locally and in CI. Use `-n 0` for a focused or
debugging run. Disabling the plugin alone does not remove `-n auto` from the
configured arguments.

```powershell
python backend/utilities/gate_lock.py -- python -m pytest -n auto
```

Nothing needs pinning to one worker. Every test that binds a port binds an
ephemeral one, no test changes the working directory, and no test writes into a
tracked root - so the parallel run passes the same node ids as the serial one
and leaves `git status --porcelain` empty.

### Run only the tests a change can break

Four marks are declared in `pyproject.toml`. Each is a module-level
`pytestmark`, so a module that gets renamed or moved keeps its mark and no list
anywhere has to be repointed.

| Selector | What it holds | Tests | `-n auto` | `-n 0` |
| --- | --- | --- | --- | --- |
| `-m contract` | The persisted shapes: the generated schemas, the two config contracts, the append-only ledgers, the committed digest tree | 564 | 20.9 s (n=2, spread 2.5) | 17.3 s |
| `-m visual` | The visual planner, its validator, the spec compiler, both renderers, and the planted attacks aimed at the planner | 161 | 19.9 s (n=2, spread 3.3) | 14.3 s |
| `-m workflow` | The workflow YAML and the shell scripts under `.github/` | 134 | 80.9 s (n=1) | - |
| `-m slow` | Every module whose average test runs over a second | 335 | 131.8 s (n=1) | - |
| `-m "not slow"` | Everything else, which is 84 percent of the tests | 1,807 | 39.3 s (n=1) | - |
| nothing | The whole suite, which is what CI runs | 2,142 | 155.4 s (n=2, spread 45.9) | - |

**Windows 11, 12 logical CPUs, Python 3.14.2, pytest 9.1.1, 2026-09-05**, every
arm through `gate_lock.py` so no sibling gate could land inside a timing.
`-n 0` is the faster arm for a small subset, because twelve workers cost about
seven seconds to start and that is most of what a 161-test run pays.

**Read the ratio rather than the seconds.** The whole-suite spread is 45.9 s on
a 155.4 s mean - 30 percent of itself, and that is the shared box rather than
the suite. A contract change runs in about a seventh of the time the whole suite
takes, and the worst pairing measured - the slowest subset run against the
fastest whole-suite run - is still six times. The two selectors that save least
say why by themselves: `-m workflow` picks the slowest file in the repository,
and `-m slow` picks the slow modules on purpose.

**CI runs everything, and always will.** A mark is a shortcut for the person
writing the change, never the thing that decides what a merge is checked
against - so a test marked wrong costs a re-run rather than a missed regression.

Two things stop a mark going quietly wrong. `--strict-markers` is in `addopts`,
so a name that is not one of the four is a collection error naming the file
instead of a warning nobody reads. And `backend/tests/test_marks.py` collects
the suite whole, once per mark and once for the complement, then fails naming
any module that no mark selects and that its own `UNMARKED_MODULES` set does not
name - so a new test module has to be classified before it can merge.

**Thirty-three modules carry no mark on purpose.** A developer working in one of
those areas already has something shorter to run than the whole suite: that
module. And `-m "not slow"` still pays for the two longest tests outside the
slow set, one in `test_extract.py` at 37 s and one in `test_embed.py` at 16 s.

**What each gate costs on a developer box, and what `-n auto` buys, is measured
in [../reference/measurements.md](../reference/measurements.md#what-the-gates-cost-on-a-developer-box).**
Read it there rather than guessing from one run: on a machine several agents
share, the same suite spans a factor of three depending on who else is working.

## The backend gates

Run all five from the repository root. Each must be clean.

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\shellcheck.exe --severity=style (Get-ChildItem .github/scripts/*.sh).FullName
.\.venv\Scripts\python.exe -m idhazh.contracts.export
git diff --exit-code -- schemas/
```

On 2026-08-25 that is 858 tests and 88 files type-checked. The last two lines
are the contract drift gate: the export regenerates `schemas/` from the Pydantic
models, and a non-empty diff means a generated artifact was hand-edited or a
model changed without regenerating ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)).

**`shellcheck` is the same binary CI runs**, installed by the `dev` extra rather
than downloaded, so the local gate and the CI gate cannot disagree about a
version. CI writes the same command with a bare `.github/scripts/*.sh`, because
bash expands a glob and PowerShell does not - hand shellcheck the literal
pattern and it reports `openBinaryFile: invalid argument`, which reads like a
broken install. It prints nothing on a pass, and a silent run is the pass.

It reads files, so it covers `.github/scripts/` and nothing else. The shell
written inline in a workflow `run:` body is held by the contract tests in
`backend/tests/test_workflows.py`
([../reference/github-actions.md](../reference/github-actions.md#the-linter-reads-scripts-and-the-test-reads-the-rest)).

**`ruff format` is not a gate.** `ruff format --check .` reports dozens of files
it would rewrite - 14 on 2026-08-24 and 38 on 2026-08-29 - all of them
pre-existing. That count is deliberately written as a magnitude rather than a
figure: it tracks how much Python the repository holds, so an exact number here
is wrong within days and the fact worth carrying is that the diff is large and
none of it is yours. Running it across the repo produces a large diff that has
nothing to do with your change. Format only the files you author, or leave
formatting alone.

## The frontend gates

Run from `frontend/`.

```powershell
npm run check
npm run build
npm run bundle-gate
python -m idhazh site-weight --site-tree build
```

`check` is `svelte-check`. `build` is the strongest of the three: every route is
prerendered, so a route that cannot render fails the build rather than the page.
**It stopped answering for every story on 2026-09-01.** A reading document
carries `ui.shell_seed_items` stories and the browser fetches the rest, so the
build never opens the stories past the seed. `python -m idhazh validate-days`
opens all of them, against the committed shape the build reads and the served
shape a browser fetches, and it runs in `ci.yml` and before every publish. It
takes no path - there is one committed digest tree - and a run that finds no day
at all fails rather than passes.

`site-weight` is the fourth, and it is the only one that measures the whole
site rather than one page. It sums `frontend/build/` - the directory the Pages
deploy uploads - and holds it against two lines: over `retention.site_budget_mb`
in `config/idhazh.json` it prints a warning and passes, and past the 1 GiB Pages
cap it fails. **Point it at anything else and the suite fails**, because the tree
is read back off `pages.yml`'s own upload step. It measures nothing until the
site is built, so run it after `npm run build`, and a run that reports zero files
fails rather than passes.

It prints three more lines and none of them fails anything. `by directory` is the
top-level children of `build/` largest first, so a directory that grew can be
named instead of guessed at from one moving total. `rate` is bytes per published
item, which is the unit that holds still - a rate per day moves by a factor of
six across days that published 731 items and 117. `runway` divides the headroom
by that rate at `run.safety_ceiling_per_run` items a day and prints the answer in
published days, to the alarm point and to the cap. **The size on the line above
is a level, and no level has a date in it.** A tree carrying no day payloads
prints `runway: unknown` rather than a comfortable number.

`bundle-gate` does two things. It asserts no encoder lands on the first-load
path, and it holds every route named in `config/idhazh.json` under the gzip
ceiling set there.

**A third check was deleted on 2026-08-30**: a per-route first-load JavaScript
ratchet against `frontend/bundle-baseline.json`, at 64 bytes either way. It had
no requirement behind it, a local build could not reproduce CI's inside its own
tolerance, and its record was one file every branch had to rewrite. The
reasoning is in
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md#the-bundle-gate-checks-two-promises-and-used-to-check-three).
If you are reading an older commit that fails on a route weight, that is why it
is gone rather than something you need to re-record.

**The page ceiling is one-sided, and it bounds the document rather than the
script.** `page_weight.ceilings_bytes` in `config/idhazh.json` gives the largest
`gzip -9` size each named route's prerendered HTML may reach. A page that got
lighter needs no permission, so there is no lower bound. A route is named when
its growth has been priced: `/404` and `/evals/` move only when the source moves,
`/archive/` grows by one day link a published day, and `/console/` grows by about
20 gzipped bytes a published telemetry row. A day page and the home page weigh what the
day published, so a fixed ceiling on either would cap the news instead of
catching a regression - the only way under it is to publish fewer items, which
[layout.md](../architecture/publishing/layout.md) forbids. Those two are covered
by the marker count in `frontend/tests/payload-weight.spec.ts`, which runs in the
browser suite. A route the config does not name is reported by the gate without
failing it.

When a named route is over, two failures are worth telling apart:

- **A page took on bytes it does not render.** A day payload inlined by a layout
  is how this last happened, and it cost 313,000 bytes. Remove them.
- **The page genuinely carries more.** Raise the number in `config/idhazh.json`,
  in the commit that earned the bytes, and say in the message what they buy. The
  number lives in that file alone - the `PageWeightConfig` default is empty - so
  there is no second copy to move.

**A ceiling is not raised to buy time.** `/archive/` was capped, raised twice in
one day on 2026-08-26 to silence a gate that fired on ordinary publishes, and
then uncapped, because a page that inlined every committed day could not hold a
fixed number. It is capped again since 2026-08-27 at 7,553 bytes, which is the
heaviest of five builds plus a measured year of publishing plus the 64-byte
noise floor. That headroom shrinks about 8 bytes on every publish since the day
list folded into month disclosures on 2026-09-01, down from 12 to 18 before it,
and it expires by design: when the gate fires on an ordinary day, the answer is
to re-measure and re-derive the number, not to add a digit
([../reference/measurements.md](../reference/measurements.md#the-ceiling-that-holds-the-saving-and-where-its-headroom-comes-from)).

**The console is three routes and takes three ceilings, all re-derived on
2026-08-31 once every row that touches those routes had merged.** One key over
three surfaces fails without saying which surface failed, so `/console/`,
`/console/model/` and `/console/machine/` each carry their own: **251,324**,
**29,273** and **31,714** bytes.

Each is the heaviest of five builds of the tree that ships, plus seven publishes,
plus the 64-byte build noise floor. What a publish costs is measured by removing
one real mature day from every ledger the console reads and rebuilding - 19,301
gzipped bytes on `/console/` and 1,179 on `/console/model/`. `/console/machine/`
is priced in RUNS instead, at 244 bytes a run over seven days at the observed
maximum of five runs a day, because a day that ran three times and a day that ran
five cost it differently
([../reference/measurements.md](../reference/measurements.md#all-three-console-ceilings-re-derived-once-every-row-had-merged-2026-08-31)).

**None of the three had fired when they were raised, and that is the normal
case.** A ceiling is re-derived because its runway expired, not because a gate
went red: the pages measured 116,153, 20,956 and 23,110 against the numbers they
replaced. All three are meant to expire again, and `/console/` expires first -
its slack is exactly seven published days.

**When a console ceiling fires, the panel does not move.** The owner ruled on
2026-08-31 that no approved feature is removed, deferred or shrunk to stay under
a page-weight number: a ceiling is a ratchet, so the answer is to re-measure it,
raise it, and record in the same commit what the bytes bought. That reverses the
guidance this page carried until then, which was to turn `console.default_window_days`
down instead. Turning the window down is still the right first move when the
page is inlining something the first paint does not need - it is a saving rather
than a cut - but it is no longer a reason to leave a panel unbuilt. The two
limits the ruling does **not** waive are Rule #2's 1 GB Pages cap, which is a
platform limit, and the 200,000-byte lazy chart chunk, which stands because a new
echarts registration is a decision about the chart vocabulary and not about size
([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md#the-console-ceiling-is-a-tripwire-and-what-to-do-when-it-fires)).

## The browser suite

The browser gate runs against the **canary day**, not the real digest, so it
does not change meaning when the pipeline publishes.

Prefer `npm run test:changed` locally. In the manual full frontend sequence
below, `test:logic` owns the build-independent group and `test:browser` owns the
other five groups. Together they retain the full test inventory.

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run test:logic
npm run build:canary
npm run test:browser
```

995 tests in 74 files (2026-09-05): 984 passed and 11 skipped, in 13.4 minutes
on an i7-1265U. The same suite measured 954 tests and 19.2 minutes on
2026-09-02, so read the minutes as the machine rather than the suite - the test
count is what grew. Every skip reads a fact the fixture owns rather than a
locator
count - the canary day is eight stories on one desk, so it cannot fill a leading
block and it never fetches. The
failure surface has a file of its own, `console-failure.spec.ts`, split by what
the fixture can reach: the canary records no failure at all, so the two facts
that need one - a denominator walked down the pipeline, and a rate withheld
under `console.min_attempts_for_rate` - are driven as pure functions, and every
state the fixture does reach is driven in the browser through the controls an
operator has. A hundred and four of that historical inventory were pure-function
tests over `frontend/src/lib/charts/`. Build-independent specs now use
`playwright.logic.config.ts`, with no preview server. Mixed specs remain in
their feature group. Both configurations use the existing Playwright runner.

**One spec asks a question the canary day cannot answer, and says so.**
`reading-page.spec.ts` reads the reading surface whole - every reader route at
360, 801 and 1536 CSS px in both themes, the time rail against the item's
eyebrow, the aside against the sticky filter panel, and a day whose stories are
broken at the network. Four of its arms need a day longer than
`ui.shell_seed_items`, because a document that already carries its whole day
never fetches, and the canary is eight stories against a seed of fifteen. They
skip here on a fact the served payload owns and run against the real digest:

```powershell
npm run build
$env:IDHAZH_TEST_BUILD = 'real'
npx playwright test tests/reading-page.spec.ts tests/layout-overflow.spec.ts
Remove-Item Env:IDHAZH_TEST_BUILD
```

Take that arm before `build:canary`, which overwrites the same `build/`
directory. **Two of its arms are expected to fail and are annotated
`test.fail()`**, because the composed page has two defects nobody has decided
how to fix ([../architecture/publishing/layout.md](../architecture/publishing/layout.md#what-the-composed-page-gets-wrong-2026-09-02)).
An expected failure turns the suite red the day it starts passing, which is
when the annotation comes off.

**A second spec cannot run here at all, and it fails rather than skips when it
is handed the canary.** `whole-day.spec.ts` draws the heaviest committed day
whole - every story, every drawing, at 390 and 1440 CSS px, in both themes - and
asks the four things a per-drawing check cannot see: whether the day ever
finishes arriving, whether every drawing it published reached the page, whether
any two of them turned out to be the same drawing, and whether every mark takes
its colour from a page token rather than from the hex the renderer baked in. The
canary is eight stories on one desk against a seed of fifteen, so it never
fetches and never reaches that scale. A skip there would be a check that quietly
stopped existing, so the module refuses to load unless the tree under test
serves exactly the days this repository has committed, and `playwright.config.ts`
keeps the file out of the default suite - `npm run test:browser` cannot reach it
and neither can naming it on the command line, because `testIgnore` filters
before an argument does.

```powershell
npm run build
npm run test:whole-day
```

**Between 2.8 and 3.7 minutes end to end** on an Intel Core i7-1265U,
2026-09-05, over two full runs on a machine several agents share: the build took
72.2 and 117.5 seconds, and the spec 97.3 and 102.1. The spec is 7 tests - three
that read the day off disk in under 25 ms each, and four browser arms that
spanned 13.7 to 28.4 seconds across the two runs. That spread is the shared box
rather than the widths, which is also why the build figure nearly doubles
between two runs of one tree. Which day it looks at is derived and never written
down: the committed day staging the most drawings, which on 2026-09-05 is
2026-08-31 with 43 drawings across 601 stories. Take this arm before
`build:canary`, which overwrites the same `build/` directory.

**It is not in CI, and that is a measurement nobody has taken rather than a
ruling that it does not belong there.** The `browser` job measured 528, 528, 569
and 583 seconds over its last four green runs (read 2026-09-05) against its
25-minute timeout, and it already builds the real site once for the model-absent
gate. What is missing is what this spec and its build cost *on a runner*, and a
developer-box figure may not stand in for one (Rule #10). Until somebody takes
that number there, run this by hand before a change to the reading page merges.

**A component with no call site proves itself here too.** A shared component
lands before the sections that render it, so the build tree-shakes it away and
no page exercises it. Compile it inside the spec instead: `preprocess` with
`vitePreprocess()`, then `compile(source, { generate: 'server' })`, write the
module under `frontend/test-results/`, `import()` it, and hand `render()` from
`svelte/server` the props. Feed that body and the `css.code` from the same
compile to `page.setContent` - the scope hashes match, because both came from
one compile - and the geometry can be measured with `getBoundingClientRect` in a
real browser. One constraint makes it work: the component must import nothing at
runtime, because a compiled module written outside its own directory cannot
resolve a relative `.ts` import. Everything it draws arrives as a prop. The
alternative is a route that exists only to host a test, and that route ships to
a reader.

**A skip condition must never read a locator count.** Written as
`test.skip((await panels.count()) === 0, ...)`, a test turns itself off the
moment the attribute it counts is renamed: nothing matches, the count is zero,
the skip fires, and the suite reports green. Read the skip against a fact the
fixture owns instead - the window the console publishes in an attribute, the
number of days the corpus carries - and then assert the selector matched, with
`await expect(locator, 'why this must exist').toHaveCount(n)`. Measured on
2026-08-27 by renaming the attribute the failure panels carried then -
`data-panel`, gone since the three panels became one chart: the count guard
reported `1 skipped` and exit 0, and the same test with the assertion reported
`1 failed` and exit 1, naming the attribute and the count it expected. A skip is
right only when the environment genuinely varies. It is never right for a
selector this repository controls, and the same mistake had already switched off
an injection canary in `canaries.spec.ts`
([../reference/agent-notes.md](../reference/agent-notes.md#running-the-gates)).

**The canary day carries every ledger the console reads.** The run manifest, the
feed-health rows and the score rows are all written by `build_canary_day.py`;
the item-health rows are written by `build:canary`. The score rows are shaped
for the compression plot rather than picked at random - eight items from 38 to
6100 source words, so the log x axis spans four decades, every configured target
zone has a mark under it, and two items carry the truncation flag that draws a
diamond. A chart state the fixture does not reach is a chart state this suite
cannot test.

**Known defect: the canary item ids do not satisfy the item-id grammar.**
`frontend/scripts/build-canary.mjs` writes ids like `tail-1-0` and `cut-a-0`,
and `ITEM_ID_PATTERN` in `backend/idhazh/contracts/base.py` needs at least two
trailing digits - so 76 of the 87 canary rows would be refused by `ItemHealthRow`
if anything validated them. Nothing does: the browser suite reads the CSV
directly, and the published projection carries `item_id` as an opaque key on
purpose, because a committed shard has no writer left to re-mint an id if that
grammar moves. Found independently while shipping two rows on 2026-09-02 and
2026-09-03, and left alone both times. It bites the day something validates the
canary rows through the contract. Fixing it means padding the index in the two
id builders and re-running the builder; nothing else reads those ids.

**The preview port derives from the checkout, so two worktrees cannot share one
server.** `playwright.config.ts` hashes its own directory into a port between
20000 and 29999, and the whole config - `baseURL`, the preview command and the
poll URL - follows it. A runner keeps 4173, so nothing about a CI run moved.
`PREVIEW_PORT` still overrides both, and it is what to reach for on the roughly
1 percent of checkout pairs that hash to one number:

```powershell
$env:PREVIEW_PORT = '4181'
```

Run this from `frontend/` to print the number this checkout will use, which is
the same derivation the config runs:

```powershell
node -e "const {createHash}=require('node:crypto');console.log(20000+createHash('sha256').update(process.cwd()).digest().readUInt32BE(0)%10000)"
```

Three traps make this suite lie to you. A fourth used to, and was fixed at the
source rather than written down as a step to remember: `build_canary_day.py`
now clears its state directory before writing, so running it twice no longer
stacks a second copy of every feed-health row and quarantines a feed the fixture
meant to keep healthy.

The traps that remain:

- **`frontend/build` is one shared directory.** `npm run build` and
  `npm run build:canary` both write it. If anything rebuilds the real site
  between your `build:canary` and your `test:browser`, the suite runs against
  real published dates and fails for reasons that are not your change. Confirm
  `frontend/build/console/index.html` still carries a canary date before and
  after the run.
- **An occupied preview port is rejected, not adopted.** `reuseExistingServer`
  is false locally and in CI. Stop a server only after proving that it belongs
  to your checkout, or choose another `PREVIEW_PORT`. Never kill every preview
  process on a machine shared with another agent.

- **The canary day has one vertical** (`ai`, 8 items). Any rule that only shows
  up with several topics cannot be tested here. Put that rule in a pure module
  and unit-test it there - `frontend/src/lib/day-shape.ts` exists for exactly
  this reason.

## Smoke-test a published-site change by hand

`CLAUDE.md` section 12 requires an agent to drive the affected pages in a
browser rather than hand the check to a person. Serve the **production build**,
not the dev server:

```powershell
npm run build
npx vite preview --outDir build --port 4174 --strictPort --host 127.0.0.1
```

- **The dev server cannot be used for this.** On `vite dev` a `script-src` CSP
  violation blocks SvelteKit's bootstrap, so the page never hydrates and every
  control - the theme toggle, `Show N more` - is dead. It is a Vite artifact
  rather than a regression, and the production build logs zero console errors.
- **`vite preview` serves `index.html` as an SPA fallback**, so a route that
  does not exist returns HTTP 200 with a page full of asset 404s. Preview cannot
  answer "does this URL exist"; the dev server and GitHub Pages both render the
  real 404 page.
- Confirm the page still renders with its data file absent or empty. A page that
  white-screens on missing data is a failure (section 12, step 5).

## Dependencies

Any dependency change goes through `npm`. CI runs `npm ci` against
`package-lock.json`.

```powershell
# edit frontend/package.json, then:
npm install
```

**Do not use `bun remove` or `bun add` here.** They re-sort every key in
`package.json`, strip its trailing newline, and write an untracked `bun.lock`
that CI ignores. `bun --cwd=<absolute path> run <script>` is fine for *running*
a script; it is only the dependency commands that are destructive.

Every new dependency names a beneficiary feature and its cost, per `CLAUDE.md`
section 8.

## See also

- [ship-a-pr.md](ship-a-pr.md) - the neutral PR lifecycle these commands serve.
- [run-the-pipeline.md](run-the-pipeline.md) - running the producer itself, which these gates do not do.
- [../reference/agent-notes.md](../reference/agent-notes.md) - environment quirks that make a command lie about its result.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - what the drift gate compares.
- [../../CLAUDE.md](../../CLAUDE.md) - sections 9, 12, and 13.
