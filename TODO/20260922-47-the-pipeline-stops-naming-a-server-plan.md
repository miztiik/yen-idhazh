# The model server's address and settings move into config

**Last Updated**: 2026-09-22

**Level**: 3 (`CLAUDE.md` section 6). It crosses three boundaries - python, committed config and the workflow files - and it renames two config keys that a generated schema is built from. Nothing persisted by an earlier run changes shape. With the config left as committed, every address and every request body is character-for-character what this repository produces today.

> Execute with [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md), parallel N = 2, AUTHOR-AND-STOP until the user authorises the run.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Why this plan exists** | Two things the pipeline hands a model server are typed into python and reachable by no config value. The **address** is three constants in [`backend/idhazh/llm/server.py`](../backend/idhazh/llm/server.py). The **sampling settings** are gated by a lookup table, so only `temperature`, `top_p` and `seed` can ever reach the wire - a key llama.cpp adds tomorrow is unreachable without a code edit, and a key added to the model file today validates and is silently dropped. |
| **The rule this plan is built on** | **A program that starts its own server probes loopback. Everything else reads the config.** And **a setting this project does not compute on is passed through, never mapped.** |
| **What changes for the reader** | Nothing. No published file, no page, no column. |
| **What changes in production** | Nothing, if the committed config is left alone. The three sampling values this plan writes down are the values llama.cpp is already applying. |
| **Why config and not an environment value** | An environment value is the only kind of setting that is never committed, so it is the only one that changes where article text goes with no diff and no review. A config field gets exactly the review a source constant gets. Owner ruling, 2026-09-22. |
| **Hard scope - in** | `config.model_server.base_url`; the address constants derived from it; `LLAMA_PORT` deleted; the `request` block renamed to `sampling` and passed through whole; `request_timeout_minutes` moved up to the model entry; the three identity rows removed from the lookup table; `models.<verb>` renamed to `models.<noun>`; `LLAMA_WEIGHTS` renamed and the dead `LLAMA_ROLE` deleted; every remaining `127.0.0.1` literal reduced to one; one log record naming the server that answered; the fingerprint stamping an unrecorded build when the address is not loopback; four sentences citing a project rule that does not exist. |
| **Hard scope - out** | Table B. Four rows, each priced. |
| **Supersedes** | The surviving half of row 21 of [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md). Table C records what that row asked for and what happened to each part. |
| **Depends on** | Nothing, but two live plans overlap and the order matters. See **Sequencing** below. |
| **ESCALATE triggers** | Five, below Table D. |
| **Execution** | Four pull requests in two waves. Peak two people. |

### Sequencing against the two live plans

| Plan | Shared files | Ruling |
| --- | --- | --- |
| [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) | `backend/idhazh/llm/server.py`, the five workflow files, `backend/utilities/llama_argv.py`, `.github/scripts/start-llama-server.sh` | Plan 44 line 34 hands every process-boundary value to this plan by name. **PR A of this plan runs before or after plan 44's workflow pull request, never beside it.** Plan 44 is moving those shell scripts into python; if it lands first, PR A's workflow work shrinks to a config read in python and gets smaller, not larger. |
| [`20260922-46-one-writer-for-the-corpus-plan.md`](20260922-46-one-writer-for-the-corpus-plan.md) | none | No ordering needed. |

### The owner question this plan carries

Not a blocker. The census test this plan once carried is gone, because there is no environment value left to police.

Three code comments and one documentation paragraph say hosted inference is forbidden by `CLAUDE.md` section 0a. Section 0a lists one non-goal and it is accessibility audit tooling, so all four cite a rule nobody wrote. Row 1 deletes them and replaces each with a statement of what the code does.

That leaves the project with no written position on where article text may be sent. The recommended replacement is one clause on Guardrail #11: *article text fetched from the open web is sent only to a model process the operator of this run controls, and a run that sent it elsewhere is not a run this project publishes.* An amendment to a guardrail is the owner's and no agent's (`CLAUDE.md` section 1). It is recommended rather than required because the review gate never left: after this plan the address is a committed config line, so changing it is a diff a person reads.

### ESCALATE triggers

1. **Stop** if any row leaves the client resolving to one server while a job's readiness probe checks another. A probe that clears a server nobody talks to is worse than no probe.
2. **Stop** if any row would make `config/idhazh.json` or a model file readable by anything but this repository. A config file this project authors needs no declared shape, and that ruling holds only while nothing else reads one (`CLAUDE.md` section 11, owner ruling 2026-09-21).
3. **Stop** if the sampling pass-through would let a config key replace a decode control. Rows 6 and 7 carry the check that prevents it; a design that needs the check removed is a different plan.
4. **Stop** if PR A is ready at the same time as plan 44's workflow pull request. Run them in either order, never together.
5. **Stop** if any row would raise a runner budget figure. The 6 hour job limit and the 1 GB site limit are GitHub's and cannot be moved (Guardrail #2).

### Table B - Hard scope - out

| id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Reconciling the server's `/props` against the fingerprint the run records | Partly paid. Row 10 makes the run stamp an unrecorded build rather than a false one, so the record stops lying. What stays out is reading the server's own answer and recording what it actually is. | A run that needs to prove which build answered, rather than only to avoid claiming the wrong one. Gating measurement: `curl -s <base_url>/props \| jq 'keys'` against the pinned build, seconds. |
| B2 | A translation table between runtimes, so one model file serves llama.cpp, vLLM and Ollama unchanged | A key one runtime accepts and another rejects fails at request time rather than at config load. Accepted deliberately: a per-key table is the wiring this plan deletes, and it would have to be maintained against three projects that each change their parameters on their own schedule. | A second runtime actually in use, and a measured list of where the two disagree. |
| B3 | Renaming `LLAMA_CPP_BUILD`, `LLAMA_CPP_ASSET`, `LLAMA_CPP_SHA`, `LLAMA_BIN`, `llama-cpp-pin.sh`, `install-llama-runtime.sh` | Nothing. Each names llama.cpp because the thing is llama.cpp. `CLAUDE.md` section 0b bans a vendor name used as this project's vocabulary, not the vendor's name for the vendor's own artefact. | A second runtime, which makes those names wrong. |
| B4 | Changing what any sampler does | A real question left unanswered: `top_k` at 40 and `min_p` at 0.05 are llama.cpp's choices, not measured ones for this corpus. Row 6 writes them down at their current values so nothing moves. | A quality measurement on the holdout set. It is a config edit afterwards, with no code change - which is the point of row 6. |

