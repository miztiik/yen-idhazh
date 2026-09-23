# The model server's address and settings move into committed config

**Last Updated**: 2026-09-23

**Level**: 3 (`CLAUDE.md` section 6). It crosses python, committed config and the workflow files, and it renames two config keys that a generated schema is built from. **No persisted payload changes shape** - two nearly did, and C11 and C12 are why they do not. With the committed config unchanged, every address and every request body is character-for-character what this repository produces today.

> Execute with [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md), parallel N = 1, AUTHOR-AND-STOP until the user authorises the run.

---

## 0a. The anchor, and the mistake

**Anchor commit: `8305c986`** - "Guardrail 11 says where article text may be sent", 2026-09-22. `git show 8305c986:TODO/20260922-47-the-pipeline-stops-naming-a-server-plan.md` is the version of this plan the owner approved. **Its scope is this plan's intent and nothing has narrowed it since.**

**What went wrong on 2026-09-23.** A review pass found real defects in the sampling and model-slot rows. An agent turned those findings into a reason to delete both rows and push them to a later plan. That was scope narrowing, which `CLAUDE.md` section 10 forbids an agent from doing without the owner's sign-off, and the owner reversed it the same day. Three reasons were given and none was one:

| id | The reason given | What it actually was |
| --- | --- | --- |
| M1 | "It touches about 35 files" | A size. `CLAUDE.md` section 0d: a limitation named with no next move is an unfinished answer. The next move was to list the files, and C11 and C12 now do |
| M2 | "It changes data that is already published" | A real risk **with a fix the reviewer supplied in the same sentence**: rename the config-side name, pin the recorded one. Written down as C11 and C12 rather than used as an exit |
| M3 | "It means only one person can work at a time" | Already true before the cut, because six other rows edit the same file. A fact that was already true cannot be a reason to remove something |

**The standing rule this leaves.** A review finds defects. A defect is a correction to fold in. Only the owner may turn a defect into a smaller plan.

**Re-measured 2026-09-23, after plan 44 rows 3 to 5 landed.** Two files this plan named are gone: `.github/scripts/start-llama-server.sh` and `backend/utilities/llama_argv.py`. [`backend/utilities/model_runtime.py`](../backend/utilities/model_runtime.py) replaced both, and it is a better home for row 5 than either - its `start_server` verb holds the config root and the port in one scope, and **all five** workflows reach it, where the shell script reached two. `LLAMA_ROLE` is already deleted, so row 7 loses half its work. Every count in Table D below is from this re-measure, not from the day the plan was written.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Intent** | Two things this pipeline hands a model server are typed into python and reachable by no config value: **the address** and **the sampling settings**. Both become committed config, so changing either is a diff a person reads. |
| **Why the address** | `CLAUDE.md` Guardrail #11 was amended on 2026-09-22 and now says the address **is** a committed config value. It is not one: it is three constants in [`backend/idhazh/llm/server.py`](../backend/idhazh/llm/server.py), one of which reads an environment value. The contract and the code disagree, and section 0d says the code is what changes. |
| **Why the sampling settings** | `server.py` reads exactly three keys by name - `temperature`, `top_p`, `seed` - through a lookup table whose rows for those three map each name to itself. A fourth key added to a model file today validates and is dropped in silence, and a key llama.cpp adds tomorrow is unreachable without a code edit. Ten of the thirteen settings the build applies are its choice, not this project's. |
| **The defect that makes the address work harder than it looks** | `DEFAULT_ENDPOINT` is a **default argument**, bound when the module loads, at 18 sites, and no caller anywhere overrides one. A config field alone changes nothing. That is row 3, and without it rows 2 and 4 are decoration. |
| **The rule this plan is built on** | **A program that starts its own server probes loopback. A stage that only talks to one reads the address from the settings it already holds. And a setting this project does not compute on is passed through, never mapped.** |
| **What changes for the reader** | Nothing. No published file, no page, no column. |
| **What changes in production** | Nothing, if `config/idhazh.json` and `config/models/*.json` are left as committed. The thirteen sampling values are the values llama.cpp is already applying. |
| **Hard scope - in** | `model_server.base_url` as a config field; the two resolvers; the 18 default-argument sites resolved by their callers; `LLAMA_PORT` deleted; a refusal when a job starts a server on one address while the stage posts to another; the loopback literals outside `.github/` reduced to one function; `MODEL_PATH`; the dead role value deleted; one log record naming the server that answered; **the `request` block renamed to `sampling` and passed through whole; `models.<verb>` renamed to `models.<noun>`**; the run record stamping an unrecorded build when the address is not loopback; four sentences citing a rule that does not exist. |
| **Hard scope - out** | Table B. Four rows, each priced. |
| **Supersedes** | The surviving half of row 21 of [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md). Table C records what that row asked for and what happened to each part. |
| **Depends on** | Nothing. [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) line 34 hands every process-boundary value to this plan by name. Its rows 1 to 5 have landed; **its one remaining row, row 6, replaces `commit-and-push.sh`, `take-state-from-the-tip.sh` and `push-rewritten-history.sh`, and this plan touches none of the three.** The two plans edit the same five workflow files and `_harness.py` on different lines, which git resolves and whoever lands second rebases. [`20260922-46-one-writer-for-the-corpus-plan.md`](20260922-46-one-writer-for-the-corpus-plan.md) is closed. |
| **ESCALATE triggers** | Seven, below Table D. |
| **Execution** | Three pull requests, serial. **Peak one worker.** `server.py` is the hub of eight of the eleven rows, so the parallelism is not there to find and manufacturing it would buy a scheduling bug. |

### ESCALATE triggers

1. **Stop** if any row leaves a job starting a server on one address while the stage posts to another. Row 5 is the control.
2. **Stop** if anything would make `backend/idhazh/llm/` read `config/`. It sits below config in the dependency graph - `backend/idhazh/config.py` imports `SETTING_KEYS` from `server.py`, so the arrow points one way only. Every function that needs the address has `settings` in its own signature.
3. **Stop** if any row would read `config/idhazh.json` with no config root. Three workflows run production stages against `backend/var/candidate-config`, so a zero-argument load returns the wrong file and the run posts to an address nobody chose.
4. **Stop** if the sampling pass-through would let a config key replace or disable a decode control. C10 is the control and it is per-builder, not a central list.
5. **Stop** if rows 9 or 10 would change the shape or the values of a payload an earlier run already wrote. C11 and C12 exist because both rows nearly did.
6. **Stop** if plan 44 row 6 turns out to touch `backend/utilities/model_runtime.py` or any line this plan edits. It does not today - its three scripts and their ten call sites are disjoint from everything here - so the two plans rebase rather than serialise. Re-check before opening PR A.
7. **Stop** if any row would raise a runner budget figure. The 6 hour job limit and the 1 GB site limit are GitHub's and cannot be moved (Guardrail #2).

### Table B - Hard scope - out

