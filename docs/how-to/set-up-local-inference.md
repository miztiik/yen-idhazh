# How to set up local inference

**Last Updated**: 2026-08-20

How to get a working local model runtime on a developer machine, so `backend/` can be run end-to-end without CI. The weights and the runtime binaries are **downloaded, not committed** - `backend/models/` and `backend/bin/` are gitignored - so a fresh clone needs this once.

CI does not use this runbook. CI downloads the same artifacts into the Actions cache from the workflow.

## Why they are not committed

- The weights are multi-gigabyte. GitHub refuses any single file over 100 MB, and the quantisations this project uses are far past that.
- The binaries are platform-specific third-party builds, reproducible from an upstream release.

Both are inputs the pipeline consumes, not work this project authored, so committing them would put tens of gigabytes of somebody else's bytes in history forever to save a one-time download (Rule #8, and `CLAUDE.md` section 10 - never commit a model weight or a downloaded binary).

## What you need

| Path | What goes there | Where it comes from |
| --- | --- | --- |
| `backend/bin/` | The inference runtime binaries for your platform. | The upstream project's release page, matching the version pinned in `config/`. |
| `backend/models/` | The quantised weight files. | Hugging Face, at the model reference and quantisation pinned in `config/`. |

Both directories are created by you, are gitignored, and are safe to delete and re-fetch at any time.

## Steps

1. **Read the pinned references from `config/`.** The model reference, the quantisation and the runtime version are configuration, never hardcoded (Rule #6). Do not fetch "the latest" - fetch what is pinned, or the run will not reproduce.
2. **Download the runtime build for your platform** into `backend/bin/`. Prefer a prebuilt release over compiling from source: building the runtime costs minutes and produces the same thing as a download.
3. **Download the weight files** into `backend/models/`. These are large; expect the first fetch to take a while and to be the slowest part of setup.
4. **Verify the runtime starts** and reports the expected version.
5. **Verify a model loads** and produces output for a trivial prompt.
6. **Confirm neither directory shows up in `git status`.** If either does, the ignore rules are wrong - fix them before committing anything else.

## Disk and time

The weights dominate both. Budget several gigabytes of disk per model and plan to keep only the quantisations you are actually working with; the rest can be re-fetched.

## Reproducing a CI run locally

A local run differs from CI in three ways that matter, and each has bitten someone:

- **Different hardware.** A laptop measurement is a laptop measurement. Never quote one as a runner figure (Rule #10); label it as an order-of-magnitude check.
- **Different thread count.** CI runs with the runner's core count. Match it locally when comparing throughput, or the numbers are not comparable.
- **Thermal behaviour.** A laptop throttles under sustained load in a way a runner may not, which shows up as a large spread rather than a shifted mean. Report the spread.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Runtime binary will not execute | Wrong platform build, or the executable bit is not set. |
| Model fails to load | Truncated download - check the file size against the source. |
| Output differs run to run | Sampling parameters not pinned; determinism comes from `config/`, not from defaults. |
| Much slower than the recorded figures | Thread count not matched to the recorded run, or another process is competing. |
| The weights show up in `git status` | The ignore rules are wrong. Fix before committing - a staged multi-gigabyte file is painful to remove from history. |

## Open research

Extremely low-bit quantisations (1-2 bit) have been published for several open-weights model families, and would change the fit calculation substantially: a model that currently does not fit the cache budget might. This has **not** been evaluated here. Treating it as a candidate requires the same two tests as any other model - Andre on whether quality survives the quantisation on our own corpus, Carmack on whether it fits and how fast it runs, both measured rather than assumed ([../agents/guardrails.md](../agents/guardrails.md), authority table).

## See also

- [../concepts/config.md](../concepts/config.md) - where the model reference, quantisation and runtime version are pinned.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - what the Summarize stage does with the model.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #2 (the runner is the architecture), Rule #10 (measured, not estimated).