### Table C - What plan 39 row 21 asked for, and what happened to each part

| id | Asked for | Outcome |
| --- | --- | --- |
| C1 | One request builder instead of four | **Refused.** The four are four shapes carrying four different Guardrail #11 controls: the chat builder sends `response_format` with a `json_schema`, the plain completion builder a top-level `json_schema`, the grammar builder a `grammar`, and the continued builder re-asserts the `json_schema` on a prompt the cache already holds. Collapsing them collapses the controls. |
| C2 | Move to the widely supported `/v1/completions` route | **Refused by a measurement** recorded at `server.py` lines 58 to 66: **both** completion routes, llama.cpp's native `/completions` and the OpenAI-compatible `/v1/completions`, ignore `response_format` and honour a top-level `json_schema`, on build b10444-5f754ea0e as of 2026-09-12. The chat route is not in that measurement and does honour `response_format`. |
| C3 | Delete three slot columns | **Refused.** `backend/utilities/slot_probe.py` is their named instrument. |
| C4 | Stamp the decode mode | **Done** in pull request #1036. |
| C5 | Stop naming a server in source | **This plan**, widened by owner instruction on 2026-09-22 to cover the sampling settings, the vendor-prefixed names and the loopback literals. |

### Table D - What is measured on `origin/main`, and what each number means

| id | Reading | Number | What it means |
| --- | --- | --- | --- |
| D1 | Lines to edit to point the pipeline at another machine | 3 | All in `server.py`. No config value, no flag reaches them. |
| D2 | Places that import `DEFAULT_ENDPOINT` | 26, in 13 files | All become correct when those 3 lines do. This is why the address work is six lines and not a refactor. |
| D3 | Readers of `DEFAULT_HEALTH` | 0 | Defined, used nowhere. Row 2 deletes it. |
| D4 | Occurrences of `LLAMA_PORT` | 51, in 19 files | Row 3 deletes the name entirely rather than renaming it: the port lives inside `base_url`, so there is nothing left for a second value to disagree with. |
| D5 | `127.0.0.1` literals | 30 | 22 in `.github/`, 6 in three self-spawning instruments, 2 in the measuring clients. Rows 2, 3, 4 and 5 take it to **one**. |
| D6 | Sampling keys the model file may set that reach the wire | 3 of 13 the build accepts | `temperature`, `top_p`, `seed`. A fourth key added to the file today validates and is dropped in silence. |
| D7 | Samplers llama.cpp applies that this project does not name | 3 | `top_k` at 40, `min_p` at 0.05, `repeat_last_n` at 64, read from the pinned build's own help text. Live in every summary, chosen by the build, and free to move on an upgrade. |
| D8 | Identity rows in the lookup table | 3 of 10 | `temperature`, `top_p` and `seed` each map to themselves. They gate every other key for no reason. |
| D9 | Reads of `LLAMA_ROLE` | 0 | Set by `start-llama-server.sh` line 59 and read nowhere; the role arrives as `--role`. Row 8 deletes it. |
| D10 | One model server's memory peak | 12.57 to 13.16 GiB, and 14.31 GiB with the job's python | 96.0 percent of a 16 GB machine, over four captures of run 2026-08-29-3 on 2026-09-08. This is why a developer runs the model on a second machine, and it is the person this plan is for. |

---

## 1. Status Reckoner

Statuses: PENDING, IN PROGRESS, BLOCKED, DONE. A row's status is stamped by the change that moves it, in that same change. Workers update their own line and nothing else.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Delete the rule that is not written | none | A | PENDING | - | - | - |
| 2 | The address becomes one config field | 1 | A | PENDING | - | - | - |
| 3 | The port name disappears into the address | 2 | A | PENDING | - | - | - |
| 4 | One loopback literal in the whole repository | 3 | A | PENDING | - | - | - |
| 5 | The model file, and the value nothing reads | 3 | A | PENDING | - | - | - |
| 6 | The run says which server answered | 2 | A | PENDING | - | - | - |
| 7 | Sampling settings pass through, unmapped | 2 | B | PENDING | - | - | - |
| 8 | Model slots get nouns | 7 | B | PENDING | - | - | - |
| 9 | The two measuring clients read the address | 2 | C | PENDING | - | - | - |
| 10 | The run record stops claiming a build it cannot see | 2 | D | PENDING | - | - | - |

### 1a. The four pull requests

| PR | Rows | Wave | Files it touches |
| --- | --- | --- | --- |
| **A - the address** | 1, 2, 3, 4, 5, 6 | 1 | `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/model_server.py` (new), `config/idhazh.json`, `schemas/app-config.schema.json`, all five files under `.github/`, `.github/scripts/start-llama-server.sh`, `backend/utilities/llama_argv.py`, the three self-spawning instruments, `backend/tests/test_summarize.py`, `backend/tests/workflows/_harness.py`, `backend/tests/workflows/test_model_server_jobs.py`, `docs/how-to/run-the-pipeline.md` |
| **B - the settings** | 7, 8 | 2 | `backend/idhazh/llm/server.py`, `backend/idhazh/config.py`, `backend/idhazh/contracts/knobs/models.py`, `config/models/qwen3.5-9b-q4km.json`, `schemas/`, `backend/idhazh/stages/work.py`, `backend/idhazh/stages/qualify.py`, `backend/idhazh/contracts/knobs/placement.py`, `backend/utilities/llama_argv.py`, `backend/utilities/pipeline_case_config.py`, `backend/tests/test_summarize.py`, `backend/tests/test_server_argv.py` |
| **C - the measuring clients** | 9 | 2 | `backend/utilities/measure_budgets.py`, `backend/utilities/measure_judge_call.py` |
| **D - the run record** | 10 | 2 | `backend/idhazh/fingerprint.py`, `docs/architecture/contracts/determinism.md` |

