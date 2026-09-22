# The model server's address becomes a committed config value

**Last Updated**: 2026-09-22

**Level**: 3 (`CLAUDE.md` section 6). It crosses python, committed config and the workflow files, and it adds a field to the top-level config contract, which regenerates a schema and a frontend type. No persisted payload changes shape. With the committed config unchanged, every address this repository builds is character-for-character what it builds today.

> Execute with [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md), parallel N = 1, AUTHOR-AND-STOP until the user authorises the run.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Why this plan exists** | `CLAUDE.md` Guardrail #11 was amended on 2026-09-22 and now says the model server's address **is** a committed config value. It is not one. It is three constants in [`backend/idhazh/llm/server.py`](../backend/idhazh/llm/server.py), one of which reads an environment value. The contract and the code disagree, and `CLAUDE.md` section 0d says the code is what changes. |
| **The second reason, which is a live defect** | `DEFAULT_ENDPOINT` is a **default argument**, bound when the module loads, at 18 sites. No caller anywhere overrides any of them. So `--base-url` in `backend/idhazh/cli.py` has never reached a server, and `stage_validate` does not take an address at all - it falls through to the module constant twice. The address is not a setting today; it is a global that looks like a parameter. |
| **The rule this plan is built on** | **A program that starts its own server probes loopback. A stage that only talks to one reads the address from the settings it already holds.** |
| **What changes for the reader** | Nothing. No published file, no page, no column. |
| **What changes in production** | Nothing, if `config/idhazh.json` is left as committed. |
| **Hard scope - in** | `model_server.base_url` as a config field; `resolve_base_url` and `resolve_endpoint`; the 18 default-argument sites resolved by their callers; `LLAMA_PORT` deleted; a refusal when a job starts a server on one address while the stage posts to another; the loopback literals outside `.github/` reduced to one function; `MODEL_FILE`; the dead role value deleted; one log record naming the server that answered; the run record stamping an unrecorded build when the address is not loopback; four sentences citing a rule that does not exist. |
| **Hard scope - out** | Table B. Four rows, each priced. The sampling block and the model-slot rename are **out**, and Table B row B1 is their brief. |
| **Supersedes** | The surviving half of row 21 of [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md). Table C records what that row asked for and what happened to each part. |
| **Depends on** | Nothing. [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) line 34 hands every process-boundary value to this plan by name, and shares `backend/idhazh/llm/server.py`, the workflow files, `backend/utilities/llama_argv.py` and `.github/scripts/start-llama-server.sh`. Run either side of plan 44's workflow pull request, never beside it. [`20260922-46-one-writer-for-the-corpus-plan.md`](20260922-46-one-writer-for-the-corpus-plan.md) shares nothing. |
| **ESCALATE triggers** | Five, below Table D. |
| **Execution** | Two pull requests, serial. **Peak one worker.** The second worker's place is authoring the plan in Table B row B1. |

### What a review pass changed, and why the worker should trust this version

An earlier draft of this plan would have taken production down. Three things it asserted were false and a worker following it would have found out at runtime.

- It said a config field would make the pipeline read the config. It would not have: `DEFAULT_ENDPOINT` is a default argument and nothing overrides it, so the field would have been written, validated, schema-generated and ignored. Row 3 exists because of that.
- It quoted a memory measurement as its reason for existing. [`docs/reference/pipeline-cost.md`](../docs/reference/pipeline-cost.md) line 708 retracts that number: "So the 96.0 percent above was never memory the kernel had to find." The machine is 15.61 GiB, what it holds runs 43.4 to 82.2 percent with a median of 52.3, and the least the kernel ever said it could still hand out was 2.76 GiB. The plan now rests on the contract, which needs no measurement.
- It had the workflow probes read the config. That is escalation trigger 1 in a costume: a non-loopback address would make every job health-check the foreign machine while the server it just started went unchecked. The probes stay loopback and row 5 adds the refusal instead.

### The rule this plan implements

`CLAUDE.md` Guardrail #11, amended by the owner on 2026-09-22: article text is sent only to a model process the operator of this run controls; the control is that the address is a committed config value, `model_server.base_url`, so moving it is a diff a person reads; an environment value is not an acceptable control for a destination.

Row 1 deletes the three code comments and the documentation paragraph that cite `CLAUDE.md` section 0a for a rule section 0a never carried, and cites the real one in their place.

### ESCALATE triggers

1. **Stop** if any row leaves a job starting a server on one address while the stage posts to another. Row 5 is the control; a design that needs it removed is a different plan.
2. **Stop** if anything would make `backend/idhazh/llm/` read `config/`. It sits below config in the dependency graph - [`backend/idhazh/config.py`](../backend/idhazh/config.py) imports `SETTING_KEYS` from `server.py`, so the arrow only points one way. Every function that needs the address has `settings` in its own signature already.
3. **Stop** if any row would read `config/idhazh.json` with no config root. Three workflows run production stages against `backend/var/candidate-config`, so a zero-argument load returns the wrong file and the run posts to an address nobody chose.
4. **Stop** if PR A is ready at the same time as plan 44's workflow pull request. Either order, never together.
5. **Stop** if any row would raise a runner budget figure. The 6 hour job limit and the 1 GB site limit are GitHub's and cannot be moved (Guardrail #2).

### Table B - Hard scope - out

