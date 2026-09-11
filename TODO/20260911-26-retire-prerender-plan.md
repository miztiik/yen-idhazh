# 26 - Prerender: the guard retires, the prerendering does not

**Last Updated**: 2026-09-11
**Level**: 4 (a build-time handler is deleted, four documentation surfaces are corrected, and the plan carries a ruling only the owner may overturn)

**Chain**: [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) section 26 and [`20260910-25-placement-plan.md`](20260910-25-placement-plan.md) section 18 both name prerender as a gap nobody owns, and both send its removal to "the UI shell plan". **No such plan-doc exists and none is planned.** This plan takes the gap off both of them.

**The filename says `retire-prerender` and the title does not, and that is the finding rather than a slip.** The file was named before the tree was read. Having read it, the answer is that one half of the prerender surface is genuinely legacy and goes, and the other half is a decision the owner took on 2026-09-09 and 2026-09-10, wrote down next to the code, and is still true. Section 0.2 is the ruling and section 6 is what it would cost to overturn it.

Execute per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): the orchestrator dispatches one worktree-isolated worker per row; workers consult personas on ambiguity; AUTO-merge on green gates; **parallel N = 2**; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Two plan-docs and one owner instruction call prerender legacy and unowned. Read against the tree, one of those three words is right and two are not. It is **owned** - `frontend/src/routes/+page.svelte` argues for it in eighteen lines dated 2026-09-10 - and it is **not uniformly legacy**: the dated reading routes stopped prerendering on 2026-09-09 and six routes deliberately did not. What is legacy is the guard those dated routes needed, and four documentation surfaces still telling a reader that every route is prerendered. This plan deletes the first, corrects the second, prices the third, and writes the ruling where the next person will meet it |
| Hard scope - in | **`frontend/prerender-guard.js` and its wiring deleted**, with its spec, its test-group entry and its one doc paragraph in the same commit; **one measurement** of what the built site weighs with prerendering on and off, written up as this repository's first benchmark record; **four false claims corrected** - two documentation pages, one gate guide and one test docstring; **the ruling recorded** in the living doc that owns the published surface; **the gap entries in plans 23 and 25 repointed** at this plan |
| Hard scope - out | **Removing `export const prerender = true` from any route.** Section 0.2 rules against it and section 6 prices the reversal; a row may not do it and no gate here permits it. **Adding a prerendered route.** **Any change to what a document contains** - the seam, the seed, `ui.shell_seed_items` and every payload are untouched, so every page ceiling in `page_weight.ceilings_bytes` must still hold to the byte after row #2. **`docs/reference/data-growth-audit.md` and `docs/reference/test-execution-audit.md`**, which are frozen records pinned to a named revision and are correct about the tree they audited. **`docs/concepts/ui-shell.md`**, whose prerender sentence is true today and is rewritten by plan 25 row #11 |
| ESCALATE triggers | 1. **A row proposes to delete an `export const prerender = true`.** That is section 6, it is priced there, and only the owner may authorize it. 2. **The measurement in row #1 shows prerendering costs the published site more than 2 percent of its bytes** - the ruling was taken on the belief that six documents a build is a rounding error, and past that it is not. 3. **A row's build emits fewer than six `index.html` files outside `404.html`.** Something un-prerendered a route and nothing else in this plan would notice. 4. **Any page ceiling in `page_weight.ceilings_bytes` moves.** No row here changes a document, so a moved byte means a row did something it did not say it would. 5. A removal row proposes to leave a test, a config key, a fixture or a doc paragraph behind. 6. A row proposes to publish a `robots.txt` or a sitemap - neither exists today and adding one is a decision about the whole site, not a consequence of this plan |
| Chosen strategy | Measure first so the ruling can be overturned on a number rather than on prose, delete the guard whose question died, correct the four claims that are false, then write the ruling in the page a reader arrives at. Nothing a reader can see changes at any point |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

**The governing line.** **Prerendering is not one decision, it is nine route files and a handler, and they were not decided together.** Seven files declare `prerender = true` and two declare `ssr = false` instead; the split was made on 2026-09-09 with a reason written beside each half. A sentence that says "prerender is legacy" flattens a decision somebody took into a state nobody chose. Every row below names the file it is talking about.

### 0.0 What the reader loses

**From this plan as scoped: nothing, and that is checkable rather than asserted.** No row changes a route file, a payload, a component, a config value or a byte of any document. Row #2 deletes a handler that runs inside `npm run build` and produces an error message on a build that was already going to fail; a reader cannot observe it, a browser never receives it, and the four page ceilings must hold to the byte afterwards or trigger 4 above.

**What a reader would lose if section 6 were taken instead**, priced there and repeated here because the contract is where a reader-facing consequence belongs:

| Loss | Who meets it |
| --- | --- |
| `/` answers with HTTP 404 | Every reader and every crawler. `adapter-static` has one fallback, `404.html`, and GitHub Pages serves it with a 404 status. The route file says so in its own comment: "Without this line the site root emits no `index.html` at all and GitHub Pages answers `/` with the fallback, at HTTP 404" |
| The first screen arrives a round trip later | Every reader on the home page. The seed and the leading block are in the first bytes today; without prerendering they are a request away |
| The grid re-lays itself under the reader | Every reader on the home page. The two-column layout is decided by the leads in the prerendered seed; without it the aside arrives with the fetch and every card on screen re-wraps |
| A failed fetch leaves a headline and a button | Every reader whose connection drops mid-load. With the seed prerendered they keep the stories on screen and `MoreDays` under them |
| The console's first paint stops matching | Every operator. Charts are drawn server-side into the document and the window controls are disabled in it and enabled on mount; without prerendering first paint is blank and three browser specs assert against the document that would no longer exist |
| Nothing renders without JavaScript | Every reader with a script blocker, and `/archive/`'s month disclosures in particular, which are the one surface that works today with no script at all |

