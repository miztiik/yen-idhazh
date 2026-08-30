# Run the Gates

**Last Updated**: 2026-08-30

Set up a machine, then run every check `CLAUDE.md` section 9 asks for before a
merge. This page owns the project's actual gate commands; the neutral PR
lifecycle that calls for them is
[ship-a-pr.md](ship-a-pr.md).

Counts and file numbers below were taken on 2026-08-24 and move as the repo
grows. Treat them as a "did the command do roughly what I expected" check, not
as a target.

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

### If you touched the span tree, run the suite twice

`observability.tracing_enabled` is false in the committed config, so the plain
`pytest` above is the OFF run. The ON run is the same suite against a config
with the toggle flipped:

```powershell
$c = Get-Content config/idhazh.json -Raw
$c.Replace('"tracing_enabled": false', '"tracing_enabled": true') | Set-Content config/idhazh.json -NoNewline
.\.venv\Scripts\python.exe -m pytest `
  --deselect "backend/tests/test_contracts.py::test_a_fresh_clone_measures_itself_and_the_committed_config_agrees" `
  --deselect "backend/tests/test_spans.py::test_tracing_off_writes_nothing_at_all"
$c | Set-Content config/idhazh.json -NoNewline
```

**Those two are deselected because they are assertions ABOUT the committed
file**, not about runtime behaviour: one says a fresh clone and the committed
config agree, the other says the committed default writes no trace. Flipping the
file makes both false by construction, and the same two would fail if you
flipped `evaluation_enabled` instead. Every other test must pass unchanged.

The point is the doctrine, not the coverage: a trace is evidence and the ledgers
are the record
([../concepts/telemetry.md](../concepts/telemetry.md#logs-are-not-the-record)),
so no test may read a span to decide anything, and a test whose outcome moves
between the two runs means one does.

Measured 2026-08-30 (Windows 11, Python 3.14.2, five sibling agents on the box):
1,599 passed in 534.8 s off, 1,597 passed and 2 deselected in 451.1 s on. The ON
run writes to `backend/var/traces/`, which is gitignored, so `git status` is
clean afterwards - and the restore line above is what keeps the config from
being committed flipped.

## The frontend gates

Run from `frontend/`.

```powershell
npm run check
npm run build
npm run bundle-gate
python -m idhazh site-weight --site-tree build
```

`check` is `svelte-check`. `build` is the strongest of the three: every route is
prerendered, so a contract-invalid payload fails the build rather than the page.

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

`bundle-gate` does three things. It asserts no encoder lands on the first-load
path, it compares every route's first-load JavaScript against the weight
recorded for it in `frontend/bundle-baseline.json`, and it holds every route
named in `config/idhazh.json` under the gzip ceiling set there.

**That comparison is a two-sided ratchet, not a budget.** A route that grew past
the recorded weight fails, and so does one that shrank past it - an unclaimed
saving left in the record is slack the next regression lands inside. The
tolerance is 64 bytes either way, derived in
[../reference/measurements.md](../reference/measurements.md) from the spread over
four builds of one tree. The gate prints every route on a pass, with its delta,
so the numbers are visible before anybody has a reason to look at them.

When it fails on a weight, the change is four steps and the gate has already
written most of it:

1. `npm run build`, then `npm run bundle-gate`.
2. Paste the replacement line it printed into `frontend/bundle-baseline.json`.
3. Write the `why` in one sentence naming the beneficiary feature. It is
   required, and an empty one fails the gate - so a new route fails twice before
   it passes, which is the friction doing its job.
4. Commit the code change and the baseline edit together. The reviewer's job is
   then one sentence, not a byte diff.

Nothing writes that file but a person. There is no `--update` flag and no
environment variable that skips the check, because a gate whose own tooling
updates its baseline cannot fail.

**The page ceiling is one-sided, and it bounds the document rather than the
script.** `page_weight.ceilings_bytes` in `config/idhazh.json` gives the largest
`gzip -9` size each named route's prerendered HTML may reach. A page that got
lighter needs no permission, so there is no lower bound. A route is named when
its growth has been priced: `/404` and `/evals/` move only when the source moves,
`/archive/` grows by one day link a published day, and `/console/` grows by about
60 gzipped bytes a published item. A day page and the home page weigh what the
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
noise floor. That headroom shrinks 12 to 18 bytes on every publish and expires by
design: when the gate fires on an ordinary day about a year from now, the answer
is to re-measure and re-derive the number, not to add a digit
([../reference/measurements.md](../reference/measurements.md#the-ceiling-that-holds-the-saving-and-where-its-headroom-comes-from)).

**`/console/` is capped since 2026-08-29, and its headroom is days rather than a
year.** Removing one real mature published day from every ledger it reads and
rebuilding cost 43,745, 43,704 and 36,504 gzipped bytes over 731, 724 and 621
scored items - about 60 bytes an item. So 301,580 is the heaviest of five builds
plus three days of the heaviest of those plus the 64-byte noise floor, and it is
meant to expire
([../reference/measurements.md](../reference/measurements.md#the-console-ceiling-is-a-tripwire-and-it-is-priced-in-published-days)).

**When `/console/` fires, do not raise it.** The page grows because the
compression scatter inlines a point for every row the ledger has ever held. The
answer is to window that seed and publish the older points through the telemetry
projection, in one change - a windowed seed on its own empties the plot behind
the window, which is a lie
([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md#the-console-ceiling-is-a-tripwire-and-what-to-do-when-it-fires)).

## The browser suite

The browser gate runs against the **canary day**, not the real digest, so it
does not change meaning when the pipeline publishes.

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run build:canary
npm run test:browser
```

127 tests in 11 files (2026-08-27), one of which skips itself. The failure
panels are held by a pair of tests, one for a window of a single day and one for
a window of several, so exactly one of the pair applies to whatever the fixture
holds. Twelve of them are pure-function tests over `frontend/src/lib/charts/`,
run in Node by the same runner. There is no separate frontend unit-test runner,
so a pure module proves itself here.

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
2026-08-27 by renaming `data-panel` in `FailurePanels.svelte`: the count guard
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

**Set `PREVIEW_PORT` when another checkout may be running the suite.**
`playwright.config.ts` reads it and defaults to 4173, and the whole config -
`baseURL`, the preview command and the poll URL - follows it. Two worktrees on
one port do not queue; the second adopts the first one's server and reads its
build.

```powershell
$env:PREVIEW_PORT = '4181'
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
- **A leftover `vite preview` on the preview port is adopted, not replaced.**
  `playwright.config.ts` sets `reuseExistingServer` outside CI, so a server left
  running by an earlier run serves stale bytes and most of the suite fails at
  once. The tell is that everything fails together while the pure-function tests
  still pass. Clear it, then re-run - do not start debugging the code:

  ```powershell
  Get-NetTCPConnection -LocalPort 4173 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```

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
