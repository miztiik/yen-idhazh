# How to run the pipeline

**Last Updated**: 2026-08-23

Running a digest end to end on your own machine, and what each stage is allowed
to do. Project-specific by nature: this describes *this* pipeline, not a process
that transfers between repositories.

## The three stages

Each takes a file and writes a file, which is what lets the middle one be
sharded across disposable machines and re-run cheaply. A stage that only works
as part of the whole is a stage nobody can debug.

| Stage | Does | Needs the network | Needs a model |
| --- | --- | --- | --- |
| `plan` | Reads every live feed, records what each one did, deduplicates, ranks, drops what was already published | yes | no |
| `work` | Fetches, extracts, summarizes and scores one item at a time | yes | yes |
| `assemble` | Collects whatever finished, publishes it, appends the ledger | no | no |

```
python -m idhazh plan
python -m idhazh work
python -m idhazh assemble
```

`python -m idhazh run` is the three in order.

## Before the first run

Install the package, and the faithfulness extra if you want scores:

```
python -m pip install -e ".[dev]"
python -m pip install -e ".[faithfulness]"   # transformers + torch, hundreds of MB
```

Get the runtime and the weights per
[set-up-local-inference.md](set-up-local-inference.md), then start the server:

```
backend/bin/llama-server --model backend/models/Qwen3-8B-Q4_K_M.gguf \
  --ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4 --port 8080
```

The summarize stage talks to `127.0.0.1:8080` and nothing else. There is no
hosted inference anywhere in this project ([../../CLAUDE.md](../../CLAUDE.md)
section 0a).

## Useful flags

| Flag | For |
| --- | --- |
| `--date YYYY-MM-DD` | Re-run a specific day. Defaults to today, UTC. |
| `--shard N --shards M` | Take one worker's share. Round-robin, so lengths spread evenly. |
| `--no-faithfulness` | Skip the scorer. The digest still publishes; **the ledger stays empty.** |
| `--config PATH` | Point at a different `config/` directory. |

## Where things land

| Path | What | Committed |
| --- | --- | --- |
| `backend/var/run/<date>/plan.json` | The day's work list | no - gitignored |
| `backend/var/run/<date>/items/*.json` | Per-item article, summary and eval | no - gitignored |
| `frontend/public/digest/<YYYY>/<MM>/<DD>/` | `digest.json` and `run.json` | **yes** |
| `state/scores.csv` | One row per scored item, appended forever | **yes** |
| `state/fingerprints.csv` | One row per pipeline stamp | **yes** |
| `state/seen/<YYYY-MM>.csv` | First sight of every address, so an undated article still has an age | **yes** |
| `state/published.csv` | Every address that reached a digest, so nothing runs twice | **yes** |
| `state/feed-health/<YYYY-MM>.csv` | What every feed did on every run | **yes** |

**The four ledgers under `state/` are the pipeline's whole memory.** Plan reads
them at the start of a run and appends to them before it ranks anything, so a
local run that is never committed forgets everything the moment it ends - the
second run will re-publish what the first one did. `state/` is read at build
time and never served to a reader
([../architecture/sources/freshness.md](../architecture/sources/freshness.md),
[../architecture/sources/health.md](../architecture/sources/health.md)).

**No article body is ever committed.** The extracted text lives under
`backend/var/`, which is gitignored, and is what the model reads. What ships is
the link, the title and our own summary.

## Reading a run that went wrong

Every failure is a state of the payload, not an absence of it, so the answer is
always in a file:

- An item that never reached the model has a `.article.json` with a `status`
  other than `ok` and a `failure_detail` saying why - a dead link, a robots
  refusal, a blocked address, or an extraction below the word floor.
- An item that reached the model and came back wrong has a `.summary.json` with
  `status: failed`, naming what it failed - a reply that lost its shape, a model
  that reasoned despite the flag, or a summary outside the publishable range.
- A run that published fewer items than it planned says so on the digest:
  `partial` is exactly whether anything failed.

Logs go to stderr and nowhere else. There is no log service and no runtime call
home ([../../CLAUDE.md](../../CLAUDE.md) section 1b).

## Three things that will bite

**A quiet news day is decided by the tie-break.** When no story is carried by
more than one feed every score is identical, so the ordering rule - score, then
when it appeared, then the address - is what picks the day, and
`collect.max_per_source` is what stops one prolific blog becoming the whole
vertical.

**A vertical below its feed floor plans nothing.** The floor is `min_feeds` on
the vertical in `config/taxonomy.json`. That is the floor working, not a bug: a
thin list produces a thin day, and a reader cannot tell a quiet day from a
broken one. Fix it by adding sources, not by lowering the floor.

**A feed that is resting is not read at all.** Five failed attempts in a row put
a feed to sleep, and the log says `feed resting id=...` rather than an error.
The rest ends on its own after five skips. Nothing here ever edits
`config/sources.json` - retiring a source is a person's decision
([../architecture/sources/health.md](../architecture/sources/health.md)).

## In CI

`.github/workflows/digest.yml` runs the same three stages every six hours: a
plan job that loads no weights, a matrix of worker jobs that each restore the
weights once and work a shard, and an assemble job that runs **even when a
worker failed** - a run that publishes nothing on a bad day is a run whose bad
days are invisible. Each run appends to the day's payload rather than replacing
it, so the day grows through the day
([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).

## See also

- [set-up-local-inference.md](set-up-local-inference.md) - getting the runtime and the weights.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - what each stage owns.
- [../concepts/config.md](../concepts/config.md) - the knobs these stages read.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - the cadence, the seen store, item ids, and why a day has no cap.
- [../architecture/sources/health.md](../architecture/sources/health.md) - the feed ledger and the quarantine rule.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - what fetch and extract refuse to do.
- [../concepts/evaluation.md](../concepts/evaluation.md) - what the scores mean.
