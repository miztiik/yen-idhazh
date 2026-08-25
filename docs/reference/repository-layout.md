# Repository Layout

**Last Updated**: 2026-08-25

Every top-level directory, what it holds, who writes it, and whether a reader
ever sees it. Read this before adding a directory, or when deciding where a new
file belongs.

The rule this page enforces is [`CLAUDE.md`](../../CLAUDE.md) section 3. This
page is the reference form of it, with the reasoning.

## One question decides every directory

**Who writes it, and does it have to survive a fresh checkout?**

There is no database and nothing running at read time (Rule #1). So anything
a later run must read has to be a committed file, and anything a reader must see
has to be a published file. Every directory below is one answer to that
question, and the four answers do not mix.

| Answer | Directory |
| --- | --- |
| A person writes it, by hand | `config/`, `docs/`, `tests/`, `TODO/` |
| A tool generates it, and it is committed | `schemas/`, `state/`, `frontend/public/digest/` |
| A tool generates it, and it is thrown away | `backend/var/`, `frontend/build/` |
| It is downloaded, not authored | `backend/models/`, `backend/bin/` |

## The committed map

| Path | Holds | Written by | Reaches a reader |
| --- | --- | --- | --- |
| `config/` | The tunable knobs: `idhazh.json`, `sources.json`, `taxonomy.json`, `watchlist.json` | a person | only the slice the site is handed |
| `schemas/` | One generated JSON Schema per contract, sixteen files | `python -m idhazh.contracts.export` | no |
| `backend/` | The build-time producer. Not a service, ever | a person | no |
| `.github/scripts/` | A shell step two or more workflow jobs run | a person | no |
| `state/` | The append-only ledgers one run leaves for the next | a run, in CI | **never** |
| `frontend/` | The published site, plus the digest payloads under `public/` | a person, and the pipeline under `public/` | yes |
| `tests/` | Cross-cutting fixtures: captured pages, golden summaries, injection canaries | a person | no |
| `docs/` | The canonical knowledge. Agent memory | a person | no |
| `TODO/` | Active plan-docs. Working material, never authoritative | a person | no |

## The uncommitted map

These exist on a developer machine and in CI. None is ever committed.

| Path | Why not |
| --- | --- |
| `backend/models/` | GGUF weights. 2.4 GB and 4.8 GB, against a 100 MB per-file ceiling |
| `backend/bin/` | llama.cpp binaries, ~45 MB. Downloaded, not authored |
| `backend/var/` | Run intermediates and caches. The committed record of a run is the digest plus the `state/` rows, never the workings |
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

**One file under `state/` is written by a person, not a machine.**
`state/labels.csv` holds human faithfulness labels, appended one keystroke at a
time by `backend/utilities/label_queue.py`. It sits with the other ledgers
because it is read the same way - joined to `state/scores.csv` on
`output_digest`, never served, and it must survive a fresh checkout. It is the
one exception to "written by a machine", and it is deliberate: the point of the
file is that no machine wrote it (`CLAUDE.md` section 0a). See
[../concepts/evaluation.md](../concepts/evaluation.md).

The Pages workflow uploads `frontend/build` and nothing else, so `state/` cannot
reach a reader even by accident. The console reads it at build time and bakes
the numbers into the page ([../concepts/pipeline-loop.md](../concepts/pipeline-loop.md)).

**`schemas/` is top-level because it is neither half's property.** It is
generated from `backend/idhazh/contracts/` and read by the frontend's payload
types. Filing it under either half would make the other half import across the
boundary that section 4 forbids. At the top, both sides read a neutral artifact
and neither owns it.

The frontend end of that arrow is still hand-written -
`frontend/src/lib/payload/types.ts` mirrors `schemas/digest-day.schema.json` by
hand, and the generator and its drift gate have not landed
([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)).
That is a known gap, not the design.

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

Splitting committed machine output (`state/`, `schemas/`, `frontend/public/`)
from committed human input (`config/`, `docs/`, `tests/`) is the decision the
rest of this page falls out of. The alternative - one directory holding both -
means a run appends to a file a person is editing, and every run risks a
conflict on work nobody asked it to touch.

`evals/` was folded into `state/` because two top-level directories were
answering the same question: what does a run leave behind for a later reader?
One answer, one place. The `/evals/` route survived the fold because the folder
was an implementation detail and the URL was a promise to a reader.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Ledgers under `backend/var/` | Gitignored. The next run would start with no memory at all. |
| Ledgers under `frontend/public/` | Published to a reader, and counted against the 1 GB site cap, for data no reader wants. |
| `schemas/` inside `backend/` | The frontend would import across the boundary section 4 draws between the halves. |
| Keeping `evals/` as its own top-level directory | A second answer to a question `state/` already answered. |
| Renaming the `/evals/` route when the folder was folded | A reader's bookmark is a promise. A directory name is not. |
| A shared workflow step under `backend/utilities/` | `backend/` is the producer, and a step only GitHub Actions runs is not producer code. Filing it there puts a runner detail inside the installable package and hides it from the workflow that calls it. |
| Leaving the step duplicated in both jobs | Two copies of a retry loop, neither executable by a test. The copies had already drifted in two log strings. |
| A `decisions/` directory of ADR files | A decision filed away from the thing it governs is a decision the next reader does not find. |

## See also

- [documentation-structure.md](documentation-structure.md) - the tiers inside `docs/` and where a new statement goes.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - what one run leaves for the next, and why nothing under `state/` is served.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - what generates `schemas/` and the drift gate over it.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the shape inside `frontend/public/digest/`.
- [../how-to/run-the-pipeline.md](../how-to/run-the-pipeline.md) - which of these paths a local run touches.
- [../../CLAUDE.md](../../CLAUDE.md) - section 3 (topology), section 4 (dependency rules), Rule #1.
