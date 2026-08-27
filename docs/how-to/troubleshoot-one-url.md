# Troubleshoot One URL Locally

**Last Updated**: 2026-08-27

Use the real network, extraction boundary and local model to inspect one article
without publishing a digest.

## Capability boundary

There is no first-class arbitrary-URL command today.

The CLI does **not** have:

- `idhazh work --url ...`;
- a fetch-only, extract-only or summarize-only command;
- a way to derive `source_id`, vertical, tier or source form from a URL;
- a way to derive the feed headline required by the article contract; or
- a separate scratch output root.

What exists:

- `work` consumes `backend/var/run/<date>/plan.json`;
- `--shard N --shards M` can select exactly one item already in that plan;
- a manually created `RunPlan` can carry one arbitrary URL **when** its live
  `source_id` and feed headline are known; and
- `work` then runs the normal fetch -> extract -> sanitize -> summarize ->
  optional score chain.

Do not invent a source id, tier, vertical, source form or title. Those values
change pipeline behaviour. If the URL is not from a live source in
`config/sources.json`, the faithful arbitrary-URL flow is missing and must be
implemented.

This is an operator procedure, not an automated test. It intentionally uses the
real network. The normal address checks, robots policy, paywall refusal,
sanitizer and model-output schema all remain active.

## What this procedure writes

It writes only gitignored diagnostics under:

```text
backend/var/run/<date>/plan.json
backend/var/run/<date>/items/<item-id>.article.json
backend/var/run/<date>/items/<item-id>.summary.json
backend/var/run/<date>/items/<item-id>.eval.json
```

The eval file exists only when faithfulness scoring is enabled and succeeds.

Do **not** run `assemble` for a scratch plan. Assemble writes the published
digest and committed ledgers. This runbook stops after `work`.

Path A assumes a plan already exists. Do not run `plan` merely to create a
scratch input unless its normal side effects are wanted: it reads every feed and
updates the seen and feed-health ledgers under `state/`.

## Prerequisites

1. Install the package:

   ```powershell
   .venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

   Install `.[faithfulness]` too if the score is part of the problem. Otherwise
   use `--no-faithfulness`.

2. Install llama.cpp and the configured summary model as described in
   [set-up-local-inference.md](set-up-local-inference.md).

3. Print the server command from current config with the program in
   [test-models-locally.md](test-models-locally.md#serve-a-model). Save it to a
   file and run `.venv\Scripts\python.exe <file>`; it is the same program CI
   runs, so a flag typed by hand here is a different server.

4. Run the printed command in a separate terminal. Do not retype or change its
   flags.

5. Confirm the server is healthy:

   ```powershell
   Invoke-WebRequest http://127.0.0.1:8080/health
   ```

On Linux, use `.venv/bin/python`, `backend/bin/llama-server` and
`LD_LIBRARY_PATH=backend/bin`.

## Path A: the URL is already in a plan

This is the supported path. It does not edit the plan.

Set the plan date and the exact URL:

```powershell
$env:DATE = "2026-08-24"
$env:TARGET_URL = "https://publisher.example/article"
```

Locate the item's zero-based index. With `shards` equal to the number of items,
that index selects exactly one item:

```powershell
@'
import sys
from pathlib import Path

from idhazh.contracts.run_plan import RunPlan
from idhazh.discover import canonicalise

date, raw_url = sys.argv[1:3]
path = Path("backend/var/run") / date / "plan.json"
plan = RunPlan.from_json(path.read_text(encoding="utf-8"))
target = canonicalise(raw_url)
matches = [
    (index, item)
    for index, item in enumerate(plan.items)
    if item.canonical_url == target or item.source_url == raw_url
]
if len(matches) != 1:
    raise SystemExit(f"expected one planned URL, found {len(matches)}")
index, item = matches[0]
print(f"item_id={item.item_id}")
print(
    f".venv\\Scripts\\python.exe -m idhazh work --date {date} "
    f"--shard {index} --shards {len(plan.items)} --no-faithfulness"
)
'@ | .venv\Scripts\python.exe - $env:DATE $env:TARGET_URL
```

Run the command it prints. Remove `--no-faithfulness` when troubleshooting the
scorer.

## Path B: arbitrary URL from a configured live source

This is a **manual workaround**, not a supported arbitrary-URL command. It
constructs the payload that `plan` would normally produce.

You must supply:

- `TARGET_URL`: the article address;
- `TARGET_TITLE`: the headline the feed supplied;
- `SOURCE_ID`: a live feed id from `config/sources.json`; and
- `DATE`: an unused local scratch date.

List live source ids when needed:

```powershell
.venv\Scripts\python.exe -c "from idhazh import config; [print(feed.id) for feed in config.load().sources.feeds]"
```

Set the inputs:

```powershell
$env:DATE = "2026-08-24"
$env:TARGET_URL = "https://publisher.example/article"
$env:TARGET_TITLE = "Headline supplied by the feed"
$env:SOURCE_ID = "configured-feed-id"
```

The scratch date must not already have a local plan. The script refuses to
overwrite one.

Create the one-item plan:

```powershell
@'
import os
from datetime import UTC, datetime
from pathlib import Path

from idhazh import assemble, config
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.run_plan import PlannedItem, RunPlan, VerticalPlan
from idhazh.discover import canonicalise, clean_title
from idhazh.rank import item_id

settings = config.load(Path("config"))
feed = next(
    (
        candidate
        for candidate in settings.sources.feeds
        if candidate.id == os.environ["SOURCE_ID"]
    ),
    None,
)
if feed is None:
    raise SystemExit("SOURCE_ID must name a live feed in config/sources.json")

