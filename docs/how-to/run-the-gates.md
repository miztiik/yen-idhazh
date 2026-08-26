# Run the Gates

**Last Updated**: 2026-08-26

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

Four extras are declared. Install only what you need:

| Extra | Pulls | When |
| --- | --- | --- |
| `dev` | `ruff`, `mypy`, `pytest` | always - this is the gate set |
| `measure` | `feedparser`, `trafilatura` | live source sampling; hits the network |
| `bench-image` | `torch`, `diffusers` | image-model benchmarking; multi-gigabyte |

`measure` and `bench-image` are heavy and reach the network. No test imports
either one.

## The backend gates

Run all four from the repository root. Each must be clean.

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m idhazh.contracts.export
git diff --exit-code -- schemas/
```

On 2026-08-25 that is 858 tests and 88 files type-checked. The last two lines
are the contract drift gate: the export regenerates `schemas/` from the Pydantic
models, and a non-empty diff means a generated artifact was hand-edited or a
model changed without regenerating ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)).

**`ruff format` is not a gate.** `ruff format --check .` reports 14 files it
would rewrite (2026-08-24), all of them pre-existing. Running it across the repo
produces a large diff that has nothing to do with your change. Format only the
files you author, or leave formatting alone.

## The frontend gates

Run from `frontend/`.

```powershell
npm run check
npm run build
npm run bundle-gate
```

`check` is `svelte-check`. `build` is the strongest of the three: every route is
prerendered, so a contract-invalid payload fails the build rather than the page.

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
lighter needs no permission, so there is no lower bound. Only routes whose HTML
does not grow with the published data are named - `/404` and `/evals/` today. A
day page weighs what the day published, and `/archive/` and `/console/` grow the
same way, so a fixed ceiling on any of them would cap the news or fail on an
ordinary publish instead of catching a regression; those are covered by the
marker count in `frontend/tests/payload-weight.spec.ts`, which runs in the
browser suite. A route the config does not name is reported by the gate without
failing it.

When a named route is over, two failures are worth telling apart:

- **A page took on bytes it does not render.** A day payload inlined by a layout
  is how this last happened, and it cost 313,000 bytes. Remove them.
- **The page genuinely carries more.** Raise the number in `config/idhazh.json`,
  in the commit that earned the bytes, and say in the message what they buy. The
  number lives in that file alone - the `PageWeightConfig` default is empty - so
  there is no second copy to move.

**`/archive/` and `/console/` are not capped, and that is deliberate.**
`/archive/` inlines every committed day to feed the on-device search and grows
about 170 KB gzipped per published day; `/console/` grows with the ledger its
charts read. A fixed ceiling on either was a countdown, not a bound: it fired on
an ordinary publish and was raised to silence it - `/archive/` twice in one day
on 2026-08-26 - which is a gate that never actually held. Their growth belongs
to the marker count above and, for `/archive/`, to its own plan under `TODO/`
([../reference/measurements.md](../reference/measurements.md#the-prerendered-page-on-the-wire)).

## The browser suite

The browser gate runs against the **canary day**, not the real digest, so it
does not change meaning when the pipeline publishes.

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run build:canary
npm run test:browser
```

83 tests in 7 files (2026-08-25), one of which skips itself when the fixture
window holds a single day. Twelve of them are pure-function tests over
`frontend/src/lib/charts/`, run in Node by the same runner. There is no separate
frontend unit-test runner, so a pure module proves itself here.

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