Wave 1 is PR A alone, because `backend/idhazh/llm/server.py` is the hub: six of the ten rows edit it. Wave 2 is B, C and D, which share no file with each other. With a pool of two, C and D go together and B follows, or B and C go together and D follows - either order is correct.

### 1b. Why rows 1 to 6 are one pull request

Rows 1, 2, 3, 4 and 6 all edit `server.py`, so they were never parallel. Row 5 is the one worth writing down: its files are the workflow files and `llama_argv.py`, which **look** disjoint from row 3's until you notice row 3 edits them too. Row 9 is the other: its two files really are disjoint, and it would still fail if started early, because it imports a name row 2 declares. **A readiness check that compares file lists cannot see an import.** Holding them in commit order removes both failures rather than managing them.

---

## 2. The contracts, declared before any code

`CLAUDE.md` Guardrail #3 puts the contract before the logic. A worker implements this section and invents nothing.

### C1 - `model_server.base_url`, the one setting this plan adds

| Property | Value |
| --- | --- |
| Where it is declared | A new `ModelServerConfig` in `backend/idhazh/contracts/knobs/model_server.py`, mounted on `AppConfig` in `backend/idhazh/contracts/app_config.py` beside `logging` and `observability` |
| Where the value lives | `config/idhazh.json`, a new top-level `"model_server"` block |
| Committed default | `"http://127.0.0.1:8080"` - the address this repository uses today, now written once as data |
| Shape | Scheme, host and port. Nothing else. A trailing `/` is accepted and dropped |
| Refused at load | No scheme, no host, or any path, query or fragment. The message names the field and the value |
| Why a path is refused | `_sibling()` builds every other route by replacing the whole path, so a prefix would survive on one route and vanish from four. A wrong answer is worse than an error. Supporting a prefix means changing `_sibling` and its golden test, which is a separate change with a separate reason |
| Why not an environment value | It would be the only setting in the project that is never committed and therefore never reviewed. Owner ruling, 2026-09-22 |
| Why one field and not a host plus a port | Two values can disagree about which server is meant. One cannot |

```json
  "logging": { ... },
  "model_server": {
    "base_url": "http://127.0.0.1:8080"
  },
  "models_file": "models/qwen3.5-9b-q4km.json",
```

### C2 - the address constants after row 2

`urlsplit` and `urlunsplit` are already imported at `server.py` line 35. Nothing new is imported for this.

```python
def resolve_base_url(declared: str) -> str:
    """Scheme, host and port of the server this run talks to.

    A path, query or fragment is refused rather than dropped: `_sibling` builds
    every other route by replacing the path, so a prefix would hold on one route
    and vanish from four.
    """
    parts = urlsplit(declared.rstrip("/"))
    if not parts.scheme or not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError(
            "model_server.base_url must be a scheme, a host and a port and nothing "
            f"else, not {declared!r}"
        )
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))
```

`DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` are composed from the resolved base. `DEFAULT_PORT` is deleted, and so is `DEFAULT_HEALTH`, which is defined at line 50 and read nowhere in the repository. An unread constant is the one most likely to drift out of step with the ones beside it, and no `health_url()` replaces it - a replacement would land with zero callers, which is the same defect with a newer name. It goes in when its first caller does.

**The import-time question, ruled.** `server.py` computes its constants when the module loads, and loading the whole config there would make every process that imports the LLM module read and validate `config/idhazh.json`. So the module keeps a fallback equal to the committed default, and the config value is applied by the caller that already holds settings. `llama_argv.py` and every stage entry point already load settings; that is where the value is read.

### C3 - how a workflow gets the address

No utility. `jq` is preinstalled on `ubuntu-latest`, and the composite action reads the committed config directly:

```bash
MODEL_BASE_URL="$(jq -r '.model_server.base_url' config/idhazh.json)"
```

Set once in `.github/actions/model-server/action.yml` as a step output, and read by all 22 probes in the five workflow files. The action's `port` input is deleted with `LLAMA_PORT`; `server_argv` reads the port back out of the base URL.

Once plan 44 moves these scripts into python, this line goes too - `config.load()` already returns it.

### C4 - the one loopback literal

Every address in `.github/` and in the three self-spawning instruments belongs to a program probing a server **it started on its own machine**. None of them reads `model_server.base_url`, and that is deliberate: a job that probes a foreign server while its own server sits unstarted is escalation trigger 1, and an instrument that measures a binary it is not running reports a number about the wrong thing.

One function, in `server.py` beside `resolve_base_url`, carries the literal for all of them:

```python
def loopback_url(port: int) -> str:
    """The address of a server started on this machine.

    Deliberately ignores `model_server.base_url`: the caller started this server
    and must probe that one, not whichever one the config names.
    """
    return f"http://127.0.0.1:{port}"
```

After rows 2 to 5, `git grep -c '127\.0\.0\.1' -- backend config .github` returns two: this function, and the committed default in `config/idhazh.json`. Both are named and both carry a comment saying why.

### C5 - the log record row 6 adds

