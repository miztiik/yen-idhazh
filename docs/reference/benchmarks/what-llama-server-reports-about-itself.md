# What llama-server reports about its own runtime settings

**Last Updated**: 2026-09-18
Which of the runtime settings we pin the server will confirm back, and through
which surface - the log, `/props` or `/metrics`.

**Flash attention is observable, and only in the log, and only at verbosity 4 or
higher.** `/props` and `/metrics` say nothing about it: both come back
byte-identical whether the server was started with `-fa on` or `-fa off`. The
log at `-lv 4` says it three ways - a named state, a compute buffer that is
5.1 times larger without it, and a graph 180 nodes longer - and the log at the
default verbosity of 3 says none of them, because it prints twelve lines and the
whole model-loader block is missing.

So a check that flash attention is ACTIVE, rather than that a flag was accepted,
is writable today. It costs one flag on the server and about 15 KB of log per
server start. This is the instrument
[row 3 of the runtime plan](../../../TODO/20260905-09-pin-the-runtime-plan.md) was
held on - its section 1a reads "the instrument does not exist" - and the same
flag hands row 4 the KV-buffer and compute-buffer lines it needs. The hold
itself is not lifted by this page: the row's other trigger is memory, which this
page has nothing to say about, and the build tested here is not the pinned one.

**Both were lifted on the runner, and this instrument is what read them.** Run
`2026-09-09-34379502244` at `log_verbosity: 4` wrote 1,306 log lines a shard
against 342 to 404 at verbosity 3, and the KV-buffer line was among them. One
correction from that run: on build 10598 the named state is
`llama_context: flash_attn = enabled`, not a `resolve_fused_ops` line.

**Method.** The binary reports 32,592 MiB of host memory. Taken
2026-09-09 between 01:42 and 01:50 local. Eleven server starts: one at the
default verbosity, one at `-lv 9`, and three each at `-lv 4` with no flag, with
`-fa on` and with `-fa off`. The argv is built by
`idhazh.llm.server.server_argv` from the committed `models.summarize` block, the
way `.github/scripts/start-llama-server.sh` builds it, so what ran is the
process the pipeline starts and not a hand-written command line. Absolute paths
below are rewritten to their repository-relative form.

**Two things this is not, and both matter before any number here is quoted.**
The build is llama.cpp `b10444`, commit `5f754ea0e`, and `digest.yml` pins
`b10598` - 154 builds away, so a line this build prints is evidence about a
neighbour of the pinned build rather than about the pinned build itself. And the
weights are `Qwen3-8B-Q4_K_M.gguf`, 5,027,783,488 bytes: the 8B, where the
active model file names a 9B for `models.summarize`. The 9B is not on this
machine. Every megabyte below is therefore the 8B's and none of them may be
quoted as the 9B's. What does carry across is which lines the binary prints and
what those lines are called, because that is a property of the binary - and the
committed captures from the pinned build agree with this one line for line on
the part both of them print, which is the next section.

### A default start prints twelve lines, and the one row 3 wants is not among them

Verbatim, from `-lv` unset:

```text
0.00.167.722 I cmn common_param: common_params_print_info: verbosity = 3 (adjust with the `-lv N` CLI arg)
0.00.179.336 W srv llama_server: -----------------
0.00.179.357 W srv llama_server: CORS is set to allow all origins ('*') and no API key is set
0.00.179.358 W srv llama_server: this can be a security risk (cross-origin attacks)
0.00.179.359 W srv llama_server: more info: https://github.com/ggml-org/llama.cpp/pull/25655
0.00.179.360 W srv llama_server: -----------------
0.00.192.023 I srv load_model: loading model 'backend/models/Qwen3-8B-Q4_K_M.gguf'
0.01.350.960 W load: control-looking token: 128247 '</s>' was not control-type; this is probably a bug in the model. its type will be overridden
0.25.539.158 I cmn init: llama threadpool init, n_threads = 4
0.33.179.385 I srv load_model: initializing, n_slots = 1, n_ctx_slot = 8192, kv_unified = 'false'
0.33.279.911 I srv llama_server: model loaded
0.33.280.340 I srv llama_server: listening on http://127.0.0.1:38911
```

