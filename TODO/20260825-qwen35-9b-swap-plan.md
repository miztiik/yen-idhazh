# Qwen3.5-9B Summarizer Swap - Plan

**Last Updated**: 2026-08-25

**Status:** Prepared, not executed. The owner selected Qwen3.5-9B as the target.
Raw runner fit passed. Quality, complete context fit, production-path fit and
reproducible identity remain blocked on the qualification repairs below. Keep
Qwen3-8B configured until the hard gates pass.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Goal | Replace only the build-time summary model with exact Qwen3.5-9B-Q4_K_M bytes. |
| Owner authorization | Target selection is approved. Safety, compatibility, identity, quality and runner-budget failures still block merge. |
| Hard scope - in | Validation replay and contracts; scorer/model/runtime identity; candidate tokenization, canaries, quality and production-path measurements; config/workflow model swap; cache transition; rollout evidence; living docs. |
| Hard scope - out | Prompt rewrite; vendor sampling; thinking mode; lower quantisation; mmproj/vision; router/search/scorer replacement; raised runner limits; historical payload rewrite; fingerprint-based inference skip. |
| Correction level | 5 - model pick plus persisted evidence contracts. |
| Execution | Structural commits first; behavioural commits second; adoption is one reversible value-only commit after evidence. |
| Rollback | Pause workers; delete candidate cache; revert adoption; fill and verify incumbent cache once; resume. Keep Qwen3.5-produced historical payloads attributed. |

## Target identity

| Field | Value |
| --- | --- |
| Repository | `unsloth/Qwen3.5-9B-GGUF` |
| Repository revision observed 2026-08-25 | `3885219b6810b007914f3a7950a8d1b469d598a5` |
| File | `Qwen3.5-9B-Q4_K_M.gguf` |
| Model id | `qwen3-5-9b-q4-k-m` |
| Quantisation | `Q4_K_M` |
| Bytes | 5,680,522,464 |
| SHA-256 | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
| Licence | Apache-2.0 |
| Vision projector | Not used or downloaded. |

## Measured facts

Candidate run: `ubuntu-latest`, AMD EPYC 9V74, 2026-08-23, llama.cpp
`b10598` / `56db501e7`, 4 threads, 3 repeats.

| Measure | Value |
| --- | --- |
| Prefill 730 / 1800 / 4850 | 10.14 +/- 0.01 / 10.06 +/- 0.01 / 9.84 +/- 0.01 tok/s |
| Decode 250 | 6.01 +/- 0.11 tok/s |
| Cold download | 118 s, n=1, spread unavailable |
| Candidate + 4B router raw weights | 8,177,802,720 bytes |
| Incumbent + candidate + router raw weights | 13,205,586,208 bytes - transition does not fit the cache ceiling |
| Runner thread decision | Keep 4; 8 was slower on 2 cores x 2 SMT. |

The incumbent throughput row used a different CPU observation and llama.cpp
build. It is not a controlled A/B.

## Current blockers

1. `validate.yml` refetches each URL for each model. It does not replay identical
   Article bytes.
2. Validation has no typed corpus/result evidence contract, paired denominator
   or pairwise human label shape.
3. `leaderboard_hhem` requires a float although Qwen3.5 has no reported value.
4. `--cap` is parsed but not passed into `stage_plan`; validation can exceed the
   job budget.
5. Validation hardcodes the incumbent, server flags and mutable runtime, and
   caches both weights together.
6. `stage_work` and validation pass truncated text as both seen and full HHEM
   input.
7. HHEM revision is mutable `main`; its digest hashes the name and revision
   string rather than loaded weights.
8. Production fingerprints are not wired to the ledger or skip classifier and
   record false/zero weight, runtime, template and runner identity.
9. `PipelineInputs` omits article-input identity and behaviour-affecting optional
   runtime fields.
10. Drift uses live ledger windows, persists no fixed-set row and ignores
    `model_id`.
11. Production model refs are duplicated across config and workflows.
12. Production divides the full plan across a fixed worker count and does not
    enforce `run.shard_size`.
13. Candidate prompt tokens, complete chat-templated context, live canaries,
    recurrent prefix reuse, production-worker RSS/time and paired quality are
    unmeasured.

**Skip decision:** defer inference skipping. This plan wires truthful observed
identity and one assembler-owned fingerprint ledger writer only. A future skip
needs a typed per-item `WorkIdentity` that combines article-input digest with
pipeline fingerprint, plus an integration test proving changed source bytes are
not skipped. Do not put article identity into the configuration fingerprint.