| id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | The 22 loopback literals in `.github/` | Nothing today. Every one is a probe against a server the same job just started on the same machine. Reading the config there is the failure row 5 exists to prevent, and it is not implementable anyway: the composite action declares no outputs, only two of the five workflows use it, and three of them run against a different config root. | A job that talks to a server it did not start. That is a different design and it brings the readiness probe, the secret handling and the failure mode with it. |
| B2 | A translation table between runtimes, so one model file serves llama.cpp, vLLM and Ollama unchanged | A key one runtime accepts and another rejects fails at request time rather than at config load. Taken deliberately: a per-key table is the wiring row 9 deletes, and it would have to be maintained against three projects that each change their parameters on their own schedule. | A second runtime in use, and a measured list of where the two disagree. |
| B3 | Changing what any sampler does, and pinning the sampler **chain order** | Two things left open. `top_k` at 40 and `min_p` at 0.05 are llama.cpp's choices, not measured ones for this corpus. And `samplers` is a request key carrying the chain order, so pinning thirteen values with the order free does **not** mean a build upgrade cannot move the distribution - row 9 pins the values and says so rather than claiming more. | A holdout quality measurement. After row 9 both are config edits with no code change, which is the point. |
| B4 | Reconciling the server's `/props` against the fingerprint | Partly paid. Row 11 makes the run stamp an unrecorded build rather than a false one. What stays out is reading the server's own answer and recording what actually replied. | A run that needs to prove which build answered rather than only to avoid claiming the wrong one. Gating measurement: one `/props` read against the pinned build, seconds. |

### Table C - What plan 39 row 21 asked for, and what happened to each part

| id | Asked for | Outcome |
| --- | --- | --- |
| C1 | One request builder instead of four | **Refused.** Four shapes carrying four different Guardrail #11 controls: `response_format` with a `json_schema` on the chat route, a top-level `json_schema` on the plain completion route, a `grammar` on the third, and the fourth is a **derivation** of the second that inherits its body. Collapsing them collapses the controls. |
| C2 | Move to the widely supported `/v1/completions` route | **Refused by a measurement** at `server.py` lines 58 to 66: both completion routes ignore `response_format` and honour a top-level `json_schema`, on build b10444-5f754ea0e as of 2026-09-12. The chat route is not in that measurement and does honour `response_format`. That comment also says no workflow pins a llama.cpp build, which is false - [`.github/scripts/llama-cpp-pin.sh`](../.github/scripts/llama-cpp-pin.sh) pins `b10598`. Row 9 edits that block and corrects the sentence. |
| C3 | Delete three slot columns | **Refused.** `backend/utilities/slot_probe.py` is their named instrument. |
| C4 | Stamp the decode mode | **Done** in pull request #1036. |
| C5 | Stop naming a server in source | **This plan**, widened by owner instruction on 2026-09-22 to cover the sampling settings and the vendor-prefixed names. |

### Table D - Measured on `origin/main`, and what each number means

| id | Reading | Number | What it means |
| --- | --- | --- | --- |
| D1 | Sites where an address is a default argument bound at module load | 18 | Eight in `server.py`, seven in stages and utilities, three argparse defaults. Row 3's whole job. `DEFAULT_COMPLETION_ENDPOINT` is a default argument zero times. |
| D2 | Callers anywhere that override one of those 18 | **0** | Not in `backend/`, not in `.github/`. The address is a global wearing a parameter's clothes. |
| D3 | Production call sites relying on a `server.py` default | 2 | `stages/validate.py` line 128 and `utilities/prove_the_entry.py` line 19. The second already loads settings one line above. |
| D4 | Readers of `DEFAULT_HEALTH` | 0 | Defined, used nowhere. Row 2 deletes it. |
| D4b | Production readers of `DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` **after row 3** | 0 | `DEFAULT_COMPLETION_ENDPOINT` already has none today. Row 3 deletes both once the eighteen are rewired; their two remaining readers are tests and both move to a fixture. |
| D5 | Sampling keys a model file may set that reach the wire | **3** | `temperature`, `top_p`, `seed`. A fourth validates and is dropped in silence. |
| D6 | Identity rows in `SETTING_KEYS` | 3 of 10 | Each maps a name to itself and gates every other key for nothing. Row 9 removes them. |
| D7 | Samplers llama.cpp applies that this project does not name | at least 12 | Including `top_n_sigma`, which is in the active chain. Row 9 pins 13; it does not pin the chain, and Table B row B3 says so. |
| D8 | Committed model files carrying a `request` block | **5**, not 1 | `qwen3.5-9b-q4km.json`, `qwen3.5-9b-q4km-thinking.json`, `ornith-1.5-9b-q5km.json`, `gemma-4-e4b-qat.json`, `gemma-4-e4b-qat-no-draft.json`. Config models forbid unknown keys, so renaming in one file refuses the other four at load. |
| D9 | Committed request-body goldens that move when the splat lands | 5 files across 4 routes | `tests/fixtures/request-bodies/*.json`. Regenerated, not hand-edited. |
| D10 | Places the role string `"summarize"` is read | ~24 non-test files, ~110 test reads, plus 5 `.github/` files | Row 10's real size. It is listed, not estimated. |
| D11 | Committed run records carrying `"role": "summarize"` | 127 occurrences across 35 files | This is why the enum **value** is pinned and only the python name and config key move. |
| D12 | Reads of `LLAMA_ROLE` | **0, and the name itself is already gone** | Plan 44 row 3 deleted it with the shell script that set it. Row 7 is now the weights rename alone. |
| D13 | Occurrences of `LLAMA_PORT` | 62 lines in 14 files | Row 4 deletes the name rather than renaming it: the port lives inside `base_url`. `backend/utilities/model_runtime.py` line 78 declares `PORT_ENV` and line 544 reads it. |
| D14 | Workflows reaching the one program that starts a server | **5 of 5** | `backend/utilities/model_runtime.py start-server`, from `actions/model-server/action.yml` line 182 for `digest.yml` and `llm-council.yml`, and directly from `idhazh-pipeline-tests.yaml` lines 255 and 332, `measure.yml` line 972 and `validate.yml` line 308. This is why row 5's refusal lives there. |
| D15 | Workflows running a production stage against a config root that is not `config/` | 3 of 5 | `validate.yml`, `measure.yml` and the pipeline-test case script. Escalation trigger 3. |

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
| 7 | The model file, and the value nothing reads | 4 | A | DONE | p47w2 | - | W2 |
| 8 | The run says which server answered | 3 | A | PENDING | - | - | - |
| 9 | Sampling settings pass through, unmapped | 8 | B | PENDING | - | - | - |
| 10 | Model slots get nouns | 9 | B | PENDING | - | - | - |
| 11 | The run record stops claiming a build it cannot see | 9 | C | PENDING | - | - | - |

### 1a. The three pull requests

| PR | Rows | Wave | What it is |
| --- | --- | --- | --- |
| **A - the address** | 1 to 8 | 1 | The address becomes config and every caller names the one it means |
| **B - the settings** | 9, 10 | 2 | The model file speaks the server's language, and a slot is named for what it is |
| **C - the run record** | 11 | 3 | The fingerprint stops claiming a build it cannot see |

**Peak worker count: one.** `backend/idhazh/llm/server.py` is edited by eight of the eleven rows; PR B edits it again; PR C edits `fingerprint.py`, which PR B also edits because `sampling_spelling` lives there. There is no honest parallelism in this plan and inventing some would buy a scheduling bug instead of a gating cycle.

**File lists, disjoint by wave.**

- **PR A**: `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `backend/idhazh/cli.py`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/model_server.py` (new), `config/idhazh.json`, `schemas/app-config.schema.json`, `frontend/src/contracts/app-config.ts`, `backend/idhazh/stages/{judge_item_pairs,qualify,qualify_canaries,two_calls,validate,work}.py`, `backend/utilities/{model_runtime,slot_probe,prompt_loop,prove_the_entry,runtime_sweep,measure_probability_mode,measure_two_calls,measure_budgets,measure_judge_call}.py`, all five `.github/` workflow files plus `actions/model-server/action.yml`, `backend/tests/{test_summarize.py,workflows/_harness.py,workflows/test_model_server_jobs.py}`, `docs/how-to/{run-the-pipeline,test-models-locally}.md`, `docs/reference/{ci-model-runtime,github-actions}.md`.
- **PR B**: the full lists are C7 and C12, because they are the two rows whose size was previously guessed at rather than counted.
- **PR C**: `backend/idhazh/fingerprint.py`, `backend/idhazh/cli.py`, `backend/idhazh/stages/{work,qualify}.py`, `backend/tests/test_fingerprint.py`, `docs/architecture/contracts/determinism.md`.