### 0.0a The search-engine consequence

**As scoped: none, and the reason is that there is nothing to affect.** Checked 2026-09-11 across the tracked tree:

- **No `robots.txt` is published and no sitemap is published.** `frontend/static/` holds `favicon.svg`, `manifest.webmanifest`, `service-worker-kill.json`, the fonts, the icons and the on-device encoder, and nothing else. The only `robots.txt` files in this repository are fixtures under `tests/fixtures/robots/`, which are other sites' permissions read by our fetcher.
- **No CI job reads prerendered HTML for a crawler.** One does read it for a byte ceiling: `npm run bundle-gate` measures each named route's prerendered HTML at `gzip -5` against `page_weight.ceilings_bytes`, which names two routes - `/404` at 4,400 B and `/evals/` at 6,600 B. That is a weight gate, not a crawl surface, and no row here changes a document it measures.
- **`.github/workflows/ci.yml` names prerender once, in a comment**, at line 101, heading the `validate-days` step. It describes what prerendering used to prove before the reading routes were split and asserts nothing about the output.

**If section 6 were taken, the consequence is total and it is the strongest single argument against it.** Every address would be answered by `404.html` at HTTP 404. A crawler that obeys status codes indexes nothing, and this site's one route with any external reach is `/`. That cost is already partly paid and already written down: `docs/architecture/publishing/frontend.md` records that a crawler which does not run scripts has read a dated page down to its seed and no further since 2026-09-01, and calls it a third cost paid at the same time that no reader can see. Section 6 would extend that from the dated pages to every page.

### 0.1 Standing rules, and they bind every row

**Deliver the intent, not the letter.** **A structural fix matters more than a small diff.** Where a row cannot be done correctly inside its stated file list, expand the scope and say so in the pull request - do not ship a band-aid to stay inside a list somebody wrote before the code was read. `CLAUDE.md` Rule #5 is the authority; a row's file list reads like a fence and is meant to read like a start.

**No prisoners.** Every removal takes its code, its tests, its fixtures, its config keys, its schema fields and its docs **in the same commit**. Git is the backup. Row #2 is the only removal row in this plan and its acceptance gate names all five.

**Verify every fact in your row against the tree before you act on it.** Every count, line number and quotation below is a reading of `main` at `b0e0411a` on 2026-09-11, and this tree moves several times an hour. Re-run the grep. Where the tree disagrees, **the tree wins and the row is corrected in the same pull request**, with a line saying what it was corrected from.

**A claim is corrected; a mention is left alone; a frozen record is never touched.** 23 pages under `docs/` name prerendering and this plan edits three of them. The test is what the sentence would make a reader do: a page that says "every route is prerendered" sends somebody to design against a constraint that does not exist, and a page that says "the page-weight gate measures prerendered HTML at gzip -5" is a true statement of method. A dated audit pinned to a revision is correct about that revision and is evidence, not debt.

**No row changes what any document contains.** This is what makes every gate in this plan cheap: the four ceilings in `page_weight.ceilings_bytes` must hold to the byte, and a moved byte is a defect rather than a re-pricing.

**Every measurement names its arms, its pin and its spread.** `kit.version.name` defaults to `Date.now`, so two builds of one unchanged tree disagree on about 20 percent of `build/` by filename. Row #1 pins `BUILD_VERSION` across both arms and says so, per [`../docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md).

**Row #1 may not be the first record in `docs/reference/benchmarks/`, and its own text says it is.** [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #P5 writes a different record into the same directory, the directory does not exist yet, and **both rows are unblocked today**, so either may create it. Row #1 writes *a* record. **Whichever of the two lands second drops the word "first" from its own text and names the row that created the directory.** Found 2026-09-11; neither plan named it ([`20260911-execution-order.md`](20260911-execution-order.md) section 6).

### 0.1a The gate sets, written out once so a row can name one

The commands are the literal ones from [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md), copied here on 2026-09-11 so a worker reading one row in an isolated worktree does not have to open another file. Where the two disagree, the gate guide wins and the row that noticed fixes this block.

**`GATE-PY`** - every row that changes a `.py` file. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/<the modules this row names>
```

**`GATE-WEB`** - every row that changes anything under `frontend/`. From `frontend/`:

```powershell
npm run check
npm run build
npm run bundle-gate
python -m idhazh site-weight --site-tree build
```

**`GATE-BROWSER`** - every row that changes what a reader or an operator sees, and every row that touches the build configuration. The canary day is the fixture; the real digest is not:

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run test:logic
npm run build:canary
npm run test:browser
```

**`GATE-DOCS`** - every row that writes a page under `docs/`, `README.md` or a plan-doc. From the repository root:

```powershell
.\.venv\Scripts\python.exe backend\utilities\doc_load.py
```

**Not a gate, in this plan or anywhere in this repository: `ruff format`.** It rewrites dozens of files nobody in this plan authored. Format the files you wrote, or leave formatting alone.

### 0.2 The ruling, and the four facts it rests on

**Ruled: the six prerendered routes stay. `frontend/prerender-guard.js` goes.** Authority: this plan, on the evidence below; reversal is section 6 and needs the owner.

**Fact 1 - the expensive half of prerendering was already removed, twelve days before the instruction that called it legacy.** Until 2026-09-09 the two dated reading routes were prerendered off the committed digest tree at **twelve documents per published day** - six HTML pages and six `__data.json` twins - which reached **50,598,258 bytes and 39.5 percent of the published site**, and grew with every day the pipeline wrote. Both render in the browser now. What is left reads no committed day to decide whether it exists, so it is **six documents per build and the count does not move when a day publishes**. Under `CLAUDE.md` Rule #12 the version that grew was the defect and the version that remains is not one.