| Property | Value |
| --- | --- |
| Where | Inside `post()`, the single place an item is sent. Not at module import, which fires in every process including test collection. Not `prove_the_entry`, which looks like a once-per-stage site and is not one - its only caller is `backend/utilities/prove_the_entry.py`, and no stage calls it |
| How often | Once per process per distinct address, by `functools.lru_cache` |
| Level and logger | `INFO`, on `LOG: Final = logging.getLogger("idhazh")`, the name eight other modules in `backend/idhazh/` already use. `logging` and `functools.lru_cache` are new imports in this file |
| What it must never print | **`parts.netloc`**. Netloc carries userinfo, so `http://user:token@box:8080` would write the token into the log verbatim. Use `parts.hostname` and `parts.port`. Never the path, the query, a header or any part of the payload (`CLAUDE.md` section 1b) |

```python
@lru_cache(maxsize=None)
def _note_origin(endpoint: str) -> None:
    """Say once which server this run is talking to.

    `hostname` and `port` rather than `netloc`: netloc carries userinfo, and a
    credential in an address must not reach a log record.
    """
    parts = urlsplit(endpoint)
    LOG.info("model server origin=%s://%s:%s", parts.scheme, parts.hostname, parts.port)
```

### C6 - the sampling block passes through

**The block is renamed and splatted whole.** `request` becomes `sampling`. `request_timeout_minutes` moves up to the model entry, because it is how long the client waits and never goes on the wire.

One helper, used by all four payload builders:

```python
def with_sampling(body: dict[str, Any], sampling: Mapping[str, Any]) -> dict[str, Any]:
    """This route's own keys, plus every key the model file declares.

    Nothing here names a control. The refused set is whatever the route already
    put in `body`, so a route that changes its controls changes this check with it.
    """
    clash = sorted(sampling.keys() & body.keys())
    if clash:
        raise ValueError(f"sampling may not set {', '.join(clash)} - this route sets it")
    return {**sampling, **body}
```

**No typed list of refused names anywhere.** A list would go stale the first time a builder changed, and a stale list either blocks a key that is now free or admits one that is now a control. Deriving the set from `body` costs one line and never rots. Owner ruling, 2026-09-22.

**Three identity rows leave `SETTING_KEYS`**: `temperature`, `top_p` and `seed` each map to themselves and gate every other key for no reason. The seven that remain are all local reads and none of them stands between the config and the wire:

| Surviving name | Reads from | Why it is read by name |
| --- | --- | --- |
| `n_ctx` | the `server` block | the pipeline does arithmetic on the window to build the truncation budget, and `config.py` refuses an entry that omits it |
| `n_batch`, `n_ubatch`, `n_threads`, `n_parallel`, `load_mode` | the `server` block | published on the run record under these names and drawn in words on a console panel, so a rename would move a published string |
| `request_timeout_minutes` | the model entry | sets the socket timeout; no server-side default bounds it |

**Two tests, neither per key.** One: a key no code mentions arrives in the payload verbatim. Two: a key that collides with a route's own control raises. Adding a sampler after this is a JSON edit with no code change and no new test.

**Two consequences to write down where they belong.** The config now speaks whatever the server speaks, so a key one runtime accepts and another rejects fails at request time rather than at config load - that is Table B row B2, taken deliberately. And the chat builder's docstring says "No token cap is sent, on either envelope"; it becomes "unless the model file names one", because `max_tokens` now passes through like everything else.

### C7 - the sampling values, approved 2026-09-22

Written at the values the pinned build already applies, read from its own help text. **Output does not change by a token.** What changes is that a build upgrade can no longer move them without a diff.

```json
  "quantisation": "Q4_K_M",
  "repo": "unsloth/Qwen3.5-9B-GGUF",
  "request_timeout_minutes": 22.1,
  "revision": "3885219b6810b007914f3a7950a8d1b469d598a5",
  "sampling": {
    "temperature": 0.2,
    "top_p": 1.0,
    "top_k": 40,
    "min_p": 0.05,
    "typical_p": 1.0,
    "repeat_penalty": 1.0,
    "repeat_last_n": 64,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "dry_multiplier": 0.0,
    "xtc_probability": 0.0,
    "mirostat": 0,
    "seed": 0
  },
  "server": {
    "--batch-size": 2048,
```

`top_k` at 40, `min_p` at 0.05 and `repeat_last_n` at 64 are llama.cpp's defaults, not this project's choices. Whether they are right for this corpus is Table B row B4 and needs a measurement; this row only stops them moving on their own.

**One verification the worker owes before the commit lands**: confirm the thirteen key spellings against the pinned build's `/props`, whose `default_generation_settings` names each one. Seconds, and it is the difference between a key that works and a key that is accepted and ignored.

### C8 - model slots get nouns

`CLAUDE.md` section 1a: a config is a self-descriptive noun, a function is a verb. The slot is a model, so it is named for what it is.

| Now | After |
| --- | --- |
| `models.summarize` | `models.summarizer` |

The role string is passed as `--role` and follows. `backend/idhazh/contracts/knobs/placement.py` carries a help string citing `models.summarize.inference` - a name that is already two renames stale - which is corrected in the same commit.

### C9 - the model file, and the value nothing reads

| Now | After | Why |
| --- | --- | --- |
| `LLAMA_WEIGHTS` | `MODEL_FILE` | It is a path to a GGUF file, which every tool calls the model: `--model` in llama.cpp and vLLM, `model_path` in Hugging Face. "Weights" means tensors everywhere else |
| `LLAMA_PORT` | **deleted** | The port lives inside `base_url`. Nothing is left for a second value to disagree with |
| `LLAMA_ROLE` | **deleted** | `start-llama-server.sh` line 59 sets it and nothing reads it. One occurrence in the repository |

The test harness constants `LLAMA_PORT_ENV`, `LLAMA_PORT_VALUE` and `LLAMA_PORT_READ` in `backend/tests/workflows/_harness.py` follow their variable out.

