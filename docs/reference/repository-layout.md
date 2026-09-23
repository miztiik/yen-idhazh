# Repository Layout

**Last Updated**: 2026-09-22

Every top-level directory, what it holds, who writes it, and whether a reader
ever sees it. Read this before adding a directory, or when deciding where a new
file belongs.

The rule this page enforces is [`CLAUDE.md`](../../CLAUDE.md) section 3. This
page is the reference form of it, with the reasoning.

## One question decides every directory

**Who writes it, and does it have to survive a fresh checkout?**

There is no database and nothing running at read time (Guardrail #1). So anything
a later run must read has to be a committed file, and anything a reader must see
has to be a published file. Every directory below is one answer to that
question, and the four answers do not mix.

| Answer | Directory |
| --- | --- |
| A person writes it, by hand | `.claude/`, `.github/`, `config/`, `docs/`, `notebooks/`, `tests/`, `TODO/` |
| A tool generates it, and it is committed | `state/`, `frontend/public/digest/` |
| A tool generates it, and it is thrown away | `backend/var/`, `frontend/build/` |
| It is downloaded, not authored | `backend/models/`, `backend/bin/` |

## The committed map

| Path | Holds | Written by | Reaches a reader |
| --- | --- | --- | --- |
| `config/` | The tunable knobs: `idhazh.json`, `appearance.json`, `sources.json`, `taxonomy.json`, `watchlist.json`, and one whole model per file under `config/models/` | a person | only the slice the site is handed |
| `corpus/` | The rolling training window: source text as training samples, its census and its holdout. **`corpus/reference-dataset-1/` is a second collection in the same directory and a different thing entirely**: a frozen, hand-labelled set for measuring the article classifier, written once by hand and never by a run. The two must not share an article, and `build_reference_dataset.py verify` is what says so. **`corpus/reference-dataset-2/` is a third**: a collection built from a URL list supplied by hand, for a later balanced classification sample, with its own settings in `config.json` and its own `scratch/` subtree ignored by git | a run, in CI; `reference-dataset-1/` and `reference-dataset-2/` by a person | **never** |
| `backend/` | The build-time producer. Not a service, ever. `backend/idhazh/` is the package, `backend/idhazh/contracts/` the Pydantic models, `backend/idhazh/contracts/knobs/` one module per block of `config/idhazh.json`, `backend/idhazh/stages/` one module per pipeline stage, `backend/utilities/` the operator tooling, `backend/tests/` its tests | a person | no |
| `.github/workflows/` | CI, the measurement harness, the daily pipeline, and the Pages deploy | a person | no |
| `.github/scripts/` | A shell step two or more workflow jobs run | a person | no |
| `.github/agents/` | The seven persona advisors (`CLAUDE.md` section 14) | a person | no |
| `.claude/skills/` | Claude Code skill wrappers that point at `docs/`, so one procedure is not written twice | a person | no |
| `state/` | The append-only ledgers one run leaves for the next. Eight of them partition - `state/seen/`, `state/feed-health/`, `state/item-health/`, `state/published/`, `state/counterfactual-scores/`, `state/content-similarity-judge/scored-pairs/` and `state/content-similarity-judge/fitted-thresholds/` by day, `state/scores/` by month. A ledger more than one job writes is a day directory holding one file per writer, so two writers never share a path. `state/content-similarity-judge/` is a child that is a folder of ledgers rather than a ledger, so everything one judge produces is one prefix for a commit step to stage; `state/llm-council/` is the other | a run, in CI | **never** |
| `state/pipeline-tests*/` | A trial run's own copy of the tree above. The bench and `Model validation` write `state/pipeline-tests/`; each pipeline-test case writes `state/pipeline-tests-<case>/`. Nothing reads any of it - no published series, no gate, no console band - so `retention.trial_state_days` empties it and the root goes with its last file. `prune-state` finds these roots by subtracting the declared stores from the children of `state/`, because the knob that names one is null in production and cannot be set there | a dispatch, in CI | **never** |
| `frontend/` | The published site, plus the digest payloads under `public/` | a person, and the pipeline under `public/` | yes |
| `tests/` | Cross-cutting fixtures: captured pages, golden summaries, injection canaries | a person | no |
| `notebooks/` | Committed notebooks a person runs off this machine, on hardware the runner does not have. Instructions only - never weights, never a token, and nothing in CI runs them (Guardrail #2) | a person | no |
| `docs/` | The canonical knowledge. Agent memory | a person | no |
| `TODO/` | Active plan-docs. Working material, never authoritative | a person | no |

## The uncommitted map

These exist on a developer machine and in CI. None is ever committed.

| Path | Why not |
| --- | --- |
| `backend/models/` | GGUF weights. 2.4 GB and 4.8 GB, against a 100 MB per-file ceiling |
| `backend/bin/` | llama.cpp binaries, ~45 MB. Downloaded, not authored |
| `backend/var/` | Run intermediates and caches. The committed record of a run is the digest plus the `state/` rows, never the workings |
| `backend/var/evidence/` | Inside `backend/var/`, and named here because a person has to find it. One file per scored item, holding the article text and the summary a human labeller must read. Article bodies are not ours to republish, so this one is uncommittable on principle rather than on size |
| `backend/var/council/` | Inside `backend/var/`, and named here for the same reason. **Everything one judging night carries between its jobs, and the only thing it carries**: the workflow uploads this directory and nothing else, so a file a tenant writes outside it is thrown away with the runner. One date a directory, and inside it a slot each for what was picked, what was judged, what the units measured and how each unit ended. A file is named `<date>-<tenant>-<unit>`, so eight units cannot land on one path and a file merged out of eight artifacts still says who wrote it. Nothing here is ever committed - a drawn row carries no verdict yet and the units rewrite it, while a row reaches `state/content-similarity-judge/scored-pairs/` once, already judged, and is never edited afterwards |
| `frontend/build/` | The built bundle. Pages rebuilds it from source on every deploy |
| `frontend/static/digest/` | Staged from `frontend/public/digest/` at build time. A copy is not a source |

Deleting any of them costs a re-download or a rebuild and nothing else. That is
the test for whether something belongs here.

## Where the confusing ones sit, and why

**`state/` is top-level because nothing else could hold it.** It is written by a
machine, it must survive a fresh checkout, and a reader must never see it. Each
of the other candidates fails on one of those three:

| Candidate | Fails because |
| --- | --- |
| `backend/var/` | Gitignored, so the next run would find nothing |
| `frontend/public/` | Published, so it would be served to a reader and count against the 1 GB site cap |
| `config/` | Human-edited. A machine appending to a file a person owns invites a merge conflict every run |
| `backend/` | Source. A ledger is not code, and a Python package is not a database |

**Two files under `state/` are written by a person, not a machine.**
`state/labels.csv` holds human faithfulness labels, appended one keystroke at a
time by `backend/utilities/label_queue.py`. It sits with the other ledgers
because it is read the same way - joined to `state/scores.csv` on
`output_digest`, never served, and it must survive a fresh checkout. It is the
one exception to "written by a machine", and it is deliberate: the point of the
file is that no machine wrote it. See
[../concepts/evaluation.md](../concepts/evaluation.md).

`state/content-similarity-judge/holdout-pairs.csv` is the second, and it is the same
exception for the same reason: a labeller reads two articles and marks them one
story or two, and that mark is the fixed floor the fitted merge line has to stay
above. No run writes it - an operator harvests the marks into it by hand, and
`note` says who made each one. `.gitattributes` names it `merge=text` in its own
line rather than letting it inherit: two people editing it are disagreeing about
the same rows rather than appending independent ones, and a reason worth reading
is worth writing down. See
[../how-to/label-the-similarity-holdout.md](../how-to/label-the-similarity-holdout.md).

**The text those labels judge lives under `backend/var/evidence/`, not under
`state/`.** A label is our own words about an item and is ours to commit. The
article it judges is somebody else's and is not, so the two are stored apart
even though one is useless without the other. The run writes the evidence, the
work job uploads it as an artifact with a deadline, and a fresh checkout has
none of it - which is the intended cost. See
[../how-to/label-the-faithfulness-queue.md](../how-to/label-the-faithfulness-queue.md).

**`corpus/` holds that same article text, committed, and it is the one place in
this repository that does.** That is an owner decision taken 2026-08-28: what
the rule protects is the published surface, and nothing renders the corpus,
links to it, or serves it. Two
consequences follow and neither is hidden. This repository is public, so those
bytes are readable by anyone. And because git history is append-only, bounding
the repository means rewriting history - which is what
`.github/workflows/prune.yml` does, and why section 8 carries exactly one
force-push exception. See
[../how-to/fine-tune-a-model.md](../how-to/fine-tune-a-model.md).

It is not under `state/`, because `state/` is append-only ledgers whose rows are
independent and union-merge; a corpus is a fixed window that evicts, so the union
of two rolls is a file holding rows the roll already threw out. It is not under
`backend/var/`, because that is gitignored reproducible run output and a training
window has to survive a fresh checkout.

The Pages workflow uploads `frontend/build` and nothing else, so `state/` cannot
reach a reader even by accident. The console reads it at build time and bakes
the numbers into the page ([../concepts/pipeline-loop.md](../concepts/pipeline-loop.md)).

**Nothing sits between the two halves any more.** `schemas/` did until
2026-09-23: 66 generated JSON Schemas, top-level because neither half owned
them. It went with `frontend/src/contracts/`, and what crosses the boundary now
is six names copied by hand into two `frontend/src/lib/server/` modules, held in
step by three backend tests
([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)).
`frontend/src/lib/payload/types.ts` is the larger mirror, still written by hand,
and that page says what binds it.

**`frontend/public/` is committed pipeline output, not source.** The backend is
its only writer; the site only renders what is already there. That is the whole
interface between the two halves.

**`.github/scripts/` holds a step, not a tool.** A shell block that two workflow
jobs both run is a duplicate nobody can execute in a test, and the daily run has
already lost a day to one. Pulling it into a file next to the workflow that
calls it makes the behaviour testable: the test runs the script against a
scripted local git origin and reads the outcome. It is not part of the producer
package, so `backend/` stays runnable with no knowledge of CI, and `pip install`
never ships a runner detail.

## What is deliberately not a directory

- **`evals/`** - folded into `state/`. The published dashboard keeps its
 `/evals/` route, because a reader's URL is a promise and a folder name is not.
- **`docs/architecture/decisions/`** - there is no ADR directory. A decision is
 recorded in the living doc it impacts, as a `## Design rationale` or
 `## Rejected alternatives` section on that page (section 5).
- **Anything empty.** A directory is created when real code is about to land in
 it. An empty module "for later" is a section 10 anti-pattern.

## Design rationale

Splitting committed machine output (`state/`, `frontend/public/`)
from committed human input (`config/`, `docs/`, `tests/`) is the decision the
rest of this page falls out of. The alternative - one directory holding both -
means a run appends to a file a person is editing, and every run risks a
conflict on work nobody asked it to touch.

`evals/` was folded into `state/` because two top-level directories were
answering the same question: what does a run leave behind for a later reader?
One answer, one place. The `/evals/` route survived the fold because the folder
was an implementation detail and the URL was a promise to a reader.

**`backend/idhazh/stages/` exists because the router had eaten the work.**
`backend/idhazh/cli.py` held the argument parser, the verb table, and the body of
all eighteen stages: 4,946 lines and 117 top-level names in one file. Nothing in
it was wrong, and that is the point - a router grows a stage at a time, and no
one commit is the one to refuse. What it cost was real. Every row of four active
plans wrote that file, so the collision table on
[`../../TODO/20260911-execution-order.md`](../../TODO/20260911-execution-order.md)
named it the single busiest module in the project at 18 rows, and two rows that
touched nothing in common still could not run in the same wave. Split on
2026-09-13: one module a stage, `stages/common.py` for the 31 names two or more
stages share, and `cli.py` down to 762 lines - the parser, the verb table, five
routing helpers, and nothing a stage does (CLAUDE.md section 1a, "A router is
the sharpest case").

**The router imports stage modules and never the names inside them.** The split
first shipped with `cli` re-exporting 51 of those names, so 168 call sites in 20
files did not have to move. That bought a day and cost the thing the split was
for. `cli` stayed the listed home of code it does not contain, so the next
reader still looked for the work in the wrong file, and the re-export was an
import path nobody had to declare. It also made one shape of redirect silent:
`setattr(cli, "_picture_faults", ...)` rebinds the router's copy while the stage
goes on calling the shipped rule out of its own module, so a test passes against
the thing it meant to replace. The nine roots below were already exempt for
exactly that reason, which left the rule true of nine names and false of 51.

Retired on 2026-09-13, in the commit after the split. `cli.stage_work` does not
resolve, every caller and every sentence names the module that defines what it
means, and `cli.py` declares no `__all__` because it exports what it defines and
nothing else. `test_the_router_exposes_no_name_a_stage_owns` in
`backend/tests/contracts/` reads the imported router against every
module-level name the stage modules declare and fails on any it can still see.

**The nine roots the tests redirect are reached through `common`.** A stage
reads `common.PUBLIC_ROOT` as an attribute rather than importing the value, so
one `monkeypatch.setattr(common, "PUBLIC_ROOT", tmp)` reaches every reader. A
redirect left on `cli` raises instead of binding a copy no stage reads - which
is now true of every stage-owned name rather than these nine alone, so the
suite-walking guard that policed the difference is gone with the difference.

**A stage module is named for the work it does, never for the loop that runs
it.** Four of them were `judge_draw`, `judge_shard`, `judge_fold` and
`judge_fit`: one family prefix naming the single loop that happened to call
them. The prefix said which loop a stage was in and nothing about what the stage
answers, so the directory listing told a reader nothing, and a second judge
writing the same four steps could only repeat the prefix and lie or break the
pattern. Renamed on 2026-09-21 to `pick_item_pairs`, `judge_item_pairs`,
`count_verdicts` and `set_merge_line`. The test is the directory listing: read a
filename and you know what the code inside answers, whoever calls it.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Ledgers under `backend/var/` | Gitignored. The next run would start with no memory at all. |
| Ledgers under `frontend/public/` | Published to a reader, and counted against the 1 GB site cap, for data no reader wants. |
| A top-level `schemas/` of generated JSON Schemas | Deleted 2026-09-23. It held 66 files, 61 of which were read by nothing but the gate that checked they had been generated, and it put a regenerated diff in front of about one reviewer in ten. |
| Keeping `evals/` as its own top-level directory | A second answer to a question `state/` already answered. |
| Renaming the `/evals/` route when the folder was folded | A reader's bookmark is a promise. A directory name is not. |
| A shared workflow step under `backend/utilities/` | `backend/` is the producer, and a step only GitHub Actions runs is not producer code. Filing it there puts a runner detail inside the installable package and hides it from the workflow that calls it. |
| Leaving the step duplicated in both jobs | Two copies of a retry loop, neither executable by a test. The copies had already drifted in two log strings. |
| A `decisions/` directory of ADR files | A decision filed away from the thing it governs is a decision the next reader does not find. |
| Moving the stages out one at a time, as each plan row happened to touch one | The rows land over weeks and each one adds a module while the file it left keeps growing, so the collision stays and nobody can say when it ends. The whole file was mechanical to move and the suite proves it: one commit, one answer. |
| A `stages/` module per plan rather than per stage | A plan is a schedule, not a shape. The stage is the unit the router dispatches and the unit a test drives, so it is the unit the file follows. |
| Keeping a family prefix on the stage modules one loop calls | The prefix is what tied four stages to one caller, and the caller is the part most likely to change. It also hands the next loop that needs the same four steps a choice between a name that lies and a name that breaks the pattern. |

## See also

- [documentation-structure.md](documentation-structure.md) - the tiers inside `docs/` and where a new statement goes.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - what one run leaves for the next, and why nothing under `state/` is served.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - where a persisted shape is declared, and what binds the frontend's copy of one.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the shape inside `frontend/public/digest/`.
- [../how-to/run-the-pipeline.md](../how-to/run-the-pipeline.md) - which of these paths a local run touches.
- [../../CLAUDE.md](../../CLAUDE.md) - section 3 (topology), section 4 (dependency rules), Guardrail #1.