---

## 2. The contracts, declared before any code

`CLAUDE.md` Guardrail #3 puts the contract before the logic. A worker implements this section and invents nothing.

### C1 - `model_server.base_url`, the address

| Property | Value |
| --- | --- |
| Declared in | A new `ModelServerConfig` in `backend/idhazh/contracts/knobs/model_server.py`, mounted on `AppConfig` in `backend/idhazh/contracts/app_config.py` beside `observability`. Twenty-one knobs modules already exist; this follows them |
| Value lives in | `config/idhazh.json`, a new top-level `"model_server"` block |
| Committed default | `"http://127.0.0.1:8080"` - today's address, written once as data |
| Shape | Scheme, host **and port**. Nothing else. A trailing `/` is accepted and dropped |
| Refused at load | No scheme, no host, **no port**, an out-of-range or non-numeric port, or any path, query or fragment |
| Why the port is required | Row 4 has `server_argv` read the port back out of this value. `http://host` parses cleanly and yields `port is None`, which would bind `--port None`. A validator that never touches `parts.port` does not catch it |
| Why a path is refused | `_sibling` builds every other route by replacing the whole path, so a prefix would survive on one route and vanish from four. A wrong answer is worse than an error |
| Regenerates | `schemas/app-config.schema.json` **and** `frontend/src/contracts/app-config.ts`. The drift gate fails on either if both are not regenerated |
| Owes | One `AppConfig.__changelog__` line. A new field is an expand, so no migration |

```json
  "logging": { ... },
  "model_server": {
    "base_url": "http://127.0.0.1:8080"
  },
  "models_file": "models/qwen3.5-9b-q4km.json",
```

### C2 - the two resolvers

Both pure. No config import, no cache, no module-level state. `urlsplit` and `urlunsplit` are already imported at `server.py` line 36.

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

`_CHAT_PATH: Final = "/v1/chat/completions"` joins `_COMPLETION_PATH` at line 66, and `DEFAULT_ENDPOINT` is composed from it so nothing spells the route twice. `DEFAULT_HEALTH` is deleted - zero readers - and no `health_url()` replaces it, because a replacement would land with zero readers too.

**`DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` survive row 2 and are deleted by row 3.** Row 2 keeps them so the tree still runs between the two commits; row 3 removes the last eighteen readers and then removes the constants. Keeping a constant nothing reads is the defect `DEFAULT_HEALTH` is deleted for, and it would be the one address in the repository that no config value can move.

**`server.py` never reads the config.** Every function that needs the address already has `settings`. A zero-argument load would read `config/idhazh.json` while three workflows run the stage under `backend/var/candidate-config`: the control failing quietly rather than loudly. Escalation triggers 2 and 3.

### C3 - the eighteen sites, and what each becomes

Without this row, rows 2 and 4 ship a field, a schema, a frontend type and a validator, and the pipeline keeps posting to the module constant.

| Group | Sites | Becomes | Caller edits owed |
| --- | --- | --- | --- |
| **The eight in `server.py`** - `post`, `props_url`, `completion_url`, `apply_template_url`, `tokenize_url`, `props`, `derive_turn_markers`, `prove_the_entry` | lines 959, 984, 989, 994, 999, 1004, 1436, 1537 | **Required. No default, no sentinel.** The address is always the caller's | **Two**: `stages/validate.py` line 128 and `utilities/prove_the_entry.py` line 19 |
| **The seven in stages and one utility** - `stage_judge_item_pairs`, `stage_qualify`, `stage_qualify_canaries`, `two_calls_one_item`, `_summarize_one`, `stage_work`, `judge_calls` | `judge_item_pairs.py:111`, `qualify.py:409`, `qualify_canaries.py:49`, `two_calls.py:431`, `validate.py:40`, `work.py:301`, `measure_judge_call.py:334` | `str \| None = None`, resolved on the **first line**: `endpoint = model_endpoint or resolve_endpoint(settings.app.model_server.base_url)` | none |
| **The three argparse defaults** | `cli.py:518`, `prompt_loop.py:592`, `slot_probe.py:192` | `default=None`, resolved after the parse. `slot_probe.py` gains a `--config-root`, following `model_runtime.py` and `prove_the_entry.py` | none |

**First-line resolution is mandatory.** Two `functools.partial` sites bind the endpoint eagerly - `judge_item_pairs.py:148` and `measure_judge_call.py:357` both do `partial(post, endpoint=completion_url(base_url), ...)`. A `None` travelling further raises `TypeError` inside `_sibling`.

**Two live defects this row fixes, not to be read as a no-op.** `stage_validate` at `validate.py:102` takes no address at all and falls through to the module constant twice; it gains one. `--base-url` at `cli.py:518` is dead - the name appears nowhere else in the file and the judge stage's only production caller never passed it - so **the flag is deleted**.

**Two properties checked in advance**: nothing in `backend/` passes `endpoint=None`, `base_url=None` or `model_endpoint=None`; and no test introspects a signature or `__defaults__` of any of the eighteen. **If any of the seven lacks `settings` in scope, stop** - escalation trigger 2.

**Then both constants go.** Once the eighteen are rewired, `DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` have no production reader left - `DEFAULT_COMPLETION_ENDPOINT` has none today either. Their two remaining readers are tests, and both move:

| Test | Today | After |
| --- | --- | --- |
| `backend/tests/test_summarize.py` lines 479 to 483 | Asserts the three constants relate correctly to each other | Asserts the same property of `resolve_endpoint` and `completion_url` against a **fixture** base URL. Same check, no constant |
| `backend/tests/workflows/test_model_server_jobs.py` line 457 | Asserts `DEFAULT_ENDPOINT` begins with the address the workflows probe | Asserts the **committed** `model_server.base_url` matches the address the workflows probe. It is a statement about two committed files, and it going red means somebody committed the mismatch row 5 refuses at run time |

### C4 - the one loopback literal outside the workflows

Every address in the three self-spawning instruments belongs to a program probing a server it started with `subprocess.Popen`. None reads `base_url`, deliberately: an instrument measuring a server it is not running reports a number about the wrong binary.

```python
def loopback_url(port: int) -> str:
    """The address of a server started on this machine.

    Deliberately ignores `model_server.base_url`: the caller started this server
    and must probe that one, not whichever one the config names.
    """
    return f"http://127.0.0.1:{port}"
```

All three instruments already import from `idhazh.llm.server`, so this adds no dependency.

### C5 - the refusal, and where it must live

The control that makes escalation trigger 1 enforceable: a job that starts a server on loopback while the stage posts elsewhere fails at start-up, not after the weights load.

**It goes in `backend/utilities/model_runtime.py`, inside `start_server`.** Not `action.yml`, which sees neither fact. That function is the one program in the repository that starts a server, **all five workflows reach it**, and it already holds both halves of the question: `config.load(config_root)` at line 538 reads **the root this job will actually run under**, and `os.environ[PORT_ENV]` at line 544 is the port about to be bound.