Absent at verbosity 3: `llama_model_loader:`, `print_info:`, `load_tensors:`,
`system_info`, `llama_kv_cache:`, `sched_reserve:`, and any line naming flash
attention. Present at verbosity 3: the window one sequence gets,
`n_ctx_slot = 8192`.

**The four committed CI captures under `tests/fixtures/runtime/` say the same
thing on the pinned build**, which is what makes a laptop reading worth having
here. `2026-08-29-3-shard-0.server-head.txt` is `b10598` on a GitHub-hosted
runner against the 9B, and it opens with the same `verbosity = 3` line, the same
CORS block, the same `load_model: loading model`, the same
`init: llama threadpool init, n_threads = 4`, the same
`load_model: initializing, n_slots = 1, n_ctx_slot = 8192, kv_unified = 'false'`,
`model loaded` and `listening on` - eleven lines in common, in the same order,
before the first request. It differs by two lines and neither is a loader line:
`b10598` adds a notice that the default port will change, and this build adds a
warning about one token in the 8B's vocabulary. **So the startup grammar is the
same across the 154 builds and across the two machines**, and the missing block
was never a CI artefact or a build difference. It was the verbosity, on both,
all along. Every line goes to stderr, not stdout; CI's `> "${NAME}.log" 2>&1`
catches both and a redirect of stdout alone would catch nothing.

### Raising the verbosity brings all of it back

| `-lv` | stderr lines | stderr bytes | what appears |
| --- | --- | --- | --- |
| 3, the default | 12 | 1,085 | nothing new |
| 4 | 206 to 208 | 16,011 | the loader block, `system_info`, the KV and compute buffers, the flash-attention state |
| 9 | 3,036 | 210,079 | `graph_reserve` per node, and a second copy of the fit pass |

Line counts across nine `-lv 4` runs spanned 206 to 208; the two-line variation
is the memory-fit pass, which reports differently on a cold and a warm page
cache. Byte figures are from one representative run of each level.

### `-fa on` versus `-fa off`: three observables, all of them in the log

Three runs of each case. **Every figure below was identical in all three, so the
spread is zero.**

| Reading, at `-lv 4` | no `-fa` flag, as committed | `-fa on` | `-fa off` |
| --- | --- | --- | --- |
| `llama_context: flash_attn` | `auto` | `enabled` | `disabled` |
| `resolve_fused_ops: Flash Attention enabled` | present | absent | absent |
| `sched_reserve: CPU compute buffer size` | 112.01 MiB | 112.01 MiB | 572.01 MiB |
| `sched_reserve: graph nodes` | 1266 | 1266 | 1446 |
| `llama_kv_cache: CPU KV buffer size` | 1152.00 MiB | 1152.00 MiB | 1152.00 MiB |
| `/props`, whole document | identical | identical | identical |
| `/metrics`, whole document | identical | identical | identical |

**Read the first two rows together or the answer is wrong.**
`llama_context: flash_attn` prints what was ASKED for, not what happened - with
no flag it says `auto`, which is the state row 3 exists to refuse to accept as
an answer. `resolve_fused_ops: Flash Attention enabled` is the decision, and it
appears only when there was a decision to make, so it is absent from both
explicit settings. The two together cover all three cases and nothing else does.

**The committed config resolves to flash attention ON.** `flash_attention` is
`null` in `config/idhazh.json`, so `server_argv` passes no `-fa` at all, so the
binary defaults to `auto`, and `auto` resolved to enabled on all four runs here.
The compute buffer says so independently: 112.01 MiB, the same as `-fa on`, and
460 MiB below `-fa off`. Whether it also resolves that way on a runner's
processor is untested and is not a question a laptop can answer.

### The check this made writable, and why it is gone

Against `llama-server.log`, after the server is healthy and with `-lv 4` passed:

```text
active = the log holds "llama_context: flash_attn = enabled"
 OR it holds both "flash_attn = auto"
 and "resolve_fused_ops: Flash Attention enabled"
refused = the log holds "llama_context: flash_attn = disabled"
absent = neither - which means the verbosity was not raised, and is a
 failure of the check rather than a report about attention
```