### C10 - the run record stops claiming a build it cannot see

Every field of `PipelineInputs` is read from this process: `runtime_build()` reads an environment value, `runner_class()` reads the runner's OS and architecture, `host_cpu()` reads this machine's processor. Point the pipeline at a second machine and the model runs there while the record describes here. Every field is well formed, so validation passes and the record is false. That matters because `MACHINE_INPUTS` is what a person reads when two runs disagree, and a record describing the wrong computer sends them to the wrong place.

**The fix needs no new state.** `UNRECORDED_BUILD = "build-not-recorded"` already exists at `backend/idhazh/fingerprint.py` line 46, and `runtime_build()` already degrades to it when nothing pins a build, because a developer machine usually pins nothing. So:

> When the resolved base URL is not loopback, `runtime_build()` returns `UNRECORDED_BUILD` rather than this machine's value.

No schema version stamp, no changelog entry, no migration, no new fixture. A record that says it does not know beats a record that says something false.

What stays out is reading the server's own `/props` and recording what actually answered - Table B row B1.

### C11 - the four sentences row 1 deletes

Each cites `CLAUDE.md` section 0a for a rule section 0a does not contain. **Every replacement states a fact about what the code does; none states a scope rule**, because an agent may not write a project rule for itself (`CLAUDE.md` section 1).

| id | File | The sentence, by its opening words | What replaces it |
| --- | --- | --- | --- |
| C11a | `backend/idhazh/llm/__init__.py`, second paragraph | "Nothing in this package reaches any origin but loopback. Hosted inference is a project non-goal..." | "The address this package talks to is one committed config value, `model_server.base_url`, read in one place. The OpenAI-shaped transport here exists because it is the format local runtimes already speak." |
| C11b | `backend/idhazh/llm/server.py`, module docstring, third line | "Nothing here is hosted - `CLAUDE.md` section 0a forbids that." | "The address is a committed config value and defaults to loopback. Nothing in this module starts a server." The rest of the paragraph, beginning "Two transports," is unchanged |
| C11c | `backend/idhazh/llm/server.py`, the `post()` docstring at line 962 | "Loopback only, by construction." | "One address for the whole run, and `_note_origin` says once which one." |
| C11d | `docs/how-to/run-the-pipeline.md`, lines 45 to 48 | "The summarize stage talks to `127.0.0.1:8080` and nothing else... There is no hosted inference anywhere in this project (section 0a)." | The paragraph in C12 |

C11c names a function row 6 creates, so row 1 leaves that one sentence and row 6 deletes it. Everything else in C11 lands in row 1.

### C12 - the documentation

**`docs/how-to/run-the-pipeline.md`**, replacing lines 45 to 48. This page, not `docs/architecture/summarize/model-boundary.md`: it is where the developer this plan is for actually reads, it is the page whose text becomes false, and it is not a page another live plan owns.

> The summarize stage talks to the address in `config/idhazh.json` under `model_server.base_url`, which is `http://127.0.0.1:8080` as committed. To use a server on another machine, change that value to its scheme, host and port. The server command reads the same value, so one edit moves both. Every job in `.github/` reads it from the committed file too.

**`docs/architecture/contracts/determinism.md`**, row 10. One sentence appended to the paragraph that already discusses `/props`, because that page owns the run record:

> When `model_server.base_url` is not loopback the run cannot see which build answered, so it records `UNRECORDED_BUILD` rather than this machine's; reconciling the record against the server's own `/props` is not done.

`python backend/utilities/doc_load.py` runs before and after each documentation edit. Both edits replace or extend existing text rather than adding a heading, so neither page is expected to move and no split test is owed.

### C13 - the commit order

One commit per row, in Reckoner order within each pull request. A worker who follows it never writes an import that points at a name which does not exist yet.

| PR | Commits, in order |
| --- | --- |
| A | 1 (text only, no behaviour) -> 2 -> 3 -> 4 -> 5 -> 6 |
| B | 7 -> 8 |
| C | 9 |
| D | 10 |

---

## 3. Row 1 - Delete the rule that is not written

**Scope.** Remove the four claims that `CLAUDE.md` section 0a forbids hosted inference, per C11.

**Files touched.** `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `docs/how-to/run-the-pipeline.md`.

**Acceptance gates.** `ruff check .` clean from the repository root. `python backend/utilities/doc_load.py` before and after. No new heading, so no split test owed. No browser smoke: nothing published changes.

**Oracle.** `git grep -n "section 0a" -- backend/idhazh/llm docs/how-to/run-the-pipeline.md` returns nothing.

**What the oracle cannot settle.** Whether the project should have the rule those sentences described. That is the owner question in section 0.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 1.1 | An agent makes this correction and reports it | A rule not in the contract cannot gate a plan, and deleting a wrong cross-reference changes no behaviour |
| 1.2 | Every replacement states a fact, never a scope rule | An agent may not write a project rule for itself (`CLAUDE.md` section 1) |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 1.R1 | Repoint the citation at Guardrail #11 | Guardrail #11 is about fetched text becoming instruction, not about where it is sent. Wrong in a new way | One line, and a false statement left in three files |
| 1.R2 | Write section 0a to make the comments true | Writes a project rule to justify four comments, and the wording would forbid the second machine this plan exists to allow | One line in `CLAUDE.md`, the owner's approval, and the plan's own purpose |

---

## 4. Row 2 - The address becomes one config field

**Scope.** Declare `ModelServerConfig`, mount it on `AppConfig`, add the committed default to `config/idhazh.json`, add `resolve_base_url`, compose the two endpoint constants from it, delete `DEFAULT_HEALTH`, and record the change in `docs/how-to/run-the-pipeline.md` per C1, C2 and C12.

**Files touched.** `backend/idhazh/contracts/knobs/model_server.py` (new), `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`, `docs/how-to/run-the-pipeline.md`.

**Acceptance gates.**

- `ruff check .` clean.
- The contract drift gate: `schemas/app-config.schema.json` regenerates byte-identical to what is committed.
- `pytest backend/tests/test_summarize.py backend/tests/workflows/test_model_server_jobs.py` green. Both, not either: the second proves CI is untouched.
- The existing assertion `completion_url("http://127.0.0.1:8181") == "http://127.0.0.1:8181/completions"` at `backend/tests/test_summarize.py` line 482 passes unchanged. It is the proof that sibling-route derivation did not move.
- A refusal test for each of the four bad shapes: no scheme, no host, a path, a query.
- `python backend/utilities/doc_load.py` before and after.

**Oracle.** With `config/idhazh.json` as committed, `DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` are byte-identical to `origin/main`. With `base_url` set to `http://192.168.1.20:9090`, both carry that host and port. `git grep -c DEFAULT_HEALTH` returns nothing.