| id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | **The sampling block and the model-slot rename.** This row is the brief for the plan that carries them, authored next. | A sampling key added to a model file today validates and is dropped in silence: `server.py` reads `temperature`, `top_p` and `seed` by name and nothing else, so ten of the thirteen settings llama.cpp applies are the build's choice rather than this project's. Two stale names stay stale. | Nothing but the writing. It shares `server.py` with this plan, so it follows rather than runs beside. **What the owner already approved, and what the review found - all of it belongs in that plan:** the `request` block becomes `sampling` and is splatted whole; the thirteen keys at the build's own values, which changes no output; `request_timeout_minutes` moves up to the model entry. **And what a worker must not lose:** `request` is declared on `ModelRef`, not `ModelEntry`, and published `run.json` files carry `model_ref.request` - rename on the entry only and leave the recorded mapping, which is what `inference` and `draft` already do. `ModelRole.SUMMARIZE = "summarize"` is a persisted enum value in 127 places across 35 run records - pin the value, move the python name and the config key. Five committed model files carry the block, not one. Ten `tests/fixtures/request-bodies/*.json` goldens move. `continued_completion_payload` is a derivation of `completion_payload` (`{**first, ...}`), so only the three constructing builders may apply the splat or it raises on every summarize-and-plan call. `sampling_spelling` in `fingerprint.py` records three names onto every run record, so the splat must record the whole block - a dict field, so more keys is an expand with no migration, and what is owed is a version stamp and one changelog line. The refused set is the route's own body keys **plus the disablers declared on the line beneath each control** - `grammar_lazy` and `grammar_triggers` beside `grammar`, `response_format` beside `json_schema`, `json_schema` and `n_predict` beside the chat route's pair, and `logit_bias`, `ignore_eos` and `samplers` on all three - because a decode control has more than one name and `grammar_lazy` disables a grammar without appearing in the body at all. `max_tokens` from config fails chat-route items with `OUTPUT_TRUNCATED` on the path that runs the injection canaries, and the repair path never sees a chat reply. `samplers` carries the chain order, so thirteen values pinned with the order free does not mean a build upgrade cannot move them. Finally, the clash check is a pure function of the config and the route, so it runs at config load as well as at build time - otherwise a typo fails on the first item of every shard after each has already restored and loaded the weights. |
| B2 | The 22 loopback literals in `.github/` | Nothing today. Every one is a probe against a server the same job just started on the same machine. Reading the config there is the failure row 5 exists to prevent, and it is not implementable anyway: the composite action declares no outputs, only two of the five workflows use it, and three of them run against a different config root. | A job that talks to a server it did not start. That is a different design and it brings the readiness probe, the secret handling and the failure mode with it. |
| B3 | Reconciling the server's `/props` against the fingerprint | Partly paid. Row 9 makes the run stamp an unrecorded build rather than a false one. What stays out is reading the server's own answer and recording what actually replied. | A run that needs to prove which build answered rather than only to avoid claiming the wrong one. Gating measurement: one `/props` read against the pinned build, seconds. |
| B4 | Renaming `LLAMA_CPP_BUILD`, `LLAMA_CPP_ASSET`, `LLAMA_CPP_SHA`, `LLAMA_BIN`, `llama-cpp-pin.sh`, `install-llama-runtime.sh` | Nothing. Each names llama.cpp because the thing is llama.cpp. `CLAUDE.md` section 0b bans a vendor name used as this project's vocabulary, not the vendor's name for the vendor's own artefact. | A second runtime, which makes those names wrong. |

### Table C - What plan 39 row 21 asked for, and what happened to each part

| id | Asked for | Outcome |
| --- | --- | --- |
| C1 | One request builder instead of four | **Refused.** Four shapes carrying four different Guardrail #11 controls: `response_format` with a `json_schema` on the chat route, a top-level `json_schema` on the plain completion route, a `grammar` on the third, and the fourth is a derivation of the second that inherits its body. Collapsing them collapses the controls. |
| C2 | Move to the widely supported `/v1/completions` route | **Refused by a measurement** at `server.py` lines 58 to 66: both completion routes ignore `response_format` and honour a top-level `json_schema`, on build b10444-5f754ea0e as of 2026-09-12. The chat route is not in that measurement and does honour `response_format`. That comment also says no workflow pins a llama.cpp build, which is now false - [`.github/scripts/llama-cpp-pin.sh`](../.github/scripts/llama-cpp-pin.sh) pins `b10598`. Correcting that sentence belongs to Table B row B1's plan, which edits the block. |
| C3 | Delete three slot columns | **Refused.** `backend/utilities/slot_probe.py` is their named instrument. |
| C4 | Stamp the decode mode | **Done** in pull request #1036. |
| C5 | Stop naming a server in source | **This plan.** |

### Table D - Measured on `origin/main`, and what each number means

| id | Reading | Number | What it means |
| --- | --- | --- | --- |
| D1 | Sites where an address is a default argument bound at module load | 18 | Eight in `server.py`, seven in stages and utilities, three argparse defaults. Row 3's whole job. `DEFAULT_COMPLETION_ENDPOINT` is a default argument zero times. |
| D2 | Callers anywhere that override one of those 18 | **0** | Not in `backend/`, not in `.github/`. The address is a global wearing a parameter's clothes. |
| D3 | Production call sites that rely on a `server.py` default | 2 | `stages/validate.py` line 128 and `utilities/prove_the_entry.py` line 19. The second already loaded settings one line above. |
| D4 | Readers of `DEFAULT_HEALTH` | 0 | Defined, used nowhere. Row 2 deletes it. |
| D5 | Occurrences of `LLAMA_PORT` | 69 lines in 19 files, excluding `TODO/` | Row 4 deletes the name rather than renaming it: the port lives inside `base_url`, so nothing is left for a second value to disagree with. |
| D6 | Cost of one `config.load()` | 18.3 to 111.9 ms, median 67.5, n=30 warm, on a developer Windows box | Once per process is not a cost worth designing around. The reason `server.py` still must not call it is the config root, not the time - see escalation trigger 3. |
| D7 | Workflows that run a production stage against a config root that is not `config/` | 3 of 5 | `validate.yml`, `measure.yml` and the pipeline-test case script all pass `backend/var/candidate-config` or a case root. |
| D8 | Workflows that reach `.github/scripts/start-llama-server.sh` | 2 of 5 | Only `digest.yml` and `llm-council.yml`, through the composite action. The other three spawn the binary inline. This is why row 5's refusal lives in `llama_argv.py`, which all five reach. |
| D9 | Reads of `LLAMA_ROLE` | 0 | Set by `start-llama-server.sh` line 59, read nowhere; the role arrives as `--role`. Row 7 deletes it. |
| D10 | Loopback literals in the repository, by scope | 22 in `.github/`, 6 in three self-spawning instruments, 2 in the measuring clients | Rows 2 and 6 take the last eight to one function plus one committed default. The `.github/` 22 stay, by Table B row B2. Do not count `backend/tests/`: it holds about 32 more, all about URL sanitisation and nothing to do with the model server. |