## Status reckoner

| Row | Work | Depends on | Status |
| --- | --- | --- | --- |
| 1 | Typed validation corpus/result and pairwise human-label contracts, including `not_reported` leaderboard provenance and a pre-registered selector with tie handling | - | PENDING |
| 2 | One typed source for model/runtime identity; exact download and cache verification | - | PENDING |
| 3 | Expand fingerprint event/ledger contract and define assembler-owned writing | 2 | PENDING |
| 4 | Wire truthful fingerprint identity and model-separated drift | 1, 2, 3 | PENDING |
| 5 | Capture once, replay both models, preserve failures, pin scorer, isolate date/run, remove `--autostash` | 1, 2 | PENDING |
| 6 | Candidate tokenizer, live canary, deterministic, same-job raw and production-path measurements | 2, 5 | PENDING |
| 7 | Blind paired human selection plus Andre quality and Carmack fit verdicts | 5, 6 | PENDING |
| 8 | One value-only Qwen3.5 adoption commit; current-default docs/tests only | 4, 7 | PENDING |
| 9 | Cache transition, bounded Content refresh, manifest/fingerprint/health verification | 8 | PENDING |
| 10 | Distil landed facts into living docs and delete this plan | 9 | PENDING |

## Commit boundaries

1. **Structural:** introduce validation corpus/result and pairwise label contracts
   with backwards-compatible readers.
2. **Structural:** centralize model/runtime identity from typed config.
3. **Structural:** expand fingerprint event/ledger ownership and migration.
4. **Behavioural:** verify runtime/GGUF/cache identity and write truthful
   fingerprint rows.
5. **Behavioural:** capture once, replay both models and retain failures.
6. **Behavioural:** segment model-dependent drift and make bounded dispatch real.
7. **Measurement:** run tokenizer, canary, raw, production-path and paired
   quality instruments.
8. **Behavioural:** switch only `models.summarize` to the exact target.
9. **Rollout:** delete old summary cache, fill candidate cache once, run bounded
   refresh and verify.

Do not combine structural and behavioural changes in one commit. The value-only
model swap in row 8 has no schema bump. Contract repairs in rows 1-3 do.

## Hard acceptance gates

- At least 20 common successful pairs from a deterministic corpus covering all
  four bands plus brief, abstract and truncated cases.
- Full attempted denominator and asymmetric failures recorded.
- Exact input hashes shared across models.
- Three deterministic repeats.
- Complete candidate chat request plus 900 output tokens fits `n_ctx=8192`.
- `fits_context` over-reserves.
- Zero reasoning, schema or canary failures.
- Every canary `must_not_survive` marker absent and every `must_survive` fact
  present in a non-blank valid reply.
- Before outputs are revealed, Andre registers direction, paired statistic and
  tolerance for item success, unsupported numbers, dropped hedges, lead
  coverage, extractiveness, publishable word gate, title fallback and
  brief/abstract/truncated handling. Every registered hard boundary passes.
- Compression is reported as a diagnostic and is not a hard pass/fail metric.
- Blind pairwise human question, tie handling and pass threshold are registered
  before outputs are revealed and pass. No LLM judge.
- Same-job raw runner evidence and production-path server-plus-scorer fit.
- Every qualification and production worker fits the current 330-minute bound
  with measured worst-case margin; do not size against the six-hour platform
  maximum.
- Steady-state cache measured under 10 GB; transition old summary cache removed.
- All gates in `docs/how-to/run-the-gates.md`.

## Tests that ship with the repairs

- A source fixture that changes on second read proves extraction happens once.
- Both models receive identical input hashes.
- Missing leaderboard provenance stays null/`not_reported`, never zero.
- One candidate failure remains in the denominator.
- Validation argv equals production `server_argv`.
- Wrong cached bytes fail before server start.
- Worker identity reaches one assembler-owned fingerprint writer.
- Old validation, fingerprint and run-manifest fixtures still load.
- Stale result files and UTC rollover cannot affect the decision.
- Drift does not mix model-dependent series across model ids.
- HHEM screening cannot write the final selected model; only the typed blind
  human selector can.

## See also

- [`../docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - generic adoption procedure.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - exact candidate and runner facts.
- [`../docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - selector and alarm boundaries.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - identity and fingerprint gaps.
- [`../docs/architecture/summarize/prompt.md`](../docs/architecture/summarize/prompt.md) - thinking, schema and tokenizer controls.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - local gate commands.