**What the oracle cannot settle.** Whether a real second machine answers. Nothing in this repository binds a server off loopback, so the first genuine end-to-end proof is a person running a server elsewhere by hand. Escalation trigger 1 guards the half-done version of it.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 2.1 | A committed config field, not an environment value | An environment value is the only setting that never appears in a diff, so it is the only one that changes where article text goes with no review. Owner ruling, 2026-09-22 |
| 2.2 | One field holding scheme, host and port | Two fields can disagree about which server is meant |
| 2.3 | The module keeps a fallback equal to the committed default | Loading the whole config when `server.py` imports would make every process that touches the LLM module read and validate a config file |
| 2.4 | `DEFAULT_HEALTH` is deleted and nothing replaces it | Zero readers. A replacement would land with zero readers too |
| 2.5 | A path, query or fragment is refused, not dropped | `_sibling` replaces the whole path, so a prefix would hold on one route and vanish from four. A wrong answer is worse than an error |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 2.R1 | An environment value, `MODEL_BASE_URL` | Never committed, never reviewed. It was this plan's first design and the owner reversed it: a config line gets exactly the review a source constant gets, so the environment buys only the loss of the gate | One line, and the only unreviewed path in the project |
| 2.R2 | A host field plus a port field | Cannot express a scheme, and the two can disagree | Two fields, and a class of mismatch |
| 2.R3 | A `--endpoint` flag on all six stages that already take the argument | A real improvement and a bigger argument surface than this plan's reason needs. One config value reaches all 26 import sites at once | Six flags, six help strings, six tests. Worth revisiting when a run needs two different servers at once |

---

## 5. Row 3 - The port name disappears into the address

**Scope.** Delete `LLAMA_PORT` and `DEFAULT_PORT`. `server_argv` reads the port back out of the base URL. Every workflow probe reads the committed config through `jq`, per C3.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/utilities/llama_argv.py`, `.github/scripts/start-llama-server.sh`, `.github/actions/model-server/action.yml`, `.github/workflows/digest.yml`, `.github/workflows/idhazh-pipeline-tests.yaml`, `.github/workflows/llm-council.yml`, `.github/workflows/measure.yml`, `.github/workflows/validate.yml`, `backend/tests/workflows/_harness.py`, `backend/tests/workflows/test_model_server_jobs.py`, `docs/how-to/run-the-pipeline.md`, `docs/how-to/test-models-locally.md`, `docs/reference/ci-model-runtime.md`, `docs/reference/github-actions.md`.

**Acceptance gates.**

- `pytest backend/tests/workflows/` green. The port assertions there move to reading the port out of the base URL; they do not disappear.
- `shellcheck` clean on `start-llama-server.sh`.
- Every one of the 22 probes resolves to the same address the server was started on. Prove it by asserting, in the workflow test, that the probe expression and the server's port come from one source.
- The test that refuses a workflow writing a bare `127.0.0.1:8080` into an address keeps passing.

**Oracle.** `git grep -c LLAMA_PORT` returns nothing. `git grep -c '127\.0\.0\.1' -- .github` returns nothing.

**What the oracle cannot settle.** Whether a live dispatch still starts. The workflow test reads the files; it does not run the job. The first real dispatch after merge is the proof, and it is why this row carries escalation trigger 1.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 3.1 | Delete the name rather than rename it | The port lives inside `base_url`. A second value for it is a second thing to disagree |
| 3.2 | `jq` against the committed file, no helper script | A helper is a file to maintain for a one-line read, and `jq` is preinstalled on the runner. When plan 44 moves these scripts to python, the line disappears rather than being ported |
| 3.3 | The action's `port` input goes with it | An input that restates a config value is a second spelling |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 3.R1 | Rename to `MODEL_SERVER_PORT` | Renames 51 occurrences and leaves two values that can disagree about one server | 51 edits, and the disagreement stays |
| 3.R2 | A small utility printing the origin | Rejected by the owner: a utility for a one-line read of a committed file | About 20 lines, and a file to maintain |
| 3.R3 | Wait for plan 44 to move the scripts first | Either order works, and waiting blocks rows 4, 5 and 6 behind another plan's schedule | One plan's wait. Escalation trigger 4 keeps them from running together, which is the only real constraint |

---

## 6. Row 4 - One loopback literal in the whole repository

**Scope.** Add `loopback_url(port)` per C4 and route the six addresses in the three self-spawning instruments through it.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/utilities/measure_probability_mode.py`, `backend/utilities/measure_two_calls.py`, `backend/utilities/runtime_sweep.py`.

**Acceptance gates.** `ruff check .` clean. Each of the three instruments still starts its own server and still probes the one it started. A unit test asserting `loopback_url` ignores `model_server.base_url` entirely.

