# 09 - The runtime stops guessing which model it was tuned for

**Last Updated**: 2026-09-05
**Level**: 4 (structural: the settings block every stage inherits, and the window every later plan is sized against)

**Chain**: previous [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md) | next [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O22, O24, O38, sections 11.0, 11.2, 11.2a, 13.3, C19.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | `ModelsConfig` carries two model roles and **one shared** `InferenceConfig`. Change which weights a role names and the new model silently inherits the previous one's window, cache types, batch shape and attention flags. Nothing raises. The run comes back slower, or out of memory, or with different words, and the config diff shows one repository string. Separately, the two-call design does not fit today's 8,192-token window at all - its worst case is 105 percent of it |
| Hard scope - in | Six memory numbers the job already collects and discards; ending the silent inheritance; `n_ctx` to 16,384 with flash attention on; one measured run that prices the runtime change alone |
| Hard scope - out | **Retiring the small model** - plan 11 does that, in the same commit as the flag flip, because it is what draws a chart today. Any prompt change. Any second call. Any cache-type change - `q8_0` moves the words and is a separate measurement |
| ESCALATE triggers | 1. The measured peak resident memory at 16,384 leaves less than 1.0 GiB free on the 14.90 GiB usable runner. 2. Flash attention does not report as active in the server's own startup line. 3. Any setting in section 11.2a is proposed without the model entry, runner and date it was derived against |
| Chosen strategy | Measure the memory first so the window raise can be judged, then close the inheritance, then raise the window, then price it. Every intermediate state ships |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The distinction this plan exists to write down.** The **pipeline** is model-neutral and stays so - the weights are named in one config entry and no module, class, field, telemetry value or schema stem carries a parameter count or a vendor. The **runtime settings are not neutral**, and pretending otherwise is the hazard. Every number in section 11.2 was derived from one model's architecture on one runner. A model swap re-derives the whole block, not only the window.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Six numbers the job already has and throws away | - | A | DONE #525 (three of six) | yi-h01-memory | #525 | worker |
| 2 | A model swap can no longer inherit in silence | - | A | DONE #528 | yi-h02-inherit | #528 | worker |
| 3 | The window doubles and flash attention pays for it | 1, 2 | B | HELD - ESCALATE 1 only (2 resolved #530) | - | - | - |
| 4 | One run prices the runtime and nothing else | 3 | C | HELD - blocked by row 3 | - | - | - |

### What rows 1 and 2 changed under the plan

**Row 1 shipped three of its six fields and withheld three, with evidence.**
`python_peak_rss_bytes`, `cgroup_peak_bytes` and a corrected `python_vmhwm_kb`
sampler column landed. `kv_cache_bytes`, `compute_buffer_bytes` and
`model_buffer_bytes` did not, because the lines section 13.3 sources them from
do not exist. Eight captured logs were searched - the four committed fixtures
under `tests/fixtures/runtime/` and four raw logs of run `32742672105`, 75 to
98 KB each - for `KV self size`, `kv_cache`, `compute buffer`, `CPU_Mapped`,
`model buffer` and `buf size`. Zero matches in any of them. At llama.cpp
`b10598` the server prints twelve startup lines at its default verbosity of 3
and the whole model-loader block is absent: no `llama_model_loader:`, no
`print_info:`, no `load_tensors:`, no `system_info`. Three columns empty on
every row for ever is speculative generality, so they were refused rather than
minted (Fowler).

**Row 2 chose the per-entry block over the qualification gate, and added a
witness.** `models.inference` is gone; each `models.<role>` carries its own
block, and the block carries `declared_for`, the SHA-256 of the entry it is set
for. `ModelsConfig` refuses a config where the two disagree. The qualification
gate was refused because `validate.yml` builds a scratch config whose
`models.summarize` is the candidate and whose every other control is the
committed one - that pairing IS the experiment, so a gate refusing an unmeasured
pairing would refuse the measurement and leave the daily path silent. Moving the
block alone was also not enough: the confirmed red state edits five strings in
place, which a per-entry block still accepts. `pipeline_fingerprint` was proved
unmoved - the same 14 digested knobs stamp `2b9be483...` on both trees.

---

## 1a. Why rows 3 and 4 are held - two ESCALATE triggers, both measured

**Trigger 1 - memory - is already breached at today's window, before the row
runs.** Section 11.2 sized the raise against 13.29 GiB peak and 1.61 GiB free.
That figure is llama-server's high-water mark ALONE, which is the whole point of
row 1 decision 1. Adding llama-server and python at the same instant, sample by
sample, over the four committed captures of run `2026-08-29-3` (291 to 383
samples a shard, 15 s apart, GitHub-hosted `ubuntu-latest`, 4 vCPU, 16 GB,
captured 2026-08-29, recomputed 2026-09-08):

| Shard | llama-server alone | Both at one instant | Free of 14.90 GiB |
| --- | --- | --- | --- |
| 3 | 13.16 GiB | **14.31 GiB** | **0.59 GiB** |
| 2 | 12.94 GiB | 14.15 GiB | 0.75 GiB |
| 0 | 12.57 GiB | 13.93 GiB | 0.97 GiB |
| 1 | 12.65 GiB | 13.86 GiB | 1.04 GiB |

Spread 0.45 GiB. Three of four shards are already under the 1.0 GiB the trigger
asks for, at `n_ctx` 8,192. The independent second instrument agrees: the widened
`state/runtime-counters.csv` now holds 225 rows over 56 runs, worst
`peak_rss_bytes` 13.82 GiB - 0.64 GiB above the 13.18 GiB
`docs/reference/measurements.md` recorded on 2026-09-01, with no model or window
change in between.

**Trigger 2 - the instrument - is RESOLVED, by PR #530.** It was raised because
no captured log carries a flash-attention line, a KV-buffer line or a
compute-buffer line. The cause was the verbosity, not the build. Measured
2026-09-09 on a Windows developer box against `llama-server` `b10444`
(`5f754ea0e`) and the 8B weights, three runs an arm, zero spread on every
figure:

| Reading, at `-lv 4` | no flag, as committed | `-fa on` | `-fa off` |
| --- | --- | --- | --- |
| `llama_context: flash_attn` | `auto` | `enabled` | `disabled` |
| `resolve_fused_ops: Flash Attention enabled` | present | absent | absent |
| `sched_reserve: CPU compute buffer size` | 112.01 MiB | 112.01 MiB | 572.01 MiB |
| `/props` and `/metrics`, whole documents | identical | identical | identical |

Three consequences, and the third is the one that changes the plan.

1. **The instrument is the log at `-lv 4`, not `/props`.** `/props` and
   `/metrics` are byte-identical between the two arms, so neither can answer the
   question. `/props` remains the right reader for the effective `n_ctx` and the
   build string, and needs no verbosity change for those.
2. **The check has three states, not two.** `llama_context: flash_attn` prints
   what was ASKED for, so with no flag it says `auto` - which is exactly the
   non-answer the oracle exists to refuse. `resolve_fused_ops` is the decision
   and prints only when there was one to make. Absent means the verbosity was
   not raised, and that fails the CHECK rather than attention. Corroborate with
   the compute-buffer size, which is a physical consequence where a log string
   is grammar that moves between builds. `-lv 4` costs 1,085 bytes a start
   rather than 16,011 - 206 lines against 12.
3. **The committed config already resolves to flash attention ON.** `null` emits
   no flag, no flag means `auto`, and `auto` resolved to enabled on all four
   no-flag runs. So row 3's flash-attention half may be a no-op on this
   processor, and O22's "flash attention pays for the doubling" may already be
   priced into the 13.29 GiB baseline rather than being a saving still to come.
   Whether `auto` resolves the same way on a runner's processor is untested and
   one CI run with `-lv 4` settles it.

Build gap, stated rather than hidden: `digest.yml` pins `b10598` and the box
tested `b10444`, 154 builds apart. Half the gap is closed by evidence -
`tests/fixtures/runtime/2026-08-29-3-shard-0.server-head.txt` is a real `b10598`
runner capture and opens with the same eleven startup lines in the same order,
`verbosity = 3` among them. So the startup grammar matches across both builds
and both machines, and the absent loader block was never a CI artefact.

**Trigger 1 still stands, and row 4 still has no memory instrument.** Row 4
decision 2 closes the 7.7 GiB gap from the KV-buffer and compute-buffer lines,
which `-lv 4` does now produce - but the arithmetic that gap sits in was written
against llama-server alone, and the concurrent figure above is what a raise has
to clear.

---

## 2. Row #1 - Six numbers the job already has and throws away

- **Scope:** `kv_cache_bytes`, `compute_buffer_bytes`, `n_ctx_configured`, `model_buffer_bytes`, `python_peak_rss_bytes` and `cgroup_peak_bytes` added to the runtime counters row, all from data the job already collects.
- **Files touched:** `backend/idhazh/contracts/runtime_counters.py`, `schemas/runtime-counters-row.schema.json`, `backend/idhazh/llm/**` (the server-log reader), `.github/workflows/digest.yml`, `tests/fixtures/contracts/runtime-counters-row/*.json`, `state/runtime-counters.csv` (widened), `backend/tests/test_contracts.py`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch writing the new cells.
- **Oracle:** The widened ledger re-parses every existing row with the new values absent, and the byte delta equals exactly the new commas plus the new header characters - counted, not estimated. A widening that moved a cell would fail that arithmetic.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `peak_rss_bytes` is llama-server's high-water mark **alone**, so every headroom figure quoted today is an upper bound on headroom - the unsafe direction. `cgroup_peak_bytes` is the number the runner counts against the limit and is the only authoritative one | Section 13.3 |
| 2 | The sampler reads `VmHWM` for llama-server and `VmRSS` for python. `VmRSS` is instantaneous, so a 15-second sampler can miss a spike and the recorded python peak is a **lower** bound. Read `VmHWM` for both | Section 13.3 |
| 3 | Append at the end. A new optional column is null on every row written before it existed, so report on the **data**, never on the column list | Recorded trap |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Raise the window and measure afterwards | Arithmetic accounts for only about 5.6 GiB of the 13.29 GiB measured, so no pure extrapolation is trustworthy. Only the delta is, and only two terms move with the window | Carmack |

---

## 3. Row #2 - A model swap can no longer inherit in silence

- **Scope:** End the shared `InferenceConfig`, so a settings block is bound to the model entry it was derived against.
- **Files touched:** `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/idhazh/llm/server.py`, `backend/idhazh/evals/qualify.py`, `frontend/src/lib/server/config.ts`, `backend/tests/test_contracts.py`, `backend/tests/test_qualify.py`, `docs/concepts/config.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A config that names a different model without supplying settings for it **fails validation with a message naming the missing block**. Whether that is achieved by moving the block onto the model reference or by a qualification gate that refuses an unmeasured pairing is the row's call; what is not open is leaving it silent.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every llama-server setting quoted anywhere carries the model entry, the runner and the date it was derived against. A bare `n_ctx: 16384` in a doc is an unmeasured number justifying a design | O38, Rule #10 |
| 2 | The design's neutrality is preserved: the fix binds settings to an entry, it does not put a model's identity into a name | O38, section 15.4a |
| 3 | `flash_attention` **already exists** as a key set to `null`. O22 is a value change, not a new knob | C19, verified 2026-09-05 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A comment warning that settings are model-specific | A comment is not a gate. The failure is silent and produces a plausible run | Fowler |

---

## 4. Row #3 - The window doubles and flash attention pays for it

- **Scope:** `n_ctx` 8,192 to 16,384 and `flash_attention` on, in **one** commit.
- **Files touched:** `config/idhazh.json`, `backend/idhazh/llm/server.py`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `frontend/src/lib/server/config.ts`, `backend/tests/**`, `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch reading the server's own startup lines.
- **Oracle:** Flash attention is asserted **active from the server's own startup line**, not from the flag having been passed - and the measured worst peak stays at least 1.0 GiB below the 14.90 GiB usable. A flag that was accepted and ignored is the failure this oracle exists to catch.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One commit, because flash attention removes the term that scales with `ubatch` times `n_ctx` - which is exactly what the larger cache costs. Split, the intermediate state pays a bill it need not | O22, section 11.2 |
| 2 | **32,768 is refused even though it fits.** The largest prompt ever seen is 5,516 tokens and the truncation cap is 5,000, so a 32K window is more than five times what the pipeline can put into it, and it would spend 1 GiB of a 1.61 GiB margin doing so | Section 11.2 |
| 3 | 131,072 fails on wall clock before memory: filling it once at 9.84 tokens a second takes 222 minutes for a single article, against a shard timeout of 200 | Section 11.2 |
| 4 | Cache types stay `f16`. `q8_0` halves the cache and **changes how partial sums accumulate**, so it changes the words - a separate measurement, not this commit | Section 11.2a |
| 5 | `--ubatch-size` stays 512 and `--threads-batch` stays unset. The first exists only to pay for a window this pipeline cannot fill; writing `4` where `null` sits invalidates every prior work identity for zero change in output | Section 11.2a |
| 6 | The candidate table from plan 08 is **not** in the 8,580-token worst case and must be added before the number is final. It is bounded by construction, so this is arithmetic, not an estimate | Section 11.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Raise the window without flash attention | Works, and pays about 0.25 GiB it need not | Carmack |
| 2 | Take `--jinja` in the same commit | Highest-value item on the settings list and it needs its own digested config field. It moves the words and deserves its own measurement | Andre, section 11.2a |

---

## 5. Row #4 - One run prices the runtime and nothing else

- **Scope:** One frozen-set run after rows 1 to 3, recording what the runtime change alone did to memory, wall clock and the words.
- **Files touched:** `docs/reference/measurements.md`, `state/fingerprints.csv` (a new stamp lands naturally)
- **Acceptance gates:** the full suite; one dispatch with nothing else in flight.
- **Oracle:** The recorded numbers carry the model entry, the runner, the date and the spread, and the `pipeline_fingerprint` moved - which is free, external evidence that the config change actually ran rather than being merely committed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The boundary is here so that if a summary metric moves at plan 11 there is **one** suspect rather than three. Retiring the model, raising the window and adding a call each invalidate comparability on their own | Andre, 2026-09-05 |
| 2 | Take the memory reading with nothing else in flight. The KV-buffer and compute-buffer lines from the server log are what close the 7.7 GiB gap between arithmetic and measurement | Carmack, section 13.1 |
| 3 | Comparability of `summary_faithfulness` across this boundary is **not** claimed. Flash attention moves float accumulation order, so it moves the words | Section 11.2a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fold this measurement into plan 11's cutover | Then three changes land together and no test separates them | Andre |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md) - the previous plan.
- [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) - the next plan.