---

## 1. Status Reckoner

Statuses: PENDING, IN PROGRESS, BLOCKED, DONE. A row's status is stamped by the change that moves it, in that same change. Workers update their own line and nothing else.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Delete the rule that is not written | none | A | PENDING | - | - | - |
| 2 | The address becomes one config field | 1 | A | PENDING | - | - | - |
| 3 | Every caller names the address it means | 2 | A | PENDING | - | - | - |
| 4 | The port name disappears into the address | 3 | A | PENDING | - | - | - |
| 5 | A job refuses to start a server nobody will talk to | 4 | A | PENDING | - | - | - |
| 6 | The loopback literals outside the workflows become one function | 4 | A | PENDING | - | - | - |
| 7 | The model file, and the value nothing reads | 4 | A | PENDING | - | - | - |
| 8 | The run says which server answered | 3 | A | PENDING | - | - | - |
| 9 | The run record stops claiming a build it cannot see | 2 | B | PENDING | - | - | - |

### 1a. The two pull requests

| PR | Rows | Wave |
| --- | --- | --- |
| **A - the address** | 1 to 8 | 1 |
| **B - the run record** | 9 | 2 |

**Peak worker count: one.** `backend/idhazh/llm/server.py` is the hub - six of the nine rows edit it - and PR B imports a name PR A declares. There is no honest parallelism here, and manufacturing some would buy a scheduling bug instead of a gating cycle. The second worker's place is authoring the plan in Table B row B1, which can start immediately and merges after this one.

PR A's files: `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `backend/idhazh/cli.py`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/model_server.py` (new), `config/idhazh.json`, `schemas/app-config.schema.json`, `frontend/src/contracts/app-config.ts`, the six stage files named in C3, `backend/utilities/{llama_argv,slot_probe,prompt_loop,prove_the_entry,runtime_sweep,measure_probability_mode,measure_two_calls,measure_budgets,measure_judge_call}.py`, all five `.github/` workflow files plus `actions/model-server/action.yml` and `scripts/start-llama-server.sh`, `backend/tests/{test_summarize.py,workflows/_harness.py,workflows/test_model_server_jobs.py}`, `docs/how-to/run-the-pipeline.md`.

PR B's files: `backend/idhazh/fingerprint.py`, `backend/idhazh/cli.py`, `backend/idhazh/stages/work.py`, `backend/idhazh/stages/qualify.py`, `backend/tests/test_fingerprint.py`, `docs/architecture/contracts/determinism.md`.

---

## 2. The contracts, declared before any code

`CLAUDE.md` Guardrail #3 puts the contract before the logic. A worker implements this section and invents nothing.

### C1 - `model_server.base_url`, the one setting this plan adds

| Property | Value |
| --- | --- |
| Declared in | A new `ModelServerConfig` in `backend/idhazh/contracts/knobs/model_server.py`, mounted on `AppConfig` in `backend/idhazh/contracts/app_config.py` beside `observability`. Twenty-one knobs modules already exist; this follows them. |
| Value lives in | `config/idhazh.json`, a new top-level `"model_server"` block |
| Committed default | `"http://127.0.0.1:8080"` - today's address, written once as data |
| Shape | Scheme, host **and port**. Nothing else. A trailing `/` is accepted and dropped |
| Refused at load | No scheme, no host, **no port**, an out-of-range or non-numeric port, or any path, query or fragment |
| Why the port is required | Row 4 has `server_argv` read the port back out of this value. `http://host` parses cleanly and yields `port is None`, which would bind `--port None`. A validator that does not touch `parts.port` does not catch it |
| Why a path is refused | `_sibling` builds every other route by replacing the whole path, so a prefix would survive on one route and vanish from four. A wrong answer is worse than an error |
| Regenerates | `schemas/app-config.schema.json` **and** `frontend/src/contracts/app-config.ts`. The drift gate fails on either if both are not regenerated |
| Owes a changelog | `AppConfig` carries an enforced `__changelog__`. One line: a new field is an expand, so no migration is owed |

```json
  "logging": { ... },
  "model_server": {
    "base_url": "http://127.0.0.1:8080"
  },
  "models_file": "models/qwen3.5-9b-q4km.json",
```

### C2 - the two resolvers

Both pure. No config import, no cache, no module-level state. `urlsplit` and `urlunsplit` are already imported at `server.py` line 36; nothing new is imported.

```python
def resolve_base_url(declared: str) -> str:
    """Scheme, host and port of the server this run talks to.

    A path, query or fragment is refused rather than dropped: `_sibling` builds
    every other route by replacing the path, so a prefix would hold on one route
    and vanish from four. A missing port is refused because `server_argv` binds
    the port it reads back out of this value.
    """
    parts = urlsplit(declared.rstrip("/"))
    if not parts.scheme or not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError(
            "model_server.base_url must be a scheme, a host and a port and nothing "
            f"else, not {declared!r}"
        )
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError(f"model_server.base_url names no usable port: {declared!r}") from error
    if port is None:
        raise ValueError(f"model_server.base_url must name a port, not {declared!r}")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def resolve_endpoint(base_url: str) -> str:
    """Where an item is posted, on the server a base URL names."""
    return resolve_base_url(base_url) + _CHAT_PATH
```

`_CHAT_PATH: Final = "/v1/chat/completions"` joins `_COMPLETION_PATH` at line 66, and `DEFAULT_ENDPOINT` is composed from it so nothing spells the route twice. `DEFAULT_HEALTH` is deleted: it has zero readers, and no `health_url()` replaces it, because a replacement would land with zero readers too. It goes in when its first caller does.