**Fact 2 - the six that remain are a decision with a reason written beside it, dated one day before the instruction.** `frontend/src/routes/+page.svelte` gives three, and none of them is a special case: one document a build is not one a published day; the address a stranger meets first should carry its seed in the first bytes; and a failed fetch should leave a reader the seed rather than a headline and a button. `frontend/src/routes/+page.server.ts` gives a fourth in its own comment - without the declaration the site root emits no `index.html` and GitHub Pages answers `/` at HTTP 404. **An instruction that treats this as an unexamined leftover is arguing against a ruling it has not read.**

**Fact 3 - the guard is legacy and says so itself.** `handleUnseenRoutes` adds no check. SvelteKit already fails a build when a route marked prerenderable produced no page; the handler's own docstring says the alternative would be `'ignore'`, and `docs/architecture/publishing/frontend.md` records that what it buys is "the sentence a failing build prints". The question it was written for - is this empty digest tree a fresh clone or a missing page - died on 2026-09-09 when the two routes that could be unseen stopped being prerendered. Three browser specs elsewhere already assert the negative that matters, that a dated route has not grown `prerender = true` back: `dated-day.spec.ts`, `topic-day.spec.ts` and `payload-weight.spec.ts`.

**Fact 4 - four surfaces still tell a reader something false, and one of them is a gate guide.** They are named in rows #3 and #4. This is the real cost of leaving prerender unowned: not the six documents, but that the last two plan-docs to touch the subject both inherited "every route is prerendered" from a page nobody corrected.

**What this ruling is not.** It is not a finding that prerendering is good, and it does not defend the seven declarations individually - row #1 measures them as one arm, and section 6 is what a worker executes the day the owner says so.

### 0.3 The inventory this plan is priced against

Read 2026-09-11 from `main` at `b0e0411a`, in an isolated worktree. Every figure names what it was read from.

| Figure | Value | Read from |
| --- | --- | --- |
| Files declaring `export const prerender = true` | **7**, over **6** routes - `/`, `/archive/`, `/evals/`, `/console/`, `/console/machine/`, `/console/model/`. The console's layout and its three pages each declare it | `git grep -n 'export const prerender' -- frontend/src` |
| Routes that do not prerender | **2** - `/[date]/` and `/[date]/[vertical]/`, both `export const ssr = false` and neither declaring `prerender` | `git grep -n 'export const ssr' -- frontend/src` |
| Documents a published day adds | **0**. Twelve until 2026-09-09 | `frontend/src/routes/[date]/+page.ts`, `docs/architecture/publishing/frontend.md` |
| What the dated routes cost when they were prerendered | **50,598,258 bytes, 39.5 percent of the published site**, measured 2026-08-27 over six committed days and 2,237 items | `docs/architecture/publishing/retention.md` |
| The guard | **1 file, 1 export, 36 lines**; wired at `frontend/svelte.config.js:7` and `:84` | `frontend/prerender-guard.js` |
| Its spec | **5 tests**, in the `publishing` group, driving the real handler off the real config | `frontend/tests/prerender-guard.spec.ts`, `frontend/scripts/test-groups.ts:30` |
| Files naming prerender, repository-wide | **133** | `git grep -iln prerender` |
| Pages under `docs/` naming it | **23** - the figure this plan's brief carried, and it is correct | `git grep -iln prerender -- docs/` |
| Plan-docs under `TODO/` naming it | **10** | `git grep -iln prerender -- TODO/` |
| Browser specs naming it | **34** | `git grep -iln prerender -- frontend/tests` |
| Files under `frontend/src` naming it | **47** | `git grep -iln prerender -- frontend/src` |
| Mentions in `.github/workflows/ci.yml` | **1**, a comment at line 101 about what prerendering used to prove. The brief's claim, and it is correct | `git grep -in prerender -- .github/workflows/ci.yml` |
| CI gate reading prerendered HTML | **`npm run bundle-gate`**, `ci.yml:214` | `frontend/scripts/bundle-gate.mjs:110`, `:217`, `:393` |
| Page ceilings it holds | **2 routes** - `/404` at 4,400 B and `/evals/` at 6,600 B, `gzip -5` | `config/idhazh.json`, `page_weight.ceilings_bytes` |
| `robots.txt` published | **none**. Sitemap: **none** | `git ls-files -- frontend/static` |
| Anything asserting prerender output is byte-identical | **nothing**. Two docs record byte-identical build pairs and both pinned `BUILD_VERSION` to get them; unpinned, two builds of one unchanged tree disagree on about **20 percent of `build/` by filename** | `docs/architecture/publishing/layout.md`, `docs/architecture/publishing/retention.md`, `docs/reference/agent-notes/gates-and-builds.md` |
| Records under `docs/reference/benchmarks/` | **0**. Row #1 writes the first one | `git ls-files -- docs/reference/benchmarks` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | What prerendering actually weighs, both arms | - | A | PENDING | - | - | - |
| 2 | The guard retires, and nothing a reader sees moves | - | A | PENDING | - | - | - |
| 3 | The three surfaces that say every route is prerendered | - | B | PENDING | - | - | - |
| 4 | The ruling, written where the next person arrives | 1, 2 | B | PENDING | - | - | - |

**What a parallel group means, stated so a worker can check it.** **Within one group, no two rows may write the same file.** A glob counts as every file it covers, so there are no globs in this plan - every row's `Files touched` list names files, and where a directory is named the row says what it creates in it and nothing else in the plan writes there.