```python
    entry_settings = config.load(config_root)
    declared = resolve_base_url(entry_settings.app.model_server.base_url)
    port = int(os.environ[PORT_ENV])
    if declared != loopback_url(port):
        raise SystemExit(
            f"this job binds {loopback_url(port)} and the stage posts to {declared}. "
            "A readiness probe that clears a server nobody talks to is worse than no "
            f"probe - set model_server.base_url in {config_root} to match, or start "
            "no server here"
        )
```

It sits before `server_argv` is called, so the refusal lands before the weights path is resolved. `resolve_base_url` and `loopback_url` are imported inside the function, beside the two imports already there - `start_server` deliberately imports nothing from `idhazh` at module scope, because the two download verbs run in a job that has not installed the package.

The three self-spawning instruments never call `start_server`; they take `loopback_url(port)` and get no refusal.

### C6 - the log record

| Property | Value |
| --- | --- |
| Where | Inside `post()`, the one place an item is sent. Not module import, which fires during test collection. Not `prove_the_entry`, whose only caller is a hand-run utility |
| Cache key | **The origin, not the endpoint.** The qualification process posts to the chat route and to `completion_url(endpoint)`; an endpoint key writes the identical line twice |
| Level and logger | `INFO`, on `LOG: Final = logging.getLogger("idhazh")`. `logging` and `functools.lru_cache` are new imports here |
| Must never print | **`parts.netloc`** - it carries userinfo, so `http://user:token@box:8080` would write the token verbatim. Use `parts.hostname` and `parts.port`. Never the path, query, a header or any payload |

```python
@lru_cache(maxsize=None)
def _note_origin(origin: str) -> None:
    """Say once which server this run is talking to."""
    LOG.info("model server origin=%s", origin)
```