**There is no `configured_endpoint()` and `server.py` never reads the config.** Every function that needs the address already has `settings` in its own signature. `backend/idhazh/llm/` sits below config in the dependency graph, and a function-local import to dodge the cycle would be the codebase saying the arrow points the wrong way. A zero-argument `config.load()` would also read `config/idhazh.json` while three workflows run the stage under `backend/var/candidate-config` - the control failing quietly rather than loudly. Escalation trigger 2 and 3.

### C3 - the eighteen sites, and what each becomes

This is the row that makes the config field mean anything. Without it, row 2 ships a field, a schema, a validator and a frontend type, and the pipeline keeps posting to the module constant.

| Group | Sites | Becomes | Caller edits owed |
| --- | --- | --- | --- |
| **The eight in `server.py`** - `post`, `props_url`, `completion_url`, `apply_template_url`, `tokenize_url`, `props`, `derive_turn_markers`, `prove_the_entry` | lines 959, 984, 989, 994, 999, 1004, 1436, 1537 | **Required. No default, no sentinel.** The address is always the caller's | **Two**: `stages/validate.py` line 128 and `utilities/prove_the_entry.py` line 19. The second already loads settings one line above |
| **The seven in stages and one utility** - `stage_judge_item_pairs`, `stage_qualify`, `stage_qualify_canaries`, `two_calls_one_item`, `_summarize_one`, `stage_work`, `judge_calls` | `judge_item_pairs.py:111`, `qualify.py:409`, `qualify_canaries.py:49`, `two_calls.py:431`, `validate.py:40`, `work.py:301`, `measure_judge_call.py:334` | `str \| None = None`, resolved on the function's **first line**: `endpoint = model_endpoint or resolve_endpoint(settings.app.model_server.base_url)` | none |
| **The three argparse defaults** | `cli.py:518`, `prompt_loop.py:592`, `slot_probe.py:192` | `default=None`, resolved after the parse where settings exist. `slot_probe.py` gains a `--config-root`, following `llama_argv.py` and `prove_the_entry.py` | none |

**First-line resolution is mandatory, not stylistic.** Two `functools.partial` sites bind the endpoint eagerly - `judge_item_pairs.py:148` and `measure_judge_call.py:357` both do `partial(post, endpoint=completion_url(base_url), ...)`. A `None` that reaches `completion_url` raises `TypeError` inside `_sibling`.

**Two live defects this row fixes, which a reader must not mistake for a no-op.**

- `stage_validate` at `validate.py:102` takes no address at all. Line 128 and line 138 both fall through to the module constant. It gains one, threaded from its settings.
- `--base-url` at `cli.py:518` is dead: the name appears nowhere else in the file, and the only production caller of the judge stage does not pass it. **Delete the flag.** The stage resolves from settings like every other one.

**Two properties the worker can rely on, both checked**: nothing in `backend/` passes `endpoint=None`, `base_url=None` or `model_endpoint=None` today; and no test introspects a signature or `__defaults__` of any of the eighteen. The two tests that assert on the constants read them directly and are untouched.

**If any one of the seven does not have `settings` in scope, stop.** Threading a config object into a function that did not have one is escalation trigger 2, not a row's business.

### C4 - the one loopback literal outside the workflows

Every address in the three self-spawning instruments belongs to a program probing a server it started with `subprocess.Popen`. None of them reads `base_url`, deliberately: an instrument that measured a server it was not running would report a number about the wrong binary.

```python
def loopback_url(port: int) -> str:
    """The address of a server started on this machine.

    Deliberately ignores `model_server.base_url`: the caller started this server
    and must probe that one, not whichever one the config names.
    """
    return f"http://127.0.0.1:{port}"
```

All three instruments already import from `idhazh.llm.server`, so this adds no dependency. The two measuring clients are different - `measure_budgets.py` and `measure_judge_call.py` start no server, so their `--base` defaults resolve from settings like row 3's other sites.

After rows 2, 3 and 6, `git grep -n '127\.0\.0\.1' -- backend/idhazh backend/utilities config` returns exactly two lines: the body of `loopback_url`, and the committed default in `config/idhazh.json`. `.github/` keeps its 22 by Table B row B2. `backend/utilities/capture_server_argv.py` line 34 keeps a bare port constant and `backend/utilities/slot_probe.py` line 16 keeps a shell example, and neither is an address.

### C5 - the refusal, and where it must live

The one control that makes escalation trigger 1 enforceable: a job that starts a server on loopback while the stage posts somewhere else fails at start-up rather than after the weights load.

**It goes in `backend/utilities/llama_argv.py`, inside `argv_for`.** Not in `action.yml`, which sees neither fact. Not in `start-llama-server.sh`, which only two of the five workflows reach - the other three spawn the binary inline and would escape it entirely. `argv_for` is reached by all five, and it already calls `config.load(config_root)` on **the root this job will actually run under**, which is the whole point: three workflows run against `backend/var/candidate-config`.

```python
    settings = config.load(config_root)
    declared = resolve_base_url(settings.app.model_server.base_url)
    if declared != loopback_url(port):
        raise SystemExit(
            f"this job binds {loopback_url(port)} and the stage posts to {declared}. "
            "A readiness probe that clears a server nobody talks to is worse than no "
            f"probe - set model_server.base_url in {config_root} to match, or start "
            "no server here"
        )
```

The three self-spawning instruments bypass `argv_for` and call `server_argv` directly. They are correctly outside this: they take `loopback_url(port)` and no refusal.

### C6 - the log record