**Four rows, two groups, no singletons.** The plan is small because three of the four candidate rows a brief would expect are refused rather than deferred: removing a `prerender = true` is section 6, a sweep of all 23 documentation pages is refused by the claim-against-mention rule in section 0.1, and editing the two frozen audits is refused by section 0's scope. **Nothing here is invented to fill a document.**

### The file sets, which are what prove it

Derived from the rows' own `Files touched` lists on 2026-09-11. **It is derived rather than authoritative**: a worker checks a group by diffing the two rows' lists in the sections below, never by trusting this table ([`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md)).

| Group | Rows | What the first row writes | What the second row writes | Where they come closest |
| --- | --- | --- | --- | --- |
| A | 1, 2 | `docs/reference/benchmarks/2026-09-11-prerender-on-and-off.md`, `docs/reference/measurements-site.md` | `frontend/prerender-guard.js` (deleted), `frontend/svelte.config.js`, `frontend/tests/prerender-guard.spec.ts` (deleted), `frontend/scripts/test-groups.ts`, `docs/architecture/publishing/frontend.md` | Both write under `docs/`. Row #1 writes two files under `docs/reference/`, row #2 writes one under `docs/architecture/publishing/`. **No shared page, and no shared directory** |
| B | 3, 4 | `README.md`, `docs/architecture/overview.md`, `docs/how-to/run-the-gates.md`, `backend/tests/test_workflows.py` | `docs/architecture/publishing/frontend.md` | Nothing. Row #3 is the three surfaces outside the living doc plus one test docstring; row #4 is the living doc and only it |

**One file is written by two rows, and they are in different groups for exactly that reason.** `docs/architecture/publishing/frontend.md` is opened by row #2, which must delete the paragraph describing the file it deletes in the same commit, and by row #4, which writes the ruling and corrects a stale table row. Group A completes before group B dispatches, so they never hold it at once. **Merging them was rejected**: row #4 waits on row #1's measurement and the guard deletion must not.

---

## 2. Row #1 - What prerendering actually weighs, both arms

### Scope

Build the site twice from one tree - once as it stands, once with the seven `prerender = true` declarations removed - and write up the difference as this repository's first record under `docs/reference/benchmarks/`. **The second arm is a throwaway measurement branch that is never merged and never pushed**; its only product is a number.

**The measurement, named exactly** ([`../CLAUDE.md`](../CLAUDE.md) Rule #10):

| What | How |
| --- | --- |
| The pin | `BUILD_VERSION` set to one literal string across both arms, because `kit.version.name` defaults to `Date.now` and two unpinned builds of one tree disagree on about 20 percent of `build/` by filename |
| Arm A | `main` as it stands. `npm run build` |
| Arm B | The same tree with the seven `export const prerender = true` lines deleted and nothing else changed. `npm run build` |
| Document count | `(Get-ChildItem frontend/build -Recurse -Filter index.html).Count`, and the same for `__data.json` |
| Site total | `python -m idhazh site-weight --site-tree build` on each arm - the number the 1 GB Pages cap is measured against |
| Page ceilings | `npm run bundle-gate` on each arm, capturing the `/404` and `/evals/` figures it prints at `gzip -5` |
| First-byte content | On arm B, whether `frontend/build/index.html` exists at all. **This is the load-bearing observation**, not a byte count: `adapter-static` has one fallback and the route comment predicts there is no root document on that arm |
| Spread | Three builds per arm at the same pin, reporting the range. A build is deterministic at a pinned version, so a non-zero spread is itself the finding |

### Files touched

- `docs/reference/benchmarks/2026-09-11-prerender-on-and-off.md` - new, and the first file in that directory.
- `docs/reference/measurements-site.md` - one line and a link to the record, per `CLAUDE.md` section 5: the log carries the figure now in force and links to the record rather than absorbing it.

### Acceptance gates

```powershell
.\.venv\Scripts\python.exe backend\utilities\doc_load.py
git status --porcelain frontend/src
```

`GATE-DOCS`, plus: **`git status --porcelain frontend/src` prints nothing.** Arm B is a scratch edit and a single tracked line surviving it fails this row. The record itself must name the hardware, the date, both arms, the pin and the spread, or it is an estimate.

### Oracle

**The fixture is the tree at the commit the row runs on, and it is named in the record.** There is no smaller one: the quantity under measurement is what the whole site weighs, and a canary day cannot answer it. This is `CLAUDE.md` Rule #12's escape hatch used deliberately - the read is over a growing collection, it happens once, by hand, off the daily path, and its cost is written down here rather than discovered later.

**The oracle for the row's own correctness is the ceiling file.** `npm run bundle-gate` on arm A must print `/404` and `/evals/` inside the 4,400 B and 6,600 B written in `config/idhazh.json`. If it does not, the worktree is not clean and no number from it is usable.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Both arms, even though the ruling is already made.** A ruling defended only in prose can only be argued with; a ruling with a number beside it can be overturned by a better number. Section 6 is executable the day the owner wants it, and this is the row that tells them what they would be buying | `CLAUDE.md` Rule #10 |
| 2 | **Arm B is never merged and never pushed.** It exists for one afternoon in one worktree. The plan's hard scope forbids removing a declaration, and a branch that did it would be one merge away from doing it by accident | This plan, section 0 |
| 3 | **The record goes under `docs/reference/benchmarks/` and the instrument log gets one line.** A run is a fact about a day and the figure it produces is in force only until the next run; appending to the log instead would leave two readings of one quantity in date order, where only the ordering says which governs | `CLAUDE.md` section 5 |

### Rejected alternatives

| Rejected | Why |
| --- | --- |
| Estimate it from the six documents' current sizes | It answers the wrong question. The interesting number is not what the six weigh, it is whether arm B produces a root document at all - and an estimate cannot see a missing file |
| Measure only arm A | Half a measurement is a description. The decision this priced is a comparison |
| Leave the measurement to whoever executes section 6 | Then the number arrives after the decision, which is the failure `CLAUDE.md` Rule #10 exists to stop |

### What this row does not do

It changes no route file, deletes no declaration, and commits nothing under `frontend/`. It does not measure decode time, hydration cost or anything a reader experiences - it measures bytes and file counts, which is what the 1 GB cap and the page ceilings are written in.

---

## 3. Row #2 - The guard retires, and nothing a reader sees moves

### Scope

Delete `frontend/prerender-guard.js`, its import and its wiring, its spec, its test-group entry and the paragraph in the living doc that describes it. **`prerender: { handleHttpError: 'warn' }` stays** - only `handleUnseenRoutes` goes, and SvelteKit's default for it is to fail, which is the behaviour we keep.

**What is lost, stated rather than implied.** A build that fails on an unseen prerenderable route prints SvelteKit's message instead of ours. Ours names every unseen route and says "Check the route file, its page options, and the links that reach it." That sentence is the whole value of the handler and it is what this row spends. It is worth spending because the condition can no longer arise innocently: the two routes that could be unseen stopped being prerendered on 2026-09-09, and the three specs that guard against them coming back live elsewhere.

### Files touched

- `frontend/prerender-guard.js` - **deleted**.
- `frontend/svelte.config.js` - delete the import at line 7, the comment at line 83 that points at the deleted file, and `handleUnseenRoutes` from the object at line 84.
- `frontend/tests/prerender-guard.spec.ts` - **deleted**, all five tests.
- `frontend/scripts/test-groups.ts` - remove `'prerender-guard'` from the `publishing` group at line 30.
- `docs/architecture/publishing/frontend.md` - delete the two sentences at line 36 describing the guard and the `'ignore'` alternative. The paragraph's first sentence, which says the six prerendered routes read no committed day, is true and stays.

### Acceptance gates

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run check
npm run build:canary
npm run bundle-gate
npm run test:logic
npm run test:browser
```

**The build is `npm run build:canary`, and the oracle below is why.** An earlier draft of this block ran `npm run build` while the oracle named the canary build, so the row had two different builds in it and neither said which one the gates were read from. The canary day is fixed in size and carries a day the archive has never produced, which is what `CLAUDE.md` Rule #12 asks for; the real digest tree grows every four hours.

`GATE-WEB` and `GATE-BROWSER`, plus all four of:

1. **No file under `frontend/` and no page under `docs/` names `handleUnseenRoutes` or imports `prerender-guard.js`.** That is a gate on the behaviour - the guard is gone from the code and from the living documentation - and it is what `git grep -l -e 'prerender-guard' -e 'handleUnseenRoutes' -- frontend docs` proves. **`TODO/` is out of scope and so are the two dated audits.** A plan-doc records a reading of its own day, and five of the twelve files that name the guard today are plan-docs including this one, which no row of this plan edits; `docs/reference/data-growth-audit.md` and `docs/reference/test-execution-audit.md` are pinned to a named revision and are correct about it. **An earlier draft of this gate asked for the name to appear nowhere outside three exempted files, and it could not pass**: the guard is named in twelve files, this row deletes two and edits three, and four of the remaining seven are plan-docs the row never opens.
2. **`npm run build:canary` still emits six `index.html` files outside `404.html`.** Deleting a handler must not un-prerender a route, and nothing else in the suite would notice if it did.
3. **`npm run bundle-gate` prints `/404` and `/evals/` at the same byte counts as before the change.** No document content moved, so a moved byte is a defect. Capture the before figures first.
4. **The `publishing` browser group still runs, with one fewer spec.** A removed name that breaks the group selector fails silently and takes the other ten specs with it.

### Oracle

**`frontend/scripts/test-groups.ts` is driven from its own fixture, not from the file system.** `groupForSpec('prerender-guard')` must return `undefined` after this row and `groupForSpec('payload-weight')` must still return `'publishing'`. Both are pure string lookups over a literal in the module, so the check needs no build and no browser.

**The build oracle is the canary day** (`backend/utilities/build_canary_day.py`, then `npm run build:canary`), which is fixed in size and carries a day the archive has never produced. The committed digest tree is not the oracle here and `CLAUDE.md` Rule #12 is why - the question is whether six routes still build, not what is in them.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The handler goes and the failure stays.** SvelteKit's default for `handleUnseenRoutes` is to fail. We are deleting a message, not a check, and a row that deleted the check would be doing what `'ignore'` does - which the guard's own docstring already refuses | `frontend/prerender-guard.js` docstring; SvelteKit's default |
| 2 | **`handleHttpError: 'warn'` is untouched.** It is a different knob about a different failure, it is not legacy, and nothing in this plan examined it | This plan, section 0 |
| 3 | **The three dated records keep their references.** `data-growth-audit.md` is pinned to `76c2d27c` and `test-execution-audit.md` to `3b425be8`; both describe a `surveyDigest` that had already been deleted before this plan was written. Editing a frozen record to match today's tree destroys the only thing it is for | `CLAUDE.md` section 5 |
| 4 | **No row replaces the sentence with a comment in `svelte.config.js`.** A comment explaining a handler that no longer exists is the debt this row is paying off | `CLAUDE.md` Rule #5 |

### Rejected alternatives

| Rejected | Why |
| --- | --- |
| Keep the handler and rewrite its docstring | The docstring is already correct and already says the question died. What is left is a file, an import, a spec and a test-group entry maintained for one error message on a build that fails either way |
| Replace it with `handleUnseenRoutes: 'ignore'` | It allows the build the guard exists to stop, and every other unseen route with it, silently. The guard's own docstring refuses this and so does this plan |
| Delete the spec and keep the file | A handler with no test and no caller is worse than either half alone. No prisoners |
| Fold this row into row #4 | Row #4 waits on a measurement and this does not. Blocking a four-file deletion on two builds buys nothing |

### What this row does not do

It removes no `export const prerender = true`, changes no route, moves no byte in any document, and edits neither frozen audit. It does not touch `docs/how-to/run-the-gates.md` - the false sentence there is about routes, not about the guard, and belongs to row #3.

---

## 4. Row #3 - The three surfaces that say every route is prerendered

### Scope

Correct four sentences on four files. Each is false against the tree, and each is false in the same direction - it tells a reader that prerendering covers routes it stopped covering on 2026-09-09.

| Where | What it says today | What is wrong |
| --- | --- | --- |
| `README.md:54` | A diagram node reading `Prerendered pages` over `digest, archive, scores` | The digest's reading pages are not prerendered. This is the first diagram a stranger sees |
| `docs/architecture/overview.md:36` | `prerender at build time` feeding `static pages` over `digest, archive, scores` | The same claim one tier down |
| `docs/how-to/run-the-gates.md:362` | "every route is prerendered, so a route that cannot render fails the build rather than the page" | False for the two dated routes, whose failure to render would not fail the build. The very next sentence already qualifies the claim for stories and not for routes |
| `backend/tests/test_workflows.py:1845` | "`npm run build` prerenders every route, so a route that cannot render fails here instead of in a reader's browser" | The same sentence in a docstring, defending a real ordering requirement with a false reason |

**`docs/how-to/run-the-gates.md:831` is examined and left alone**, and the reason is the rule in section 0.1. It reads "Its own docstring said so: every route is prerendered, so first-load JavaScript is hydration cost" - reported speech inside a rejected-alternatives block explaining why a gate was deleted. It quotes a false claim rather than making one. A worker who disagrees after reading the surrounding paragraph may correct the tense and say so in the pull request.

**`run-the-gates.md` names prerender at five lines, not two, and the other three are true.** `git grep -in prerender -- docs/how-to/run-the-gates.md` returns 362, 421, 831, 862 and 894 (re-measured 2026-09-11). Line 421 describes what `page_weight.ceilings_bytes` measures, 862 prices a rejected alternative against a prerendered page, and 894 says the gate covers every prerendered document including the three console routes. **All three state a method and none of them claims every route is prerendered**, so this row reads them and leaves them, and its pull request says it did.

### Files touched

- `README.md` - the one diagram node.
- `docs/architecture/overview.md` - the one diagram node.
- `docs/how-to/run-the-gates.md` - the one sentence at line 362. The paragraph's remaining sentences about `validate-days` are correct and stay.
- `backend/tests/test_workflows.py` - the one docstring sentence. **The assertions do not change**, and the ordering requirement the docstring defends - build before commit, weight gate after - is correct and is re-justified rather than removed.

### Acceptance gates

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/test_workflows.py
.\.venv\Scripts\python.exe backend\utilities\doc_load.py
```

`GATE-PY` and `GATE-DOCS`, plus: **`git diff --stat backend/tests/test_workflows.py` shows a docstring change and no assertion change**, and the test still passes for the reason it was written - two severities, one of which may cost a reader the day.

### Oracle

**Driven from the workflow fixtures the test already loads**, never from a build. `test_the_build_gates_the_publish_and_the_weight_gate_runs_after_it` is parametrised over `PUBLISHING_SITE_JOBS` and reads the workflow YAML; it asserts step order and nothing about prerendering. The docstring is the only false thing in it, so the oracle is that the parametrised case still passes unchanged.

**For the three documentation files there is no executable oracle and the row says so plainly.** The check is a reader's: the sentence names which routes, and a person who knows only the sentence would not go looking for a prerendered dated page. `doc_load.py` catches a broken link and a malformed page, not a false claim.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Four sentences, not 23 pages.** 23 pages under `docs/` name prerendering and most of them state a true method or a dated measurement. A sweep would rewrite correct prose and bury the four corrections that matter | This plan, section 0.1 |
| 2 | **The two diagrams are corrected rather than deleted.** They are the only picture of the read-time half a stranger gets. A node saying what is actually prerendered costs the same pixels as one that is wrong | Jony; `CLAUDE.md` section 0b |
| 3 | **The test docstring is corrected in place and the assertions are untouched.** The requirement it defends is real; only its reason had rotted. Deleting the docstring would take the requirement's only explanation with it | `CLAUDE.md` section 13 |
| 4 | **The reported-speech sentence at `run-the-gates.md:831` is left, and the judgement is recorded rather than hidden.** A rejected-alternatives block that quotes a false docstring is evidence about why a gate was deleted | This plan, section 0.1 |

### Rejected alternatives

| Rejected | Why |
| --- | --- |
| Sweep all 23 pages | It replaces four defects with 23 diffs, and the pages that merely state a measurement method are correct. A large diff also hides the four sentences somebody needed to read |
| Delete the diagram nodes | The read-time half of the picture then has one box, and a reader learns less than they did from the wrong one |
| Add a `Last Updated` sweep across every page that names prerendering | It changes 23 date stamps and tells a reader every one of those pages was reviewed, which would be false |

### What this row does not do

It touches no route file, no `svelte.config.js`, no living doc under `docs/architecture/publishing/` - that is row #4 - and neither frozen audit. It corrects **no plan-doc**, including `TODO/20260910-25-placement-plan.md:406`, whose decision says "every page here is prerendered". A plan-doc records a reading of the day it was written and is corrected by the plan that owns it, not by a passing sweep. It is named in section 8.

---

## 5. Row #4 - The ruling, written where the next person arrives

### Scope

**Extend the argument the page already makes**, with row #1's number beside it and the reversal priced, and correct the one stale row in that page's own table. **This is the row that stops the next plan inheriting "prerender is legacy" from a page nobody finished**, which is how both plan 23 and plan 25 came to say it.

**The page is not silent on this and an earlier draft of this row read it as though it were.** `docs/architecture/publishing/frontend.md:48` already carries three of section 0.2's four reasons, in its own words: "It stays prerendered, because one document a build is not one a published day and it costs the site nothing that grows. Its seed and its leading block ship in the first bytes rather than a request away, because it is the address a stranger meets first. And when its fetch fails the reader still has the seed with `MoreDays` under it." **So this row extends an argument rather than writing a ruling** - and the difference matters, because a row that writes a ruling over a page that already argues it produces two statements of one decision and the second reader has to work out which governs.

What lands in `docs/architecture/publishing/frontend.md`:

1. **The argument at line 48 is extended into a `## Design rationale` entry**, keeping its three sentences, adding section 0.2's fourth reason and **row #1's measurement**, and naming the decision as a decision rather than as three things that "make `/` different". `CLAUDE.md` section 4 puts a decision in the living doc it impacts and nowhere else.
2. **A `## Rejected alternatives` row for turning prerendering off**, carrying section 6's price - HTTP 404 on every address, no first-screen content, the grid re-wrap, the console's blank first paint, and nothing rendering without a script.
3. **The stale table row corrected.** Line 68 reads "Prerendered HTML on `/`, with the whole day in it". `/` has carried a seed and fetched the rest since 2026-09-10, and the same page argues for that change 22 lines above the table that contradicts it.

### Files touched

- `docs/architecture/publishing/frontend.md` - and only this file. Row #2 has already removed the guard paragraph from it by the time this row dispatches.

### Acceptance gates

```powershell
.\.venv\Scripts\python.exe backend\utilities\doc_load.py
```

`GATE-DOCS`, plus all three of:

1. **The page states a route count and it is `6`**, matching `git grep -c 'export const prerender = true' -- frontend/src` at `7` over six routes - the console layout and its page both declare it, which is why the two numbers differ and why the page says so.
2. **Every figure the rationale quotes carries its hardware, its date and its spread**, or cites row #1's record by name.
3. **`git grep -n 'with the whole day in it' -- docs/` returns nothing.**

### Oracle

**The oracle is the page's own contradiction, and it is checkable.** Before this row, `frontend.md` says at line 46 that `/` carries a seed and fetches the rest, and at line 68 that `/` ships the whole day. Both cannot be true. After it, one statement of what `/` ships survives, and `git grep -c 'the whole day in it' -- docs/architecture/publishing/frontend.md` returns 0.

There is no fixture, because the artefact is prose. What keeps the row honest is that every number in it is either quoted from row #1's record or already carries a date in the page.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The ruling goes in `frontend.md`, not in a decision record and not in this plan.** There is no `docs/architecture/decisions/` directory in this repository and a plan-doc is non-authoritative working material. A ruling that lives only in `TODO/` is the failure this plan is repairing | `CLAUDE.md` section 5 |
| 2 | **The rejected alternative is written out in full even though nobody asked for it.** The next person to be told prerender is legacy needs the counter-argument in the page, priced, or they will re-propose it - which is exactly what happened twice in two days | `CLAUDE.md` section 5 |
| 3 | **The row depends on #1 and #2 and waits for both.** It quotes row #1's number and it edits a paragraph row #2 has already shortened. Dispatching it early produces a merge conflict in a page that is 1,000 lines long | `../docs/how-to/execute-a-plan.md` |
| 4 | **The stale table row is corrected here rather than in row #3.** It is in the living doc, and one row owning one file is what keeps the group table provable | This plan, section 1 |

### Rejected alternatives

| Rejected | Why |
| --- | --- |
| Put the ruling in this plan and link to it | `TODO/` is a cache of `docs/`, and a plan-doc is deleted or archived when its rows land. The ruling would go with it |
| Write a new page, `docs/concepts/prerendering.md` | It answers no question `frontend.md` does not already own, and a reader arriving at `frontend.md` would meet the old claim and never find the new page. `CLAUDE.md` section 5 merges a page nobody arrives at |
| Record it in `CLAUDE.md` | It is not a rule. It is a design decision about one subsystem, and section 4 says where those go |

### What this row does not do

It removes no declaration, changes no build, and edits no other page. It does not update `docs/concepts/ui-shell.md`, whose sentence about three prerendered console routes is true today and is rewritten by plan 25 row #11 when the strip takes five tabs.

---

## 6. What retiring prerendering would take, and why this plan is not doing it

**Written out in full because a rejection with no price is an opinion.** If the owner rules that the six routes go after reading section 0.2 and row #1's measurement, this is the work, and it converts into rows with no further research.

| Step | What it touches |
| --- | --- |
| Delete the seven declarations | `frontend/src/routes/+page.server.ts`, `archive/+page.server.ts`, `evals/+page.ts`, `console/+layout.ts`, `console/+page.server.ts`, `console/machine/+page.server.ts`, `console/model/+page.server.ts` |
| Answer the fallback problem | `adapter-static` has one fallback and GitHub Pages serves it at HTTP 404. Either the site accepts a 404 status on every address, or something publishes a copy of `404.html` at each address - which is prerendering with extra steps |
| Re-home five server loads | The three console pages and `/`, `/archive/` run universal or server loads that SvelteKit executes at build time today. Each becomes a runtime fetch, with a loading state, a request budget and an error class - the three things `frontend.md` records prerendering as deleting, two of which came back on 2026-09-01 and had to be solved again |
| Re-price two page ceilings | `page_weight.ceilings_bytes` measures prerendered HTML. With nothing prerendered, `/evals/` has no document to weigh and the gate holds one route |
| Rewrite or delete parts of 34 browser specs | Several assert against the prerendered document by name - `console-published.spec.ts` and `console-readout.spec.ts` check that a figure is in it, `console-window.spec.ts` checks a control is disabled in it, `console-machine-page.spec.ts` checks the prerendered page prices at the configured rate, `charts.spec.ts` has a describe block for the prerendered chart, and `footer-facts.spec.ts` reads it as raw text |
| Re-draw the console's charts in the browser | They are server-drawn SVG at a fixed `chart.width_px` because a prerendered chart has no element to measure. Moving them to the client re-opens a decision `console-charts.md` settled and costs a drawing library |
| Take the reader losses in section 0.0 | All six of them |
| Take the crawler loss in section 0.0a | Every address answers 404 |

**Why this plan refuses it.** The cost is on the left and the benefit is six documents per build that grow with nothing. Under `CLAUDE.md` Rule #12 the version of prerendering that grew with the archive was the defect, and it was removed on 2026-09-09 - 39.5 percent of the published site, gone, with the reason written down. What remains costs the site a constant and buys a first screen, a status code and a page that works without a script. **A design is changed by a measurement that contradicts it** (Rule #10), and no measurement contradicts this one. The instruction that called it legacy was reasoning from the state before 2026-09-09.

---

## 7. The docs each row writes

| Row | Page | What changes |
| --- | --- | --- |
| 1 | `docs/reference/benchmarks/2026-09-11-prerender-on-and-off.md` | New, and the first record in that directory |
| 1 | [`../docs/reference/measurements-site.md`](../docs/reference/measurements-site.md) | One line and a link to the record |
| 2 | [`../docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) | Two sentences deleted with the file they describe |
| 3 | [`../README.md`](../README.md) | One diagram node |
| 3 | [`../docs/architecture/overview.md`](../docs/architecture/overview.md) | One diagram node |
| 3 | [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) | One sentence |
| 4 | [`../docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) | A design rationale, a rejected alternative, one corrected table row |

---

## 8. Open gaps nobody owns

Named here so they are not mistaken for work this plan is doing.

| Gap | What it is | Why it is not a row here |
| --- | --- | --- |
| `TODO/20260910-25-placement-plan.md` row #6 decision 5 | A decision reading "every page here is prerendered", which is false for the two dated routes | **Corrected on 2026-09-11 by the plan that owns it**, in the same pull request that fixed this line. It is named here because a plan-doc records a reading of the day it was written, and correcting another plan's decision text from a passing sweep is how a decision loses its author - so the correction was made in plan 25 and this row records that it was |
| `docs/how-to/run-the-gates.md:831` | Reported speech quoting a deleted gate's false docstring | Row #3 examined it and left it, with the reason. A worker who disagrees may correct the tense and say so |
| Whether `/evals/` earns a prerendered document | It is one of the six and nobody has asked what it is for since the dashboard was built. Its ceiling is 6,600 B, the smallest on the site | This plan rules on prerendering as one decision. Whether a single route deserves its document is a question about that route |
| A published `robots.txt` or sitemap | Neither exists. The site has no crawl instructions of any kind | It is a decision about the whole site and nothing in this plan creates a need for one. Section 0's ESCALATE trigger 6 keeps a row from adding one quietly |
| `handleHttpError: 'warn'` | The other prerender knob in `svelte.config.js`. Nothing in this plan examined what it currently swallows | Row #2 leaves it untouched on purpose. It is a different failure and deserves its own reading |

---

## See also

- [`20260911-handover.md`](20260911-handover.md) - how to pick this queue up with no context: the queue reader, the reading order, and the standing traps.
- [`20260911-execution-order.md`](20260911-execution-order.md) - the schedule across the five open plans. **All four rows here are unblocked today and row #2 collides with nothing anywhere in the set**, which makes this the cheapest plan to run and the one that unsticks two other plans' open gaps.
- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - its section 26 named prerender as a gap and sent it to a plan that does not exist; this plan takes it, and its row #15 is the console tab the owner's 2026-09-11 ruling re-addressed to `/console/judgement/`. **Its row #P5 also writes into `docs/reference/benchmarks/`**, which row #1 here says it creates - section 0.1.
- [`20260910-25-placement-plan.md`](20260910-25-placement-plan.md) - its section 0.1 and section 18 carry the same gap and the same 23-page count, and its row #12 builds `/console/judgement/`.
- [`20260911-classification-research-record.md`](20260911-classification-research-record.md) - the research record whose 2026-09-11 reading of `frontend/prerender-guard.js` and `frontend/svelte.config.js` is where both plans' prerender paragraphs came from.
- [`../docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the living doc that owns the six routes, the 2026-09-09 split and the 2026-09-10 seam, and the page row #4 writes the ruling into.
- [`../docs/concepts/ui-shell.md`](../docs/concepts/ui-shell.md) - the four surfaces the site publishes, and the page "the UI shell plan" was probably a memory of.
- [`../docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md) - why `BUILD_VERSION` is pinned across both of row #1's arms, and what an unpinned pair costs.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - what a read over a growing collection must declare, which row #1's measurement does.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and where the no-two-rows-one-file rule comes from.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - the shape every row above is written in.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every gate set in section 0.1a.