**Oracle.** `git grep -c '127\.0\.0\.1' -- backend config .github` returns exactly two: the body of `loopback_url`, and the committed default in `config/idhazh.json`. `backend/utilities/capture_server_argv.py` line 34 keeps a bare port constant and `backend/utilities/slot_probe.py` line 16 keeps a docstring example; neither is an address.

**What the oracle cannot settle.** Nothing outstanding. It is written as a list of survivors rather than as "zero", because zero is not the correct answer and an earlier draft of this plan claimed it was.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 4.1 | The spawners do not read the config | Each starts a server with `subprocess.Popen` and then finds it. Reading the config would let an instrument measure a server it is not running and report a number about the wrong binary |
| 4.2 | One function carries the literal | A literal with one home and a comment saying why is not a hardcoded value; thirty copies are |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 4.R1 | Make all eight utility addresses read the config | Six of them are how a parent finds the child it started | Six lines, and a class of silently wrong measurement |
| 4.R2 | Use `localhost` instead of `127.0.0.1` | A different literal, not fewer literals, and it adds a name resolution that can fail | Nothing, and nothing gained |

---

## 7. Row 5 - The model file, and the value nothing reads

**Scope.** Rename `LLAMA_WEIGHTS` to `MODEL_FILE` and delete `LLAMA_ROLE`, per C9.

**Files touched.** `.github/scripts/start-llama-server.sh`, `.github/actions/model-server/action.yml`, `backend/utilities/llama_argv.py`, the workflow files that set the weights value, and the workflow tests that read it.

**Acceptance gates.** `pytest backend/tests/workflows/` green. `shellcheck` clean. The weights value still reaches `server_argv` as `--model`.

**Oracle.** `git grep -c LLAMA_WEIGHTS` and `git grep -c LLAMA_ROLE` both return nothing.

**What the oracle cannot settle.** Nothing. `LLAMA_ROLE` has one occurrence and no reader, so its deletion cannot change behaviour.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 5.1 | `MODEL_FILE`, not `MODEL_WEIGHTS` | It is a path to a file. "Weights" means tensors in every other tool |
| 5.2 | `LLAMA_CPP_BUILD` and the rest keep their names | They name llama.cpp because the thing is llama.cpp. Table B row B3 |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 5.R1 | Rename every `LLAMA_*` name | Six of them correctly name the vendor's own artefacts. A blanket rename makes those six wrong | About 100 edits, and six names that then lie |
| 5.R2 | Leave `LLAMA_ROLE` alone | It is set on every dispatch and read by nothing. A reader will assume it matters | Nothing, and one permanent piece of misdirection |

---

## 8. Row 6 - The run says which server answered

**Scope.** Add the module logger and the one-shot origin record per C5, and apply C11c.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`.

**Acceptance gates.**

- `ruff check .` clean.
- A test driving `post()` with `http://user:token@box:8080/v1/chat/completions` and asserting `"token" not in caplog.text`.
- A test asserting a second `post()` to the same address writes no second record.

**Oracle.** Running the summarize stage prints exactly one `model server origin=` line at `INFO`, carrying scheme, host and port.

**What the oracle cannot settle.** Whether anybody reads it. It costs eight lines and it is the only thing in a run that can answer, after the fact, which machine produced the output.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 6.1 | Emitted from `post()`, memoised | Module import fires in every process including test collection. `post()` is the one place an item is sent |
| 6.2 | Not from `prove_the_entry` | Its only caller is a hand-run utility. No stage calls it, so the record would never fire in production |
| 6.3 | `hostname` and `port`, never `netloc` | Netloc carries userinfo. A credential must not reach a log record |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 6.R1 | Put the address on the run manifest | A persisted field is a version stamp, a changelog line, a migration and a fixture, for a value identical in every run CI makes | The full `CLAUDE.md` section 11 cost |
| 6.R2 | Log per item | Answers the same question thousands of times and buries everything else | Nothing, and a log nobody reads |

---

## 9. Row 7 - Sampling settings pass through, unmapped