| Property | Value |
| --- | --- |
| Where | Inside `post()`, the one place an item is sent. Not module import, which fires during test collection. Not `prove_the_entry`, whose only caller is a hand-run utility |
| Cache key | **The origin, not the endpoint.** The qualification process posts to the chat route and to `completion_url(endpoint)`, so an endpoint key writes the identical line twice with nothing to say why |
| Level and logger | `INFO`, on `LOG: Final = logging.getLogger("idhazh")`, the name eight other modules use. `logging` and `functools.lru_cache` are new imports in this file |
| Must never print | **`parts.netloc`.** It carries userinfo, so `http://user:token@box:8080` would write the token verbatim. Use `parts.hostname` and `parts.port`. Never the path, the query, a header or any part of the payload |

```python
@lru_cache(maxsize=None)
def _note_origin(origin: str) -> None:
    """Say once which server this run is talking to."""
    LOG.info("model server origin=%s", origin)
```

`post()` computes the origin with `urlsplit` and passes it. **The test does not open a socket** (Guardrail #7): call `_note_origin` directly with `http://user:token@box:8080` and assert `"token" not in caplog.text`. For the once-per-origin claim, call `_note_origin.cache_clear()` first - `lru_cache` is process-global and would otherwise leak into every later test in the process.

`post()` is the only path that sends article text. `_ask` is a second send path and carries only this module's own probe constants; `token_pieces` would send whatever it is handed and has zero callers. That last sentence belongs in the docstring so the next person to give it a caller sees the constraint.

### C7 - the four sentences row 1 deletes

Each cites `CLAUDE.md` section 0a for a rule section 0a does not contain. The rule they were reaching for now exists, so each replacement cites the real one.

| id | File | The sentence, by its opening words | What replaces it |
| --- | --- | --- | --- |
| C7a | `backend/idhazh/llm/__init__.py`, second paragraph | "Nothing in this package reaches any origin but loopback. Hosted inference is a project non-goal..." | "The address this package talks to is one committed config value, `model_server.base_url`. Article text goes only to a model process this run's operator controls (`CLAUDE.md` Guardrail #11). The OpenAI-shaped transport here exists because it is the format local runtimes already speak." |
| C7b | `backend/idhazh/llm/server.py`, module docstring, third line | "Nothing here is hosted - `CLAUDE.md` section 0a forbids that." | "The address is a committed config value and defaults to loopback. Nothing in this module starts a server, and nothing here reads the config - every caller brings the address it means." The rest of the paragraph, beginning "Two transports," is unchanged |
| C7c | `backend/idhazh/llm/server.py`, the `post()` docstring | "Loopback only, by construction." | "One address for the whole run, and `_note_origin` says once which one." |
| C7d | `docs/how-to/run-the-pipeline.md`, lines 45 to 48 | "The summarize stage talks to `127.0.0.1:8080` and nothing else... There is no hosted inference anywhere in this project (section 0a)." | The paragraph in C8 |

C7c names a function row 8 creates, so row 1 leaves that sentence and row 8 deletes it. Everything else in C7 lands in row 1.

### C8 - the documentation

**`docs/how-to/run-the-pipeline.md`**, replacing lines 45 to 48:

> The summarize stage talks to the address in `config/idhazh.json` under `model_server.base_url`, which is `http://127.0.0.1:8080` as committed. To use a server on another machine, change that value to its scheme, host and port. The server command reads the same value from the same config root, and refuses to start a server on one address while the stage posts to another. Every job in `.github/` starts its own server and probes it on loopback.

**`docs/architecture/contracts/determinism.md`**, row 9. One sentence appended to the paragraph that already discusses `/props`:

> When `model_server.base_url` is not loopback the run cannot see which build answered, so it records `UNRECORDED_BUILD` rather than this machine's; reconciling the record against the server's own `/props` is not done.

`python backend/utilities/doc_load.py` runs before and after each documentation edit. Both edits replace existing text rather than adding a heading, so neither page is expected to move and no split test is owed.

### C9 - the run record rule

Every field of `PipelineInputs` is read from this process. Point the pipeline at a second machine and the model runs there while the record describes here: every field is well formed, so validation passes and the record is false.

**No new state is minted.** `UNRECORDED_BUILD = "build-not-recorded"` exists at `backend/idhazh/fingerprint.py` line 46 and `runtime_build()` already degrades to it when nothing pins a build.

> `runtime_build()` gains a second argument, the resolved base URL, and returns `UNRECORDED_BUILD` when that address is not loopback.

Its three callers pass it: `cli.py:212`, `stages/work.py:324`, `stages/qualify.py:434`. All three already hold settings. No version stamp, no changelog entry, no migration, no new fixture - and if the row turns out to need any of the three, that is a finding and the row stops.

**One consequence to write down rather than discover.** `runtime_build` is in `MACHINE_INPUTS`, so two runs against two different foreign builds both stamp the sentinel and the determinism guard sees no move. That is pre-existing for a developer machine that pins nothing; row 9 widens it to the configuration this plan creates. It is named in `determinism.md` by C8 and it is Table B row B3's reason to exist.

### C10 - the commit order

One commit per row, in Reckoner order. A worker who follows it never writes an import pointing at a name that does not exist yet.

| PR | Commits, in order |
| --- | --- |
| A | 1 (text only, no behaviour) -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 |
| B | 9 |

**Two rules that bind every gate in this plan.** A test that reads `config/idhazh.json` goes red the day an operator uses the feature, which is `CLAUDE.md` section 13's "a test goes red because somebody edited the tree" - so **every test here builds its config from a fixture**. And `git grep -c` prints one line per matching file rather than a number, so an oracle that wants a count uses `git grep -n ... | Measure-Object -Line`.

---

## 3. Row 1 - Delete the rule that is not written

**Scope.** Remove the four claims that `CLAUDE.md` section 0a forbids hosted inference, per C7, and cite Guardrail #11 instead.

**Files touched.** `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `docs/how-to/run-the-pipeline.md`.

**Acceptance gates.** `ruff check .` clean from the repository root. `python backend/utilities/doc_load.py` before and after. No new heading, so no split test owed. No browser smoke: nothing published changes.

**Oracle.** `git grep -n "section 0a" -- backend/idhazh/llm docs/how-to/run-the-pipeline.md` returns nothing.

**What the oracle cannot settle.** Nothing outstanding. The rule is written and dated.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 1.1 | Each replacement cites Guardrail #11 | The rule those four sentences reached for is now written, so the replacement points at it rather than at nothing |
| 1.2 | C7c waits for row 8 | Its replacement names `_note_origin`, which row 8 creates |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 1.R1 | Leave the sentences and add hosted inference to section 0a | It would forbid the second machine the amended Guardrail #11 explicitly allows | One line, and a contradiction inside `CLAUDE.md` |

---

## 4. Row 2 - The address becomes one config field

**Scope.** Declare `ModelServerConfig`, mount it, add the committed default, add `resolve_base_url` and `resolve_endpoint`, compose `DEFAULT_ENDPOINT` from `_CHAT_PATH`, delete `DEFAULT_HEALTH`, and record the change in the how-to page. Contracts C1, C2, C8.

**Files touched.** `backend/idhazh/contracts/knobs/model_server.py` (new), `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `frontend/src/contracts/app-config.ts`, `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`, `docs/how-to/run-the-pipeline.md`.

**Acceptance gates.**

- `ruff check .` clean; `mypy backend` clean.
- **Contract drift gate green**: `schemas/app-config.schema.json` AND `frontend/src/contracts/app-config.ts` both regenerate byte-identical to what is committed. Regenerating only the schema fails the gate.
- `AppConfig.__changelog__` gains one line. A new field is an expand, so no migration is owed and none is written.
- Six refusal tests, each built from a fixture string, never from `config/idhazh.json`: no scheme, no host, **no port**, a port out of range, a non-numeric port, a path.
- `pytest backend/tests/test_summarize.py backend/tests/workflows/test_model_server_jobs.py` green. Both: the second proves CI is untouched.
- `completion_url("http://127.0.0.1:8181") == "http://127.0.0.1:8181/completions"` at `backend/tests/test_summarize.py` line 482 passes unchanged. It is the proof that sibling-route derivation did not move.
- `python backend/utilities/doc_load.py` before and after.

**Oracle.** `resolve_base_url` on the committed default returns it unchanged; `DEFAULT_ENDPOINT` is byte-identical to `origin/main`; `resolve_base_url("http://host")` raises naming the missing port; `git grep -n DEFAULT_HEALTH` returns nothing.

**What the oracle cannot settle.** Whether anything actually reads the field. It does not, until row 3. That is why row 3 exists and why this row must not be merged alone.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 2.1 | A committed config field, not an environment value | `CLAUDE.md` Guardrail #11, amended 2026-09-22. An environment value is the only setting that never appears in a diff |
| 2.2 | One field carrying scheme, host and port | Two values can disagree about which server is meant |
| 2.3 | The port is required and range-checked | Row 4 reads it back out to bind the server. `http://host` parses cleanly and would bind `--port None` |
| 2.4 | `server.py` never reads the config | It sits below config in the dependency graph, and a zero-argument load would read the committed file while three workflows run under a candidate root |
| 2.5 | `DEFAULT_HEALTH` deleted, nothing replaces it | Zero readers. A replacement would land with zero readers too |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 2.R1 | An environment value | Never committed, never reviewed. It was this plan's first design and the owner reversed it | One line, and the only unreviewed destination in the project |
| 2.R2 | A `configured_endpoint()` in `server.py`, cached, with a function-local config import | The local import is a cycle dodge that works and silently half-builds a module if anything ever calls it during import; the cache would be the first cache of a file's contents in the repository and owes three new `cache_clear()` obligations; and a zero-argument load reads the wrong config root in three of five workflows | One function, one import trick, three cache-clear sites, and a control that fails quietly |
| 2.R3 | A host field plus a port field | Cannot express a scheme, and the two can disagree | Two fields, and a class of mismatch |

---

## 5. Row 3 - Every caller names the address it means

**Scope.** The eighteen default-argument sites of contract C3. Eight become required parameters, seven resolve from the settings they already hold, three argparse defaults resolve after the parse. Thread an address into `stage_validate`, which has none. Delete the dead `--base-url` flag.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/idhazh/cli.py`, `backend/idhazh/stages/{judge_item_pairs,qualify,qualify_canaries,two_calls,validate,work}.py`, `backend/utilities/{measure_judge_call,prompt_loop,slot_probe,prove_the_entry}.py`, `backend/tests/test_summarize.py`.

**Acceptance gates.**

- `ruff check .` clean; `mypy backend` clean. mypy is the gate that proves all eighteen were found: a required parameter nobody passes is a type error.
- **The integration test that would have caught the defect this plan exists to fix**: a fixture config carrying `base_url: "http://192.168.1.20:9090"`, one stage run with **no endpoint argument**, and an assertion that the outbound URL carries that host. Driven by the recorded-response harness; no socket opens.
- `pytest backend/tests` green.
- The two `functools.partial` sites still bind a resolved string, never `None`.

**Oracle.** `git grep -n '= DEFAULT_ENDPOINT' -- backend` returns nothing. Changing `base_url` in a fixture config changes where the stage posts.

**What the oracle cannot settle.** Whether a real second machine answers. Nothing in this repository binds a server off loopback, so the first genuine end-to-end proof is a person running one elsewhere by hand.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 3.1 | The eight in `server.py` become required, with no sentinel | The address is always the caller's. Only two call sites rely on a default today, and one of them already holds settings |
| 3.2 | The other ten resolve on the function's first line | Two `partial` sites bind the endpoint eagerly, so a `None` travelling further raises inside `_sibling` |
| 3.3 | `--base-url` is deleted, not wired | The name appears nowhere else in `cli.py` and the judge stage's only production caller never passed it. It has never reached a server |
| 3.4 | `stage_validate` gains an address | It takes none today and falls through to the module constant twice. This is the one place in the row where behaviour genuinely changes, and it is a fix |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 3.R1 | Keep the defaults and have them read the config | Rejected as 2.R2 | see 2.R2 |
| 3.R2 | A separate structural commit installing sentinels that resolve to the constant | Proven safe - nobody passes `None`, no test introspects a signature - and still pointless: it adds a line the next commit deletes. The real split is row 2 lands the contract, row 3 lands the wiring | One commit touching 18 files that changes nothing |

---

## 6. Row 4 - The port name disappears into the address

**Scope.** Delete `LLAMA_PORT` and `DEFAULT_PORT`. `server_argv` reads the port back out of the base URL.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/utilities/llama_argv.py`, `backend/utilities/runtime_sweep.py`, `backend/utilities/measure_probability_mode.py`, `.github/scripts/start-llama-server.sh`, `.github/actions/model-server/action.yml`, `.github/workflows/{digest,idhazh-pipeline-tests,llm-council,measure,validate}.yml`, `backend/tests/test_summarize.py`, `backend/tests/workflows/_harness.py`, `backend/tests/workflows/test_model_server_jobs.py`, `backend/utilities/slot_probe.py`, `docs/how-to/run-the-pipeline.md`, `docs/how-to/test-models-locally.md`, `docs/reference/ci-model-runtime.md`, `docs/reference/github-actions.md`.

**Acceptance gates.**

- `pytest backend/tests/workflows/` green. `shellcheck` clean on `start-llama-server.sh`.
- `test_model_server_jobs.py` asserts the literal `PORT_ENV = "LLAMA_PORT"` exists inside `runtime_sweep.py`. That assertion moves with the name; it does not get deleted.
- The `_harness.py` constants `LLAMA_PORT_ENV`, `LLAMA_PORT_VALUE` and `LLAMA_PORT_READ` follow their variable.
- `runtime_sweep.py` does `int(os.environ[PORT_ENV])` twice and `measure_probability_mode.py` passes `port=DEFAULT_PORT`. Both are hard failures after the delete. **The row says where the sweep's port comes from afterwards: its own `--port` argument, defaulted from the resolved base URL.**
- `slot_probe.py` line 16's shell example moves off `LLAMA_PORT`.

**Oracle.** `git grep -n LLAMA_PORT` returns nothing. `git grep -n DEFAULT_PORT -- backend` returns nothing.

**What the oracle cannot settle.** Whether a live dispatch still starts. The workflow tests read files; they do not run the job. The first real dispatch after merge is the proof, which is why row 5 exists.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 4.1 | Delete the name rather than rename it | The port lives inside `base_url`. A second value for it is a second thing to disagree |
| 4.2 | Safe because nothing runs two servers at once | Verified: every workflow starts one server per runner, the pipeline-test job kills the first before starting the second, and the sweep loops cases on one port. The one other port in the tree is a hand-run instrument's own `--server-port`, which never reads a shared constant |
| 4.3 | The action's `port` input goes too | An input restating a config value is a second spelling |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 4.R1 | Rename to `MODEL_SERVER_PORT` | 69 lines edited and two values that can still disagree about one server | 69 edits, and the disagreement stays |

---

## 7. Row 5 - A job refuses to start a server nobody will talk to

**Scope.** The refusal of contract C5, inside `argv_for`.

**Files touched.** `backend/utilities/llama_argv.py`, `backend/tests/workflows/test_model_server_jobs.py`.

**Acceptance gates.**

- A unit test from a fixture config root: matching addresses build an argv, a non-loopback `base_url` raises `SystemExit` whose message names both addresses.
- The refusal fires before any weights are read. Prove it by the call order in `argv_for`, not by timing.
- `pytest backend/tests/workflows/` green.

**Oracle.** With a fixture config root whose `base_url` is `http://192.168.1.20:9090`, `argv_for` refuses. With the committed root, it builds today's argv unchanged.

**What the oracle cannot settle.** Nothing outstanding. All five workflows reach `argv_for`; two reach it through the shell script and three call it directly.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 5.1 | The refusal lives in `argv_for`, not in the action or the shell script | It is the only place where the port about to be bound and the address the stage will post to are both in scope, and the only one all five workflows reach. The shell script reaches two of five |
| 5.2 | It reads the config root it was given | Three workflows run against `backend/var/candidate-config`. A refusal reading the committed file would check the wrong one |
| 5.3 | The three self-spawning instruments are exempt | They bypass `argv_for` and probe the server they started, which is C4's rule |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 5.R1 | Have the workflow probes read `base_url` | It is escalation trigger 1: a non-loopback address makes every probe clear the foreign machine while the local server goes unchecked. It is also unimplementable - the action declares no outputs and only two of five workflows use it | Five copies of a `jq` line, and a probe that lies |
| 5.R2 | No refusal | The mismatch is then found after the cache restores and the weights load, on every shard at once | Nothing to write, and a wasted run per mistake |

---

## 8. Row 6 - The loopback literals outside the workflows become one function

**Scope.** Add `loopback_url(port)` per C4 and route the six literals in the three self-spawning instruments through it.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/utilities/{measure_probability_mode,measure_two_calls,runtime_sweep}.py`.

**Acceptance gates.** `ruff check .` clean. Each instrument still starts its own server and probes the one it started. A unit test that `loopback_url` ignores `base_url` entirely.

**Oracle.** `git grep -n '127\.0\.0\.1' -- backend/idhazh backend/utilities config` returns exactly two lines: the body of `loopback_url` and the committed default. Scoped deliberately: `backend/tests/` holds about 32 more that are about URL sanitisation and have nothing to do with the model server.

**What the oracle cannot settle.** Nothing outstanding. It is stated as survivors rather than as zero, because zero is not the correct answer and an earlier draft of this plan claimed it was.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 6.1 | The spawners do not read the config | Each starts a server and then finds it. Reading the config would let an instrument report a number about a binary it is not running |
| 6.2 | One function carries the literal | A literal with one home and a comment saying why is not a hardcoded value; thirty copies are |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 6.R1 | `localhost` instead | A different literal, not fewer, and it adds a name resolution that can fail | Nothing, and nothing gained |

---

## 9. Row 7 - The model file, and the value nothing reads

**Scope.** Rename `LLAMA_WEIGHTS` to `MODEL_FILE` and delete `LLAMA_ROLE`, per Table D rows D9.

**Files touched.** `.github/scripts/start-llama-server.sh`, `.github/actions/model-server/action.yml`, `backend/utilities/llama_argv.py`, the workflow files that set the weights value, and the workflow tests that read it.

**Acceptance gates.** `pytest backend/tests/workflows/` green. `shellcheck` clean. The weights value still reaches `server_argv` as `--model`.

**Oracle.** `git grep -n LLAMA_WEIGHTS` and `git grep -n LLAMA_ROLE` both return nothing.

**What the oracle cannot settle.** Nothing. `LLAMA_ROLE` has one occurrence and no reader, so deleting it cannot change behaviour.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 7.1 | `MODEL_FILE`, not `MODEL_WEIGHTS` | It is a path to a file. "Weights" means tensors in every other tool: `--model` in llama.cpp and vLLM, `model_path` in Hugging Face |
| 7.2 | The llama.cpp build, asset, pin and binary names stay | They name the vendor's own artefacts, which section 0b permits. Table B row B4 |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 7.R1 | Rename every `LLAMA_*` name | Six of them correctly name llama.cpp's own artefacts. A blanket rename makes those six lie | About 100 edits, and six wrong names |

---

## 10. Row 8 - The run says which server answered

**Scope.** Add the module logger and the one-shot origin record per C6, and apply C7c.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`.

**Acceptance gates.**

- `ruff check .` clean.
- A test calling `_note_origin` **directly** with `http://user:token@box:8080` asserting `"token" not in caplog.text`. No socket opens.
- A test calling `_note_origin.cache_clear()` first, then twice with one origin, asserting one record.
- The new `post()` docstring says `_ask` carries only this module's probe constants and that `token_pieces` has no caller, so the next person to give it one sees the constraint.

**Oracle.** Running the summarize stage prints exactly one `model server origin=` line at `INFO`, carrying scheme, host and port and no credential.

**What the oracle cannot settle.** Whether anybody reads it. It costs eight lines and it is the only thing in a run that can say, after the fact, which machine produced the output.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 8.1 | Cached on the origin, not the endpoint | The qualification process posts to two routes on one server; an endpoint key would write the same line twice |
| 8.2 | Emitted from `post()`, memoised | Module import fires in every process including test collection. `post()` is the one place an item is sent |
| 8.3 | `hostname` and `port`, never `netloc` | Netloc carries userinfo. A credential must not reach a log record |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 8.R1 | Put the address on the run manifest | A persisted field is a version stamp, a changelog line, a migration and a fixture, for a value identical in every run CI makes | The full `CLAUDE.md` section 11 cost |
| 8.R2 | Log per item | Answers the same question thousands of times and buries everything else | Nothing, and a log nobody reads |

---

## 11. Row 9 - The run record stops claiming a build it cannot see

**Scope.** Contract C9. `runtime_build()` gains the resolved base URL and returns `UNRECORDED_BUILD` when it is not loopback. One sentence in `determinism.md` per C8.

**Files touched.** `backend/idhazh/fingerprint.py`, `backend/idhazh/cli.py`, `backend/idhazh/stages/work.py`, `backend/idhazh/stages/qualify.py`, `backend/tests/test_fingerprint.py`, `docs/architecture/contracts/determinism.md`.

**Acceptance gates.**

- `pytest backend/tests` green.
- Two unit tests, both from a fixture: a loopback address leaves the stamp unchanged; a non-loopback address stamps `UNRECORDED_BUILD`. Neither reads `config/idhazh.json`.
- **No version stamp, no changelog entry, no migration.** The sentinel exists and already validates. If this row needs any of the three, that is a finding and the row stops.
- `python backend/utilities/doc_load.py` before and after.

**Oracle.** A run configured against a second machine writes a record whose `runtime_build` says it was not recorded, and every other field still validates.

**What the oracle cannot settle.** What the build actually was. Reading `/props` and recording the truth is Table B row B3.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 9.1 | Degrade rather than refuse | A run against a second machine is the feature. Refusing it would undo rows 2 and 3 |
| 9.2 | Reuse `UNRECORDED_BUILD` | It exists, it validates, and it already means exactly this. No new state is minted |
| 9.3 | `runner_class` and `host_cpu` are left alone | Both describe the machine that ran the pipeline, which is this one, and that stays true. Only the build describes the model's machine |
| 9.4 | The determinism-guard consequence is written down, not fixed | Two runs against two different foreign builds both stamp the sentinel and the guard sees no move. Pre-existing for a developer machine that pins nothing; this row widens it, so `determinism.md` names it and Table B row B3 carries the fix |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 9.R1 | Record the defect and fix nothing | It was this plan's first shape, on the belief that a new unrecorded state was needed. It already exists, so the fix is smaller than the note explaining the deferral | Nothing, and a record that keeps saying something false |
| 9.R2 | Read `/props` and record what answered | The honest full fix, and a bigger one: a new field, a version stamp, a changelog line and a migration | The whole of `CLAUDE.md` section 11, plus a ruling on what a run does when the server it reached is not the one the record describes |

---

## See also

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - row 21, whose surviving half is this plan. Table C records the rest.
- [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) - hands every process-boundary value to this plan at its line 34, and shares the workflow files with PR A. Escalation trigger 4 keeps them apart.
- [`../docs/reference/pipeline-cost.md`](../docs/reference/pipeline-cost.md) - retracts the memory figure an earlier draft of this plan used as its reason.
- [`../docs/how-to/run-the-pipeline.md`](../docs/how-to/run-the-pipeline.md) - where the change is recorded.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - owns the run record that row 9 corrects.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the pool, readiness, and the execution stamp.