Three states, not two, and why the third one has to exist is in
[agent-notes/git-and-github.md](../agent-notes/git-and-github.md#reading-a-run).
Corroborate with `sched_reserve: CPU compute buffer
size`, which is a physical consequence rather than a restatement: on this model
at `n_ctx` 8192 it is 112.01 MiB with attention fused and 572.01 MiB without.
Corroboration is worth the line because the log grammar is llama.cpp's and moves
between builds, while the buffer difference is arithmetic and does not.

**Written 2026-09-09 as `idhazh.llm.server.flash_attention_state`, deleted
2026-09-21.** Nothing ever called it: no stage, no workflow step and no operator
utility asked it anything, so it had four tests and no reader. Whether a kernel
fused is the runtime's own business, and this project was asking by grepping a
log line it had to raise the verbosity to see. The three excerpt captures its
tests ran off went with it; the readings they held are the table above, which is
what a person actually reads. What stays is the flag: `flash_attention` is still
a config knob, `server_argv` still emits `-fa` from it, and the recorded input
manifest still carries its spelling in `runtime_flags`.

### `/props` settles the build and the window, and cannot settle flash attention

`/props` is the right instrument for three questions and the wrong one for this
one. It carries no key matching `flash`, `attn`, `kv` or `buf` anywhere in the
document, and the five cases are byte-identical once the per-process
`media_marker` nonce is normalised out.

| `/props` field | Value on this run | What it settles |
| --- | --- | --- |
| `default_generation_settings.n_ctx` | 8192 | the effective window, at any verbosity |
| `build_info` | `b10444-5f754ea0e` | which build is actually running |
| `model_path`, `model_alias`, `model_ftype` | the file, `qwen3-5-9b-q4-k-m`, `Q4_K - Medium` | which bytes were opened, and under which alias |
| `total_slots`, `endpoint_metrics` | 1, `true` | the slot count and whether `/metrics` will answer |

The alias reads `qwen3-5-9b-q4-k-m` while `model_path` ends in
`Qwen3-8B-Q4_K_M.gguf`, because `--alias` comes from config and the weights came
from the environment. That disagreement is the reason `digest.yml` already
checks the PATH against the expected filename rather than trusting the alias.

**`build_info` is worth taking.** It is the running process answering, where
`llama-server --version` is a second process that need not be the one serving.

### `/metrics` answers neither question

Fifteen series, and the whole document has the same SHA-256 at the default
verbosity, with `-fa on` and with `-fa off`. It counts prompts, tokens,
requests, slots and speculative decoding. It has no memory series and no
attention series, so it can say nothing about flash attention or about a buffer
size.

### What landed from this, and what one server start now costs

**The flag is committed.** `models.summarize.inference.log_verbosity` is `4` in
`config/idhazh.json`, and `idhazh.llm.server.server_argv` emits `-lv 4` from
it. It is a knob rather than a literal because an operator debugging a start
wants `9` and a daily run does not (Guardrail #6). Null omits the flag and keeps the
runtime's own default of 3, so a checkout with no config file starts a quiet
server exactly as before.

**The cost is one job artifact, and it is not a committed file.** A server start
goes from 12 stderr lines and 1,085 bytes to about 206 lines and 16,011 bytes -
roughly 15 KB per start, on the readings in the table above. A daily run made
five starts across two roles when this was written, four work shards and the
visual planner; that second role retired on 2026-09-13, so it is four starts and
about 62 KiB a day now. It lands in the run's own log, which GitHub Actions retains
and nothing else reads, and no byte of it reaches the 1 GB published site
(Guardrail #2) or the repository. The daily workflow already uploads
`llama-server.log` as a two-day artifact, well inside the 500 MB allowance.

**`log_verbosity` is not fingerprint-digested**, and sits in
`idhazh.fingerprint.NOT_DIGESTED` with that reason written next to it. A log
level cannot move a logit, so digesting it would have invalidated every earlier
work identity on the day somebody turned the logging up - which is what
`n_threads_batch` was refused for on the other side of the same argument.

## See also

- [../pipeline-cost.md](../pipeline-cost.md) - the figure this record puts in force, beside every other producer figure.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, which is why every number here carries its conditions.