`post()` computes the origin with `urlsplit`. **The test opens no socket** (Guardrail #7): call `_note_origin` directly with a credentialed URL and assert the token is absent; call `cache_clear()` first for the once-per-origin claim, because `lru_cache` is process-global. The docstring records that `_ask` is a second send path carrying only this module's probe constants, and that `token_pieces` would send whatever it is handed and has no caller.

### C7 - the sampling block passes through

**The rename.** `request` becomes `sampling`. `request_timeout_minutes` moves up to the model entry, because it is how long the client waits and never goes on the wire.

**The splat, applied by the three builders that construct a body from nothing** - `request_payload`, `completion_payload`, `grammar_completion_payload`:

```python
def with_sampling(body: dict[str, Any], sampling: Mapping[str, Any]) -> dict[str, Any]:
    """This route's own keys, plus every key the model file declares.

    The refused set is whatever the route already put in `body`, plus the keys
    declared beside the control this route sets, so a builder that changes its
    control changes this check with it.
    """
    clash = sorted(sampling.keys() & (body.keys() | disablers))
    if clash:
        raise ValueError(f"sampling may not set {', '.join(clash)} - this route sets it")
    return {**sampling, **body}
```

**`continued_completion_payload` must NOT call it.** It is `{**first, ...}` - a derivation of a body `completion_payload` already built - so the whole sampling block is already in `first`, every key would clash, and it would raise on every summarize-and-plan call. The derivation inherits sampling through `**first`, which its docstring already promises. `thinking_span` and `answer_span` are derivations for the same reason.

**The clash check runs at config load as well.** It is a pure function of the config keys and the route's key sets, both known when settings load. Left to build time it fires on the first item of every shard at once, after each has already restored the cache and loaded the weights.

**Files.** `backend/idhazh/llm/server.py`, `backend/idhazh/config.py`, `backend/idhazh/contracts/knobs/models.py`, **all five** `config/models/*.json`, `backend/idhazh/fingerprint.py`, `backend/idhazh/evals/qualify.py`, `backend/idhazh/similarity/judge.py`, `backend/idhazh/stages/work.py`, and the nine `request_timeout_seconds(entry.request)` call sites: `stages/common.py:530`, `stages/judge_item_pairs.py:136`, `stages/qualify.py:427`, `stages/two_calls.py:487`, `stages/validate.py:81`, `stages/work.py:314`, `utilities/prompt_loop.py:369`, `utilities/prove_the_entry.py:22`, `utilities/measure_judge_call.py:354`. Plus `backend/utilities/capture_request_bodies.py`, `backend/tests/test_request_bodies.py` and the five goldens under `tests/fixtures/request-bodies/`.

### C8 - the sampling values, approved 2026-09-22

Written at the values the pinned build already applies. **Output does not change by a token.** What changes is that a build upgrade can no longer move them without a diff.

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

`top_k` 40, `min_p` 0.05 and `repeat_last_n` 64 are the build's defaults written down. `temperature` 0.2, `top_p` 1.0 and `seed` 0 are this project's own values, already sent - `top_p` is **not** a build default, which is 0.95. The other seven are already neutral.

**No fresh `/props` read is owed.** The pinned build has already echoed all thirteen at these values into a committed fixture: `tests/fixtures/completions/judge/a-window-of-one-verdict-spelled-twice.json` lines 75 to 139. Cite it; do not re-measure.

**What this achieves and what it does not.** Thirteen values are pinned. The sampler **chain order** is a separate request key, `samplers`, and it is not pinned - a build that reorders the chain moves the distribution with all thirteen held. Table B row B3.

### C9 - what leaves the lookup table, and what stays

Three rows map a name to itself and gate every other key for nothing. They go.

| Leaves | Stays, and why it must be read by name |
| --- | --- |
| `temperature`, `top_p`, `seed` | `n_ctx` - the pipeline does arithmetic on the window and `config.py` refuses an entry that omits it |
| | `n_batch`, `n_ubatch`, `n_threads`, `n_parallel`, `load_mode` - published on the run record under these names and drawn on a console panel, so a rename would move a published string |
| | `request_timeout_minutes` - sets the socket timeout; no server-side default bounds it |

**After this, no mapping stands between the config and the wire.** The `server` block was always pure pass-through - a key is a flag, a non-null value is its argument.

**Five live readers call `setting(request, name)` for exactly the three being removed** and every one of them is in row 9's file list: `fingerprint.py:173-174` (`sampling_spelling`), `evals/qualify.py:617`, `similarity/judge.py:335`, `stages/work.py:167`, `config.py:72-88`. Miss one and it is a `KeyError` on every run.

### C10 - the control guard: per-builder, never a central list

The clash check compares key identity, and **every decode control on this build has more than one name.** A central list of synonyms is the stale list the owner's no-typed-list ruling refused. So each constructing builder declares, on the line beneath the control it sets, the keys that re-spell or disable it:

| Builder | Control it sets | `disablers` declared beside it |
| --- | --- | --- |
| `request_payload` (chat) | `response_format` | `frozenset({"json_schema", "grammar", "max_tokens", "n_predict"})` |
| `completion_payload` | `json_schema` | `frozenset({"response_format", "grammar", "grammar_lazy", "grammar_triggers", "max_tokens"})` |
| `grammar_completion_payload` | `grammar` | `frozenset({"grammar_lazy", "grammar_triggers", "response_format", "json_schema", "max_tokens"})` |
| all three | - | `frozenset({"logit_bias", "ignore_eos", "samplers"})`, unconditional; they are synonyms for nothing and each defeats a control on its own |

**Why this is not the list that was refused.** A central list must be remembered. These sit on the line beneath the control, so a builder that changes its control changes the set in the same edit - which is exactly the reason the central list was refused.

**Why `max_tokens` is in all three.** The chat builder sends no cap by design. A cap from config makes the reply stop at `length`, and `summarize.py:745-752` fails that item with `OUTPUT_TRUNCATED` before the content is read. The repair path at `calls.py:1622` only ever sees a completion-route reply, never a chat one - and the chat route is the qualification path that runs the injection canaries. `grammar_lazy` is the sharpest case: it leaves `grammar` formally applied and never engaged, so the control is off while its own key is untouched.

### C11 - what rows 9 and 10 must not change

**This is the section the 2026-09-23 mistake exists to prevent.** Both rows are one careless edit away from rewriting a payload an earlier run already wrote.

| id | The trap | The rule |
| --- | --- | --- |
| C11a | `request` is declared on **`ModelRef`**, not `ModelEntry`. `ModelUse` embeds `ModelRef`, and every published `run.json` carries `model_ref.request` with all four keys | **Rename on `ModelEntry` only. Leave `request: dict[str, Any]` on `ModelRef` as a recorded-shape mapping** - exactly what `inference` and `draft` already are on that class. `schemas/run-manifest.schema.json` and `frontend/src/contracts/run-manifest.ts` then do not move |
| C11b | `ModelRole.SUMMARIZE = "summarize"` is the type of `ModelUse.role`, and the string sits in 127 places across 35 committed run records. The file already carries the precedent: `VISUAL_PLANNER` kept its old value for this reason | **Pin the enum value.** `SUMMARIZE = "summarize"` stays; the python name and the config key move. Row 10's gate says the `--role` argument matches the **config key**, never that the enum value does |
| C11c | `sampling_spelling` records three names onto `PipelineInputs.sampling` on every run. After the splat, ten keys move the decode with nothing recording it | **Record the whole block.** It is a dict field, so more keys is an expand: an older record with three keys still validates. What is owed is one `run-manifest` version stamp and one changelog line. No migration, no new field |
| C11d | `config/idhazh.json` sets `finetune.teacher: "summarize"`, validated against `ModelsConfig.roles()`. Miss it and every command in the project fails to load config | Row 10 edits `config/idhazh.json`, and adds `{"summarize": "models.summarizer"}` to `SUPERSEDED_MODELS_NAMES` so a stale operator file is refused by name |
| C11e | `SUPERSEDED_ENTRY_NAMES` maps `inference` to `models.<role>.request`, a key that stops existing | Row 9 repoints it at `models.<role>.sampling` |
| C11f | Both `ModelsConfig` and `AppConfig` carry an enforced `__changelog__`, and the committed model file carries a `version` derived from it | One line each, newest first, one line long (`CLAUDE.md` section 11) |

### C12 - model slots get nouns

`CLAUDE.md` section 1a: a config is a self-descriptive noun, a function is a verb. The slot holds a model.

| Now | After |
| --- | --- |
| `models.summarize` | `models.summarizer` |

**Files, counted rather than estimated.** All five `config/models/*.json`; `backend/idhazh/contracts/knobs/models.py`; `backend/idhazh/contracts/knobs/finetune.py:87`; `backend/idhazh/contracts/knobs/placement.py:289` (a help string citing `models.summarize.inference`, already two renames stale); `backend/idhazh/contracts/app_config.py`; `config/idhazh.json`; `backend/idhazh/config.py`; `backend/idhazh/cli.py:196`; `backend/idhazh/similarity/judge.py:247`; `backend/idhazh/stages/{assemble.py:371, common.py:526-532, decide.py:38, qualify_decide.py, two_calls.py, validate.py}`; `backend/idhazh/evals/qualify.py:412`; `backend/utilities/{model_refs,model_runtime,measure_two_calls,measure_ledgers,measure_probability_mode,prompt_loop,prove_the_entry,runtime_sweep,capture_server_argv,pipeline_case_config}.py` - **`model_runtime.py` line 538 is the one that starts every server, so miss it and no job runs**; and in `.github/`: `actions/model-server/action.yml`, `workflows/idhazh-pipeline-tests.yaml`, `workflows/measure.yml`, `workflows/validate.yml`. Plus the five `tests/fixtures/server-argv/*.json` goldens, because `capture_server_argv.py:74` names the role. **Re-run the census before slicing this row**: plan 44 moved these sites once already.

### C13 - the model file, and the value nothing reads

| Now | After | Why |
| --- | --- | --- |
| `LLAMA_WEIGHTS` | `MODEL_PATH` | It is a path to a GGUF file. Every tool calls it the model: `--model` in llama.cpp and vLLM, `model_path` in Hugging Face. "Weights" means tensors. **`MODEL_FILE` was this row's first answer and is unusable**: `measure.yml` line 1046 already binds it to a bare filename, and `_harness.py` bans it inside `digest.yml` at any scope, so the verbatim rename turned `test_the_daily_run_writes_no_model_ref_of_its_own` red. `MODEL_PATH` is also the accurate noun - the value is `backend/models/<file>`, not a filename |
| `LLAMA_PORT` | **deleted** | The port lives inside `base_url`. Nothing is left for a second value to disagree with. The `_harness.py` constants `LLAMA_PORT_ENV`, `LLAMA_PORT_VALUE` and `LLAMA_PORT_READ` follow it |
| `LLAMA_ROLE` | **already gone** | Plan 44 row 3 deleted it with the shell script that set it. Nothing here to do |
| `LLAMA_CPP_BUILD`, `LLAMA_CPP_ASSET`, `LLAMA_CPP_SHA`, `LLAMA_BIN`, `llama-cpp-pin.sh`, `install-llama-runtime.sh` | **unchanged** | They name llama.cpp because the thing is llama.cpp. Section 0b bans a vendor name used as this project's vocabulary, not the vendor's name for its own artefact |

### C14 - the four sentences row 1 deletes

Each cites `CLAUDE.md` section 0a for a rule section 0a does not contain. The rule they reached for now exists, so each replacement cites the real one.

| id | File | The sentence, by its opening words | What replaces it |
| --- | --- | --- | --- |
| C14a | `backend/idhazh/llm/__init__.py`, second paragraph | "Nothing in this package reaches any origin but loopback. Hosted inference is a project non-goal..." | "The address this package talks to is one committed config value, `model_server.base_url`. Article text goes only to a model process this run's operator controls (`CLAUDE.md` Guardrail #11). The OpenAI-shaped transport here exists because it is the format local runtimes already speak." |
| C14b | `backend/idhazh/llm/server.py`, module docstring, third line | "Nothing here is hosted - `CLAUDE.md` section 0a forbids that." | "The address is a committed config value and defaults to loopback. Nothing in this module starts a server, and nothing here reads the config - every caller brings the address it means." The rest of the paragraph, from "Two transports," is unchanged |
| C14c | `backend/idhazh/llm/server.py`, the `post()` docstring | "Loopback only, by construction." | "One address for the whole run, and `_note_origin` says once which one." |
| C14d | `docs/how-to/run-the-pipeline.md`, lines 45 to 48 | "The summarize stage talks to `127.0.0.1:8080` and nothing else... There is no hosted inference anywhere in this project (section 0a)." | The paragraph in C15 |

C14c names a function row 8 creates, so row 1 leaves that sentence and row 8 deletes it.

### C15 - the documentation

**`docs/how-to/run-the-pipeline.md`**, replacing lines 45 to 48:

> The summarize stage talks to the address in `config/idhazh.json` under `model_server.base_url`, which is `http://127.0.0.1:8080` as committed. To use a server on another machine, change that value to its scheme, host and port. The server command reads the same value from the same config root, and refuses to start a server on one address while the stage posts to another. Every job in `.github/` starts its own server and probes it on loopback.

**`docs/architecture/contracts/determinism.md`**, row 11. One sentence appended to the paragraph that already discusses `/props`:

> When `model_server.base_url` is not loopback the run cannot see which build answered, so it records `UNRECORDED_BUILD` rather than this machine's; reconciling the record against the server's own `/props` is not done.

`python backend/utilities/doc_load.py` runs before and after each documentation edit. Both edits replace existing text rather than adding a heading, so no split test is owed.

### C16 - the run record rule

Every field of `PipelineInputs` is read from this process. Point the pipeline at a second machine and the model runs there while the record describes here: every field is well formed, so validation passes and the record is false.

**No new state is minted.** `UNRECORDED_BUILD = "build-not-recorded"` exists at `fingerprint.py:46` and `runtime_build()` already degrades to it when nothing pins a build.

> `runtime_build()` gains a second argument, the resolved base URL, and returns `UNRECORDED_BUILD` when that address is not loopback.

Its three callers pass it: `cli.py:212`, `stages/work.py:324`, `stages/qualify.py:434`. All three hold settings. No version stamp, no changelog, no migration - and if the row needs any of the three, that is a finding and the row stops.

**One consequence written down rather than discovered.** `runtime_build` is in `MACHINE_INPUTS`, so two runs against two different foreign builds both stamp the sentinel and the determinism guard sees no move. Pre-existing for a developer machine that pins nothing; this row widens it to the configuration the plan creates. C15 names it in `determinism.md` and Table B row B4 carries the fix.

### C17 - the commit order

One commit per row, in Reckoner order. A worker who follows it never writes an import pointing at a name that does not exist yet.

| PR | Commits, in order |
| --- | --- |
| A | 1 (text only, no behaviour) -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 |
| B | 9 -> 10 |
| C | 11 |

**Two rules that bind every gate in this plan.** A test that reads `config/idhazh.json` or a committed model file goes red the day an operator uses the feature, which is `CLAUDE.md` section 13's "a test goes red because somebody edited the tree" - so **every test here builds its config from a fixture**. And `git grep -c` prints one line per matching file rather than a number, so an oracle wanting a count uses `git grep -n ... | Measure-Object -Line`.

---

## 3. Row 1 - Delete the rule that is not written

**Scope.** Remove the four claims that section 0a forbids hosted inference, per C14, and cite Guardrail #11 instead.

**Files.** `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `docs/how-to/run-the-pipeline.md`.

**Gates.** `ruff check .` clean. `doc_load.py` before and after. No new heading. No browser smoke.

**Oracle.** `git grep -n "section 0a" -- backend/idhazh/llm docs/how-to/run-the-pipeline.md` returns nothing.

**What it cannot settle.** Nothing outstanding. The rule is written and dated.

**Decisions.** 1.1 Each replacement cites Guardrail #11, because the rule those sentences reached for now exists. 1.2 C14c waits for row 8, which creates the function it names.

**Rejected.** Adding hosted inference to section 0a: it would forbid the second machine Guardrail #11 explicitly allows. Cost: one line, and a contradiction inside `CLAUDE.md`.

---

## 4. Row 2 - The address becomes one config field

**Scope.** C1, C2, C15. Declare `ModelServerConfig`, mount it, add the committed default, add both resolvers, compose `DEFAULT_ENDPOINT` from `_CHAT_PATH`, delete `DEFAULT_HEALTH`.

**Files.** `backend/idhazh/contracts/knobs/model_server.py` (new), `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `frontend/src/contracts/app-config.ts`, `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`, `docs/how-to/run-the-pipeline.md`.

**Gates.**

- `ruff check .` and `mypy backend` clean.
- **Drift gate**: the schema **and** the frontend type both regenerate byte-identical. Regenerating only the schema fails it.
- One `AppConfig.__changelog__` line; no migration, because a new field is an expand.
- Six refusal tests from fixture strings: no scheme, no host, no port, port out of range, non-numeric port, a path.
- `pytest backend/tests/test_summarize.py backend/tests/workflows/test_model_server_jobs.py` green.
- `completion_url("http://127.0.0.1:8181") == "http://127.0.0.1:8181/completions"` at `test_summarize.py:482` passes unchanged - the proof that sibling derivation did not move.

**Oracle.** On the committed default, `DEFAULT_ENDPOINT` is byte-identical to `origin/main`. `resolve_base_url("http://host")` raises naming the missing port. `git grep -n DEFAULT_HEALTH` returns nothing.

**What it cannot settle.** Whether anything reads the field. Nothing does until row 3, which is why this row must not merge alone.

**Decisions.** 2.1 Committed config, not an environment value (Guardrail #11, amended 2026-09-22). 2.2 One field carrying scheme, host and port, because two values can disagree. 2.3 The port is required and range-checked, because row 4 reads it back out to bind the server. 2.4 `server.py` never reads the config (triggers 2 and 3). 2.5 `DEFAULT_HEALTH` deleted, nothing replaces it.

**Rejected.** An environment value - never committed, never reviewed; this plan's first design and the owner reversed it. A cached `configured_endpoint()` with a function-local config import - the import trick silently half-builds a module if anything ever calls it during import, it would be the first cache of a file's contents in the repository, and a zero-argument load reads the wrong config root in three of five workflows. A host field plus a port field - cannot express a scheme, and the two can disagree.

---

## 5. Row 3 - Every caller names the address it means

**Scope.** C3. The eighteen sites. Thread an address into `stage_validate`. Delete the dead `--base-url`.

**Files.** `backend/idhazh/llm/server.py`, `backend/idhazh/cli.py`, the six stage files, `backend/utilities/{measure_judge_call,prompt_loop,slot_probe,prove_the_entry}.py`, `backend/tests/test_summarize.py`.

**Gates.**

- `ruff check .` and `mypy backend` clean. **mypy is the gate that proves all eighteen were found**: a required parameter nobody passes is a type error.
- **The integration test that would have caught the defect this row exists to fix**: a fixture config with `base_url: "http://192.168.1.20:9090"`, one stage run with **no endpoint argument**, an assertion that the outbound URL carries that host. Driven by the recorded-response harness; no socket opens.
- `pytest backend/tests` green. Both `partial` sites still bind a resolved string.

**Oracle.** `git grep -n '= DEFAULT_ENDPOINT' -- backend` returns nothing, and `git grep -n 'DEFAULT_ENDPOINT\|DEFAULT_COMPLETION_ENDPOINT' -- backend` returns nothing at all - both constants are gone with their last reader. Changing `base_url` in a fixture config changes where the stage posts.

**What it cannot settle.** Whether a real second machine answers. Nothing here binds a server off loopback, so the first end-to-end proof is a person running one elsewhere by hand.

**Decisions.** 3.1 The eight in `server.py` become required with no sentinel - only two call sites rely on a default and one already holds settings. 3.2 The other ten resolve on the first line, because two `partial` sites bind eagerly. 3.3 `--base-url` is deleted, not wired: it has never reached a server. 3.4 `stage_validate` gains an address - the one place in this row where behaviour genuinely changes, and it is a fix. 3.5 Both address constants are deleted once nothing reads them, for the same reason `DEFAULT_HEALTH` is: an address no config value can move is the one most likely to drift out of step with the one that can.

**Rejected.** A separate structural commit installing sentinels that resolve to the constant: proven safe, and still pointless - it adds a line the next commit deletes. The real split is row 2 lands the contract, row 3 lands the wiring.

---

## 6. Row 4 - The port name disappears into the address

**Scope.** Delete `LLAMA_PORT` and `DEFAULT_PORT`. `server_argv` reads the port back out of the base URL.

**Files.** `backend/idhazh/llm/server.py`, `backend/utilities/{model_runtime,runtime_sweep,measure_probability_mode,slot_probe}.py`, `.github/actions/model-server/action.yml`, the five workflow files, `backend/tests/{test_summarize.py,workflows/_harness.py,workflows/test_model_server_jobs.py}`, `docs/how-to/{run-the-pipeline,test-models-locally}.md`, `docs/reference/{ci-model-runtime,github-actions}.md`.

**Gates.**

- `pytest backend/tests/workflows/` green.
- `test_model_server_jobs.py` carries 19 of the 62 `LLAMA_PORT` lines, including an assertion that the literal `PORT_ENV = "LLAMA_PORT"` exists inside `runtime_sweep.py`; that assertion **moves with the name**, it is not deleted.
- `backend/utilities/model_runtime.py` line 78 declares `PORT_ENV` and line 544 reads it into `server_argv`. Both move to the port read back out of `base_url`.
- `runtime_sweep.py` and `measure_probability_mode.py` each read the environment value once. Both are hard failures after the delete. **The sweep's port afterwards is its own `--port` argument, defaulted from the resolved base URL.**
- `slot_probe.py` line 16's shell example moves off `LLAMA_PORT`.

**Oracle.** `git grep -n LLAMA_PORT` returns nothing. `git grep -n DEFAULT_PORT -- backend` returns nothing.

**What it cannot settle.** Whether a live dispatch still starts. The workflow tests read files; they do not run the job. Row 5 is why that is acceptable.

**Decisions.** 4.1 Delete rather than rename: the port lives inside `base_url`. 4.2 Safe because nothing runs two servers at once - every workflow starts one server per runner, the pipeline-test job kills the first before the second, and the sweep loops cases on one port; the only other port in the tree is a hand-run instrument's own `--server-port`, which reads no shared constant. 4.3 The action's `port` input goes too.

**Rejected.** Renaming to `MODEL_SERVER_PORT`: 69 lines edited and two values that can still disagree about one server.

---

## 7. Row 5 - A job refuses to start a server nobody will talk to

**Scope.** C5, inside `model_runtime.start_server`.

**Files.** `backend/utilities/model_runtime.py`, `backend/tests/workflows/test_model_server_jobs.py`.

**Gates.** A unit test from a fixture config root: matching addresses build an argv, a non-loopback `base_url` raises `SystemExit` naming both addresses. The refusal fires **before `server_argv` is called**, so it lands before the weights path is resolved - proved by call order, not by timing. `pytest backend/tests/workflows/` green.

**Oracle.** A fixture root with `base_url: "http://192.168.1.20:9090"` refuses; the committed root starts the server exactly as today.

**What it cannot settle.** Nothing outstanding. All five workflows reach `start_server`: two through the composite action, three directly.

**Decisions.** 5.1 It lives in `start_server` - the only place where the port about to be bound and the address the stage will post to are both in scope, and the one program in the repository that starts a server. 5.2 It reads the config root it was given, because three workflows run against a candidate root. 5.3 The two resolvers are imported inside the function, beside the two imports already there: `start_server` imports nothing from `idhazh` at module scope because the download verbs run before the package is installed. 5.4 The three self-spawning instruments never call it and get no refusal; they probe the server they started.

**Rejected.** Having the workflow probes read `base_url`: escalation trigger 1, and unimplementable anyway - the action declares no outputs and two of five workflows use it. No refusal at all: the mismatch is then found after the cache restores and the weights load, on every shard at once.

---

## 8. Row 6 - The loopback literals outside the workflows become one function

**Scope.** C4. Add `loopback_url(port)` and route the six literals in the three self-spawning instruments through it.

**Files.** `backend/idhazh/llm/server.py`, `backend/utilities/{measure_probability_mode,measure_two_calls,runtime_sweep}.py`.

**Gates.** `ruff check .` clean. Each instrument still starts its own server and probes that one. A unit test that `loopback_url` ignores `base_url`.

**Oracle.** `git grep -n '127\.0\.0\.1' -- backend/idhazh backend/utilities config` returns exactly two lines: the body of `loopback_url` and the committed default. Scoped deliberately - `backend/tests/` holds about 32 more that are about URL sanitisation and nothing to do with the model server.

**What it cannot settle.** Nothing outstanding. It is stated as survivors rather than as zero, because zero is not the correct answer and an earlier draft claimed it was.

**Decisions.** 6.1 The spawners do not read the config; an instrument measuring a server it is not running reports a number about the wrong binary. 6.2 One function carries the literal - a literal with one home and a comment saying why is not a hardcoded value; thirty copies are.

**Rejected.** `localhost`: a different literal, not fewer, plus a name resolution that can fail.

---

## 9. Row 7 - The model file name

**Scope.** C13. `LLAMA_WEIGHTS` becomes `MODEL_PATH`. **`LLAMA_ROLE` is already gone** - plan 44 row 3 deleted it with the shell script that set it, so this row is the model-path rename alone, plus the one dead line below.

**Files.** `.github/workflows/digest.yml`, `backend/tests/workflows/test_model_server_jobs.py`. Two files; the name survives nowhere else.

**Gates.** `pytest backend/tests/workflows/` green. The model path still reaches `server_argv` as `--model`.

**Oracle.** `git grep -n LLAMA_WEIGHTS -- backend .github config docs frontend schemas` returns nothing. **Scoped, because this plan-doc's own prose carries the string** and an unscoped grep can never go quiet while the row that explains it exists.

**What it cannot settle.** Nothing.

**Decisions.** 7.1 `MODEL_PATH`, not `MODEL_WEIGHTS` and not `MODEL_FILE` - "weights" means tensors in every other tool, and `MODEL_FILE` is taken twice over (C13). 7.2 The llama.cpp build, asset, pin and binary names stay; they name the vendor's own artefacts. 7.3 The `env` block on `The server proves the entry` is deleted rather than renamed: `prove_the_entry.py` reads no environment variable at all, so the line was set and never read. This is the "value nothing reads" in this row's own title, which `LLAMA_ROLE` was expected to be and no longer is.

**Rejected.** Renaming every `LLAMA_*` name: six of them correctly name llama.cpp's own artefacts, and a blanket rename makes those six lie. Amending `MODEL_ENV_NAMES` so `MODEL_FILE` could be used: it pays for a spelling by deleting a guard against exactly the drift the spelling would create (Fowler ruled, 2026-09-23).

---

## 10. Row 8 - The run says which server answered

**Scope.** C6, and apply C14c.

**Files.** `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`.

**Gates.** `ruff check .` clean. A test calling `_note_origin` **directly** with `http://user:token@box:8080`, asserting the token is absent from the log; no socket opens. A test calling `cache_clear()` then twice with one origin, asserting one record. The new `post()` docstring names `_ask` and `token_pieces` so the next person to give either a caller sees the constraint.

**Oracle.** Running the summarize stage prints exactly one `model server origin=` line at `INFO`, carrying scheme, host and port and no credential.

**What it cannot settle.** Whether anybody reads it. It costs eight lines and it is the only thing in a run that can say, after the fact, which machine produced the output.

**Decisions.** 8.1 Cached on the origin, not the endpoint - the qualification process posts to two routes on one server. 8.2 Emitted from `post()`, memoised. 8.3 `hostname` and `port`, never `netloc`.

**Rejected.** Putting the address on the run manifest: a persisted field costs a version stamp, a changelog line, a migration and a fixture, for a value identical in every run CI makes. Logging per item: answers the same question thousands of times and buries everything else.

---

## 11. Row 9 - Sampling settings pass through, unmapped

**Scope.** C7, C8, C9, C10, and C11a, C11c, C11e, C11f. Rename `request` to `sampling` on the entry, move the timeout up, splat the block in the three constructing builders, remove the three identity rows, add the per-builder disabler sets, record the whole block.

**Files.** C7's list - and it is complete, not indicative.

**Gates.**

- `ruff check .` and `mypy backend` clean. Drift gate green.
- **`ModelRef.request` is untouched.** `schemas/run-manifest.schema.json` and `frontend/src/contracts/run-manifest.ts` regenerate byte-identical. If either moves, stop: C11a was missed.
- **All five** `config/models/*.json` carry `sampling`. Config models forbid unknown keys, so one file edited is four files refused at load.
- Test one: a key no code mentions arrives in the payload verbatim. Test two: for each builder, a key from **its own** disabler set raises, naming the key. Neither test is per sampler.
- Test three: `continued_completion_payload` builds from a body that already carries sampling and does **not** raise.
- The five `tests/fixtures/request-bodies/*.json` goldens are **regenerated** with `python backend/utilities/capture_request_bodies.py`, and the diff adds exactly ten keys per route and changes no existing value.
- `config.py`'s validation loop still refuses an entry with no `--ctx-size` and no timeout. It reads two names, neither being removed.
- One `run-manifest` version stamp and one changelog line for C11c. One `ModelsConfig.__changelog__` line for the rename.

**Oracle.** Adding `"top_k": 7` to a model file changes the request body and needs no code edit. `SETTING_KEYS` has seven rows, each a real translation or a required read.

**What it cannot settle.** Whether the three pinned defaults suit this corpus, and whether the chain order moves. Table B row B3 owns both.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 9.1 | The block is splatted, not read key by key | A vendor changes its parameters on its own schedule. Per-key wiring makes every one of those a code change |
| 9.2 | Three builders splat, not four | `continued_completion_payload` is `{**first, ...}`; the fourth would clash on all thirteen and raise every summarize-and-plan call |
| 9.3 | No central list of refused names; each builder declares its control's disablers beside it | A central list must be remembered, which is the stale list the owner refused. A set on the line beneath the control moves when the control does |
| 9.4 | The clash check runs at config load too | It is a pure function of config and route. Left to build time it fires on the first item of every shard after each has restored the cache and loaded the weights |
| 9.5 | Pin the three at the build's current values, not at disabled | Zero behaviour change today, and the drift hole closes. Moving them is then a config edit with a measurement |
| 9.6 | `sampling`, not `generation` or `request` | vLLM calls it `SamplingParams`, llama.cpp `common_params_sampling`. "Request" describes the envelope, not the setting |
| 9.7 | `request_timeout_minutes` leaves the block | It is how long the client waits. It never goes on the wire |
| 9.8 | The record carries the whole block | Ten keys moving the decode unrecorded is the defect `determinism.md` exists to prevent. A dict field is an expand: no migration |

**Rejected.**

| id | Alternative | Why not | Cost to take |
| --- | --- | --- | --- |
| 9.R1 | Add the ten missing keys to `SETTING_KEYS` | Keeps the per-key gate and pays it ten more times, then again for every key any runtime adds | Ten rows now, a permanent tax |
| 9.R2 | A translation table across llama.cpp, vLLM and Ollama | Table B row B2 - the wiring this row deletes, maintained against three projects | A table per runtime, and a merge every time any of them changes |
| 9.R3 | Splat with the controls first and let config win | A config key could turn off constrained decoding | Nothing to write, and the decode control becomes optional |
| 9.R4 | Set the three samplers to disabled | Changes the sampler on every summary from the next run | A holdout measurement first, which is a different job |
| 9.R5 | Move this row to a later plan | **This was done on 2026-09-23 and reversed by the owner the same day.** Section 0a records it. The findings that prompted it are folded in above as C7 and C10 | The per-key gate stays live for a plan cycle, for no gain |

---

## 12. Row 10 - Model slots get nouns

**Scope.** C12, C11b, C11d. Rename the slot key from a verb to a noun, pin the enum value, and refuse a stale operator file by name.

**Files.** C12's list - and it is complete, not indicative.

**Gates.**

- `ruff check .` and `mypy backend` clean. Drift gate green.
- **`ModelRole.SUMMARIZE` still equals `"summarize"`.** A test asserts it. If a committed `run.json` would change, stop: C11b was missed.
- `config/idhazh.json` loads. `finetune.teacher` resolves against the new key.
- `SUPERSEDED_MODELS_NAMES` refuses a file still naming the old key, by name.
- The five `tests/fixtures/server-argv/*.json` goldens regenerate with `python backend/utilities/capture_server_argv.py`.
- All five workflow and action sites are edited; a workflow test asserts the `--role` argument matches the config key.
- `pytest backend/tests` green.

**Oracle.** `git grep -n 'models\.summarize' -- backend config docs .github` returns nothing, and `git grep -c '"role": "summarize"' -- frontend/public` is unchanged from `origin/main`.

**What it cannot settle.** Whether the other slot names are right. One slot exists today; the others are named so the pattern is set when a second arrives.

**Decisions.** 10.1 A noun per slot (`CLAUDE.md` section 1a). 10.2 The enum **value** is pinned and only the python name and config key move, because the string is in 127 places across 35 published run records and the file already carries that precedent. 10.3 After row 9, because both edit the model files and the same contract module, and the settings shape is the one a worker is likelier to get wrong.

**Rejected.** `models.summarizer_model` - says "model" twice under a key already called `models`. Leaving the verb - one verb where the contract asks for a noun, in the key a second slot will copy; the same rename later across more callers.

---

## 13. Row 11 - The run record stops claiming a build it cannot see

**Scope.** C16, C15.

**Files.** `backend/idhazh/fingerprint.py`, `backend/idhazh/cli.py`, `backend/idhazh/stages/{work,qualify}.py`, `backend/tests/test_fingerprint.py`, `docs/architecture/contracts/determinism.md`.

**Gates.** `pytest backend/tests` green. Two unit tests from a fixture: a loopback address leaves the stamp unchanged, a non-loopback address stamps `UNRECORDED_BUILD`. Neither reads `config/idhazh.json`. **No version stamp, no changelog entry, no migration** - and if the row needs any of the three, that is a finding and the row stops. `doc_load.py` before and after.

**Oracle.** A run configured against a second machine writes a record whose `runtime_build` says it was not recorded, and every other field still validates.

**What it cannot settle.** What the build actually was. Table B row B4.

**Decisions.** 11.1 Degrade rather than refuse - a run against a second machine is the feature. 11.2 Reuse `UNRECORDED_BUILD`; it exists, validates, and already means this. 11.3 `runner_class` and `host_cpu` are left alone; both describe the machine that ran the pipeline, which is this one. 11.4 The determinism-guard consequence is written down, not fixed.

**Rejected.** Recording the defect and fixing nothing - the sentinel already exists, so the fix is smaller than the note explaining the deferral. Reading `/props` and recording what answered - the honest full fix, and a bigger one: a new field, a version stamp, a changelog line and a migration.

---

## See also

- **`8305c986`** - the anchor commit. `git show 8305c986:TODO/20260922-47-the-pipeline-stops-naming-a-server-plan.md` is the owner-approved scope this plan restores. Section 0a records what was removed on 2026-09-23 and why that was wrong.
- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - row 21, whose surviving half is this plan. Table C records the rest.
- [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) - hands every process-boundary value to this plan at its line 34, and shares the workflow files with PR A. Escalation trigger 6 keeps them apart.
- [`../docs/how-to/run-the-pipeline.md`](../docs/how-to/run-the-pipeline.md) - where the change is recorded.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - owns the run record that rows 9 and 11 touch.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the pool, readiness, and the execution stamp.