**Scope.** Rename the `request` block to `sampling`, move `request_timeout_minutes` up to the model entry, add `with_sampling`, splat the block in all four payload builders, and remove the three identity rows from `SETTING_KEYS`, per C6 and C7.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/idhazh/config.py`, `backend/idhazh/contracts/knobs/models.py`, `config/models/qwen3.5-9b-q4km.json`, `schemas/`, `backend/tests/test_summarize.py`.

**Acceptance gates.**

- `ruff check .` clean, contract drift gate green.
- The thirteen key spellings confirmed against the pinned build's `/props` before the commit lands.
- Test one: a key no code mentions arrives in the payload verbatim.
- Test two: a key colliding with a route's own control raises, naming the key.
- `config.py`'s validation loop still refuses an entry with no `--ctx-size` and no timeout. It reads two names, neither of them one of the three being removed, so this is a check rather than a change.
- The four builders produce byte-identical payloads to `origin/main` for the committed config.

**Oracle.** Adding `"top_k": 7` to the model file changes the request body and needs no code edit. `SETTING_KEYS` has seven rows, all of them a real translation or a required read.

**What the oracle cannot settle.** Whether the three pinned defaults are right for this corpus. They are llama.cpp's choices written down, not measured ones. That is Table B row B4 and it needs a holdout measurement.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 7.1 | The block is splatted, not read key by key | A vendor changes its parameters on its own schedule. Per-key wiring makes every one of those changes a code change |
| 7.2 | No typed list of refused names | A list goes stale the first time a builder changes, and then it either blocks a key that is now free or admits one that is now a control. Deriving the set from the route's own body costs one line and never rots. Owner ruling, 2026-09-22 |
| 7.3 | Pin the three at the build's current values, not at disabled | Zero behaviour change today, and the drift hole closes. Moving them is then a config edit with a measurement |
| 7.4 | `sampling`, not `generation` or `request` | vLLM calls it `SamplingParams` and llama.cpp calls it `common_params_sampling`. "Request" describes the envelope, not the setting |
| 7.5 | `request_timeout_minutes` moves out of the block | It is how long the client waits. It never goes on the wire, so it is not a sampler |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 7.R1 | Add the ten missing keys to `SETTING_KEYS` | Keeps the per-key gate and pays it ten more times, then again for every key any runtime adds | Ten rows now, and a permanent maintenance tax |
| 7.R2 | A translation table across llama.cpp, vLLM and Ollama | Table B row B2. It is the wiring this row deletes, maintained against three projects | A table per runtime, and a merge every time any of them changes |
| 7.R3 | Splat with the controls first and let config win | A config key could turn off constrained decoding, which is a Guardrail #11 control | Nothing to write, and the decode control becomes optional |
| 7.R4 | Set the three samplers to disabled | Changes the sampler on every summary from the next run | A holdout quality measurement first, which is a different job |

---

## 10. Row 8 - Model slots get nouns

**Scope.** Rename the model slot key from a verb to a noun per C8, and correct the stale help string.

**Files touched.** `config/models/qwen3.5-9b-q4km.json`, `backend/idhazh/contracts/knobs/models.py`, `backend/idhazh/contracts/knobs/placement.py`, `backend/idhazh/config.py`, `backend/utilities/llama_argv.py`, `backend/utilities/pipeline_case_config.py`, `backend/idhazh/stages/work.py`, `backend/idhazh/stages/qualify.py`, `schemas/`, `backend/tests/test_server_argv.py`.

**Acceptance gates.** `ruff check .` clean, contract drift gate green, `pytest backend/tests` green. The role string passed as `--role` matches the config key exactly, asserted by a test.

**Oracle.** `git grep -n 'models\.summarize' -- backend config docs` returns nothing.

**What the oracle cannot settle.** Whether the other two slot names in C8 are the right ones. Only one slot exists today; the others are named so the pattern is set when a second arrives.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 8.1 | A noun per slot | `CLAUDE.md` section 1a: configs are nouns, functions are verbs |
| 8.2 | Its own row, after row 7 | Both rows edit the model file and the same contract module, so they are serial. Row 7 first because the settings shape is what a worker is likeliest to get wrong |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 8.R1 | `models.summarizer_model` | Says "model" twice; it is already under `models` | Nothing, and a longer name |
| 8.R2 | Leave the verb | One verb where the contract asks for a noun, in the key a second slot will copy | Nothing now, and the same rename later across more callers |

---

## 11. Row 9 - The two measuring clients read the address

**Scope.** Change the two `--base` defaults to the resolved base URL.

**Files touched.** `backend/utilities/measure_budgets.py`, `backend/utilities/measure_judge_call.py`.

**Acceptance gates.** `ruff check .` clean. Both scripts still parse their arguments and still accept an explicit `--base`. `.github/workflows/measure.yml` is not edited: it passes `--base` explicitly, so that job's behaviour is identical.

**Oracle.** Neither file contains a literal address.

**What the oracle cannot settle.** Nothing outstanding.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 9.1 | These two move and the three instruments do not | Neither contains a `subprocess.Popen`. They talk to a server somebody else started |
| 9.2 | The `--base` flag survives on both | An explicit flag beats a config value, and `measure.yml` relies on it |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 9.R1 | Leave both alone | These are the tools a developer on a second machine reaches for first | Nothing, and a flag typed every time |

---

## 12. Row 10 - The run record stops claiming a build it cannot see

**Scope.** When the resolved base URL is not loopback, `runtime_build()` returns `UNRECORDED_BUILD`, per C10. Record the remaining gap in `determinism.md` per C12.

**Files touched.** `backend/idhazh/fingerprint.py`, `docs/architecture/contracts/determinism.md`.

**Acceptance gates.**

- `pytest backend/tests` green.
- A unit test: with the committed config the stamp is unchanged; with a non-loopback base URL it is `UNRECORDED_BUILD`.
- No schema version stamp, no changelog entry, no migration. The sentinel already exists and already validates, so if this row needs any of the three, something is wrong and it stops.
- `python backend/utilities/doc_load.py` before and after.

**Oracle.** A run configured against a second machine writes a record whose `runtime_build` says it was not recorded, and every other field still validates.

**What the oracle cannot settle.** What the build actually was. Reading the server's `/props` and recording the truth is Table B row B1, with its gating measurement named there.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 10.1 | Degrade rather than refuse | A run against a second machine is the feature. Refusing it would undo rows 2 and 3 |
| 10.2 | Reuse `UNRECORDED_BUILD` | It exists, it validates, and it already means exactly this: nothing pinned the build. No new state is minted |
| 10.3 | `runner_class` and `host_cpu` are left alone | Both describe the machine that ran the pipeline, which is this one, and that is true either way. Only the build describes the model's machine |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 10.R1 | Record the defect in a sentence and fix nothing | It was this plan's first shape, on the belief that a new unrecorded state was needed. The state already exists, so the fix is smaller than the note explaining why it was deferred | Nothing to write, and a record that keeps saying something false |
| 10.R2 | Read `/props` and record what answered | The honest full fix, and a bigger one: a new field, a version stamp, a changelog line and a migration | The whole of `CLAUDE.md` section 11, plus a ruling on what a run does when the server it reached is not the one the record describes |
| 10.R3 | Refuse to run against a non-loopback address | Undoes the plan | Nothing, and the feature |

---

## See also

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - row 21, whose surviving half is this plan. Table C records the rest.
- [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) - hands every process-boundary value to this plan at its line 34, and shares the workflow files with PR A. Escalation trigger 4 keeps them apart.
- [`../docs/how-to/run-the-pipeline.md`](../docs/how-to/run-the-pipeline.md) - where the change is recorded and where the developer this plan is for reads.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - owns the run record that row 10 corrects.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the pool, readiness, and the execution stamp.