title = clean_title(os.environ["TARGET_TITLE"])
if title is None:
    raise SystemExit("TARGET_TITLE must contain a usable feed headline")

source_url = os.environ["TARGET_URL"]
canonical_url = canonicalise(source_url)
url_key = derive_url_key(canonical_url)
date = os.environ["DATE"]
generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

item = PlannedItem(
    item_id=item_id(feed.vertical, url_key),
    url_key=url_key,
    source_url=source_url,
    canonical_url=canonical_url,
    source_id=feed.id,
    tier=feed.tier,
    source_form=feed.form,
    vertical=feed.vertical,
    title=title,
    rank_score=0.0,
)
plan = RunPlan(
    version=RunPlan.schema_version(),
    date=date,
    run_id=f"{date}-0",
    generated_at=generated_at,
    verticals=[
        VerticalPlan(
            id=feed.vertical,
            considered=1,
            planned=1,
            live_feeds=1,
        )
    ],
    items=[item],
)

path = Path("backend/var/run") / date / "plan.json"
if path.exists():
    raise SystemExit(f"scratch plan already exists: {path.as_posix()}")
assemble.write_atomic(path, plan.to_json())
print(f"wrote {path.as_posix()} item_id={item.item_id}")
'@ | .venv\Scripts\python.exe -
```

Run the one-item chain:

```powershell
.venv\Scripts\python.exe -m idhazh work `
  --date $env:DATE `
  --shard 0 `
  --shards 1 `
  --no-faithfulness
```

Remove `--no-faithfulness` to load HHEM and write the eval payload.

For Bash, export the same four variables and run the unchanged Python body with
`python - <<'PY' ... PY`.

## Read the result

First list the item files:

```powershell
Get-ChildItem "backend\var\run\$env:DATE\items"
```

Read the article payload before the summary. It tells you whether the network
and trust boundary succeeded:

```powershell
Get-Content "backend\var\run\$env:DATE\items\*.article.json" -Raw |
  ConvertFrom-Json |
  Select-Object item_id, status, failure_code, failure_detail,
    word_count, token_count, brief, truncated
```

Then read the summary and timings:

```powershell
Get-Content "backend\var\run\$env:DATE\items\*.summary.json" -Raw |
  ConvertFrom-Json |
  Select-Object item_id, status, failure_code, failure_detail,
    title, summary, input_tokens, output_tokens,
    fetch_ms, extract_ms, summarize_ms, duration_ms
```

Interpret them in this order:

| Evidence | Meaning |
| --- | --- |
| No article file | The worker crashed before it could persist the fetch/extract result. Read stderr. |
| `ValidationError: an ok article carries title and text` | A manual plan omitted `TARGET_TITLE`. The worker does not derive the feed headline from the page. |
| Article `status` is not `ok` | Fetch or extraction stopped the item. Read `failure_code` first, then `failure_detail`. |
| Article is `ok` with `too_short`, `not_prose` or `boilerplate` | This is a recorded shape signal. The item can still continue, usually as `brief`. |
| Article is `ok`, no summary file | The process stopped between extraction and the model result. Check server health and stderr. |
| Summary `model_unreachable` | Nothing is listening at `127.0.0.1:8080`, or the local server died. |
| Summary `context_exceeded` | The server answered HTTP 400: the prompt plus the reply budget did not fit `--ctx-size`. Shorten the source, not the server. |
| Summary `output_truncated` | The model exhausted the configured output budget before closing its JSON. |
| Summary `bad_shape` | The constrained reply or reasoning channel violated the summary contract. |
| Summary `length_out_of_range` | The reply parsed, but its word count missed the configured band. |
| No eval file | Expected with `--no-faithfulness`; otherwise inspect scorer installation and stderr. |

The fetched article text is deliberately visible in `.article.json` for local
diagnosis. It stays under gitignored `backend/var/` and must not be committed.

## Validate the whole local path

The manual path was exercised on 2026-08-24 with a real BBC URL, the live
`bbc-tech` source definition and local Qwen3-8B-Q4_K_M (retired incumbent,
historical record) on an Intel i7-1265U. One observation (`n=1`): fetch 328 ms,
extraction 78 ms, summarization 352,921 ms. These are proof that the procedure
reaches every stage, not performance baselines, and the configured summarizer
has never been timed on this path.

## Clean up

Stop the llama server, then delete only the scratch run:

```powershell
Remove-Item -Recurse -Force "backend\var\run\$env:DATE"
```

Confirm no diagnostic payload is tracked:

```powershell
git status --short
```

## What a first-class command still needs

A real arbitrary-URL feature would need a new CLI command, for example:

```text
idhazh inspect-url --url ... --source-id ... --title ...
```

That command does not exist. To add it correctly, it must:

- require or derive every `PlannedItem` field without inventing source metadata;
- use the same live fetcher, robots policy, extractor, sanitizer and model
  request as `work`;
- write only to a gitignored inspection directory;
- never append `state/`, write `frontend/public/`, or call `assemble`;
- expose stage boundaries so fetch and extraction can be inspected without a
  running model; and
- ship with contract and integration tests using captured fixtures, while the
  operator command itself remains able to use the real network.

Until that exists, Path A is supported and Path B is the explicit manual
workaround. A URL with no configured source identity cannot be run faithfully.

## See also

- [run-the-pipeline.md](run-the-pipeline.md) - the supported plan, work and assemble stages.
- [test-models-locally.md](test-models-locally.md) - install, serve and compare local models.
- [set-up-local-inference.md](set-up-local-inference.md) - install llama.cpp and GGUF weights.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - which stage owns each transformation.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - address checks, robots, sanitization and output controls.
- [../../CLAUDE.md](../../CLAUDE.md) - Rules #3, #7, #10 and #11.
