# The address of the summarising server becomes a setting

**Last Updated**: 2026-09-22

**Level**: 2 (`CLAUDE.md` section 6). One environment value, two constants rebuilt from it, one constant deleted because nothing reads it, one log line, two command defaults, and one test that keeps the whole thing out of CI. No persisted shape moves. No route changes. No committed column is added or removed. With the new value unset, every address this repository builds is character-for-character what it builds today, which is what makes the level 2 and not 3.

> Execute with [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md), parallel N = 2, AUTHOR-AND-STOP until the user authorises the run.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Why this plan exists** | The address of the model server is typed into three lines of [`backend/idhazh/llm/server.py`](../backend/idhazh/llm/server.py) and reachable by no setting of any kind. A developer whose model server runs on a second machine has to edit those three lines and then keep the edit out of every commit they make. That developer is not hypothetical: a single `llama-server` peaks at 12.57 to 13.16 GiB and reaches 14.31 GiB once the job's python is counted - 96.0 percent of a 16 GB machine, measured over four captures of run 2026-08-29-3 on 2026-09-08 and recorded at [`.github/actions/model-server/action.yml`](../.github/actions/model-server/action.yml) lines 145 to 152. On a 16 GB laptop that leaves nothing for the pipeline to run in. |
| **What changes for the reader** | Nothing. No published file, no page, no column. |
| **What changes in CI** | Nothing. Every job keeps its loopback server and its loopback health probe, and a test added by this plan fails the build if any job ever sets the new value. |
| **The rule this plan is built on** | **A program that starts its own server probes loopback. A program that only talks to one reads the setting.** The repository holds thirty addresses. Five of them belong to programs that do not start a server. Those five move. The other twenty-five are correct as literals and stay. |
| **Hard scope - in** | One environment value, `LLAMA_BASE_URL`, read once in `backend/idhazh/llm/server.py`; the two endpoint constants rebuilt from it; `DEFAULT_HEALTH` deleted; one `INFO` record saying which server answered; the `--base` defaults of `backend/utilities/measure_budgets.py` and `backend/utilities/measure_judge_call.py`; one test asserting no job sets the value; three code comments and two documentation sentences that today claim a project rule that does not exist. |
| **Hard scope - out** | Table B below. Five items, each with what it costs to leave out. |
| **Supersedes** | The surviving half of row 21 of [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md). Table C below records what that row asked for and what happened to each part. |
| **Depends on** | Nothing. Two plans are live in the same area and neither blocks this one. [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) line 34 hands the host to this plan by name. Its first pull request edits one docstring in `backend/idhazh/llm/server.py`, around line 437, which is the only file the two plans share and nowhere near the lines this plan edits. Whoever lands second rebases one hunk. [`20260922-46-one-writer-for-the-corpus-plan.md`](20260922-46-one-writer-for-the-corpus-plan.md) shares no file at all. |
| **ESCALATE triggers** | Four, listed below the decision request. |
| **Chosen strategy** | One value that is a whole base URL, not a host and not a port. Every address this module builds is derived from it, so a run cannot ask one server for a template and a different server for an answer. |
| **Execution** | Two pull requests that share no file and can run at the same time from the first minute. Six rows. |

### The owner question this plan carries

This is a decision for the owner (`CLAUDE.md` section 0 and section 1). It does not block authoring. It **does** block merging row 2.

**Situation.** Three places in the code and one page in the documentation say that hosted inference is forbidden by `CLAUDE.md` section 0a. Section 0a lists exactly one non-goal, accessibility audit tooling. The rule those four places cite is not written anywhere.

**Problem.** Those four sentences are the only text in this repository that says where article text fetched from the open web is allowed to go. They are wrong about their citation, so this plan deletes them. Row 2 then adds a setting that repoints where that text is sent. Deleting the only statement of a limit in the same plan that adds the lever which crosses it leaves the project with no written position at all.

**Impact.** Article text is untrusted third-party content under Guardrail #11, and this plan gives an operator a one-line way to send it to any HTTP endpoint on the internet. The mechanical control this plan ships is the census test in row 5: no automated job can set the value, so nothing published from CI can ever reach a foreign server. What is missing is the written rule for a person running the pipeline by hand.

**Options.**

| id | Option | What it costs | What it gives up |
| --- | --- | --- | --- |
| A1 | **Add a clause to Guardrail #11**: article text fetched from the open web is sent only to a model process the operator of this run controls, and a run that sent it elsewhere is not a run this project publishes. **Recommended** | One paragraph in `CLAUDE.md`, landed in row 2's pull request. An amendment to a guardrail is the owner's to make and no agent's (section 1). | Nothing. The clause describes what is already true of every run this repository has ever made. |
| A2 | Add hosted inference to the section 0a non-goal list | One line in `CLAUDE.md`. | The honest reading of the four deleted sentences, which was about where article text goes, not about which vendor runs the model. It also closes a door this plan exists to open: a second machine on the developer's own desk is hosted inference by that wording. |
| A3 | Write nothing, ship the lever, rely on the census test | Nothing today. | The written rule. The test stops a job; it does not stop a person, and the person is the one this plan is for. |
| A4 | Hold row 2 until the owner rules | One round trip. | The developer with the 16 GB laptop waits. |

**Recommendation: A1.** It states the limit that actually matters - who controls the process that receives the text - without forbidding the second machine this plan is built for, and it lands in the same pull request that removes the sentences it replaces.

### ESCALATE triggers

1. **Stop** if any row would leave the python client resolving to one server while the job's readiness probe checks a different one. A probe that clears a server nobody talks to is worse than no probe, and it is the exact split that the comment at `backend/idhazh/llm/server.py` lines 42 to 47 exists to prevent.
2. **Stop** if the new value turns out to be set in any environment where `pytest` runs. `backend/tests/workflows/test_model_server_jobs.py` asserts around line 457 that `DEFAULT_ENDPOINT` begins with the loopback address the workflows use. A developer who exports the value and then runs the suite turns that test red for a reason that has nothing to do with their change. Row 5 fixes that test; until row 5 lands, this trigger is live.
3. **Stop and ask** for the owner ruling above before merging row 2.
4. **Stop** if any row would raise a runner budget figure. The 6 hour job limit and the 1 GB site limit are GitHub's and cannot be moved (Guardrail #2).

### Table B - Hard scope - out

| id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | The 22 loopback lines in `.github/`, across `actions/model-server/action.yml`, `workflows/digest.yml`, `workflows/idhazh-pipeline-tests.yaml`, `workflows/measure.yml` and `workflows/validate.yml` | Nothing today. Every one is a `curl` health probe or a metrics read aimed at a server the same job just started on the same machine. Moving them would buy a capability that cannot be used: no launcher in this repository passes `--host` to `llama-server`, so nothing here ever binds off loopback. | A job that talks to a server it did not start. That is a different design and it brings the readiness probe, the secret handling and the failure mode with it. |
| B2 | The six addresses inside `backend/utilities/measure_probability_mode.py`, `measure_two_calls.py` and `runtime_sweep.py` | Nothing. Each of those three starts its own server with `subprocess.Popen` and then talks to it. The address is how the parent finds the child it just made. A setting there would let an instrument measure a server it is not running. | Nothing in sight. These are correct as literals. |
| B3 | Reconciling `/props` against the fingerprint the run records | A real defect, deferred with its home named. `PipelineInputs` carries nine fields all read from this process's environment. A run against a second machine stamps that machine's answers with this machine's build, so the record validates and is wrong. Row 6 writes one sentence into [`docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) saying so, because that page owns the record. | The refusal path needs an unrecorded state on a persisted shape, which is a version stamp, a changelog line, a read-side migration and a fixture (`CLAUDE.md` section 11). The measurement that would size it: `curl -s http://127.0.0.1:8080/props \| jq 'keys'` against the pinned build, which takes seconds. |
| B4 | Making the address a field in `config/` | Nothing. It is a process-boundary value: the machine the process talks to, not a knob that changes what the pipeline decides. A config field would also give `idhazh.fingerprint` something to classify, which is what the comment at `server.py` lines 42 to 47 already refuses for the port, on the same grounds (Guardrail #6, `CLAUDE.md` section 11). | A second setting that changes an output. There is none. |
| B5 | Adding hosted inference to the `CLAUDE.md` section 0a non-goal list | The four sentences that claim it exists are deleted by row 1 regardless, because a citation to a rule that is not written is a false citation. What it costs is a written position, and option A1 above is the recommended way to get one. | The owner's ruling on the decision request above. |

### Table C - What plan 39 row 21 asked for, and what happened to each part

| id | What row 21 asked for | Outcome |
| --- | --- | --- |
| C1 | One request builder instead of four | **Refused.** The four builders at `server.py` are four different shapes carrying four different Guardrail #11 controls: the chat builder sends `response_format` with a `json_schema`, the plain completion builder sends a top-level `json_schema`, the grammar builder sends a `grammar`, and the continued builder re-asserts the `json_schema` on a prompt the cache already holds. Collapsing them collapses the controls. |
| C2 | Move to the widely supported `/v1/completions` route | **Refused by a measurement** dated after the row was written and recorded at `server.py` lines 58 to 66: **both** completion routes, llama-server's native `/completions` and the OpenAI-compatible `/v1/completions`, ignore `response_format` and honour a top-level `json_schema`, on build b10444-5f754ea0e as of 2026-09-12. The chat route is not in that measurement and does honour `response_format`. |
| C3 | Delete three slot columns | **Refused.** `backend/utilities/slot_probe.py` is their named instrument. |
| C4 | Stamp the decode mode | **Done** in pull request #1036. |
| C5 | Stop naming a server in source | **This plan.** |

### Table D - What a change of address costs today, measured on `origin/main`

| id | Reading | Number | What it means |
| --- | --- | --- | --- |
| D1 | Lines a developer must edit to point the pipeline at another machine | 3 | All three in `backend/idhazh/llm/server.py`, and all three must be kept out of every commit for as long as the second machine is in use. |
| D2 | Settings, flags or environment values that reach those 3 lines | 0 | `LLAMA_PORT` reaches the port. Nothing reaches the host. |
| D3 | Places in `backend/` that import `DEFAULT_ENDPOINT` | 26, across 13 files | All of them become correct the moment the 3 lines are correct, which is why this plan is 6 lines of real change and not a refactor. |
| D4 | Readers of `DEFAULT_HEALTH` | 0 | The constant is defined and never used anywhere in the repository. Row 2 deletes it. |
| D5 | Command-line flags anywhere that set a model address | 3 | `--base-url` on the judging shard in `backend/idhazh/cli.py` line 517, and `--endpoint` on `backend/utilities/slot_probe.py` and `backend/utilities/prompt_loop.py`. All three already default to a constant from `server.py`, so all three follow the new value with no edit. |
| D6 | Stage functions taking an endpoint argument that nothing fills | 6 | In `work.py`, `two_calls.py`, `validate.py`, `qualify.py`, `qualify_canaries.py` and `judge_item_pairs.py`. Each already falls back to the module constant. This plan leaves all six alone: making them reachable from the command line is a second change with its own argument surface. |
| D7 | Loopback addresses in the repository, total | 30 | 22 in `.github/`, 6 in the three self-spawning instruments, 2 in the two measuring clients. Five move: three constants and the two client defaults. |

---

## 1. Status Reckoner

Statuses: PENDING, IN PROGRESS, BLOCKED, DONE. A row's status is stamped by the change that moves it, in that same change. Workers update their own line and nothing else.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Delete the rule that is not written | none | P1 | PENDING | - | - | - |
| 2 | One address, and a run can set it | 1 | P1 | PENDING | - | - | - |
| 3 | The run says which server answered | 2 | P1 | PENDING | - | - | - |
| 4 | The two measuring clients read the address | 2 | P1 | PENDING | - | - | - |
| 5 | No job may set the address | none | P2 | PENDING | - | - | - |
| 6 | Say what the run record cannot know | none | P2 | PENDING | - | - | - |

### 1a. The two pull requests

| Pull request | Rows | Files it touches | Worker |
| --- | --- | --- | --- |
| **P1 - the address** | 1, 2, 3, 4 | `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`, `backend/utilities/measure_budgets.py`, `backend/utilities/measure_judge_call.py`, `docs/how-to/run-the-pipeline.md`, and `CLAUDE.md` if the owner takes option A1 | one |
| **P2 - the guards** | 5, 6 | `backend/tests/workflows/test_model_server_jobs.py`, `docs/architecture/contracts/determinism.md` | one |

The two lists share nothing, so both start in minute one. Peak: two people at a time.

### 1b. Why rows 1 to 4 are one pull request and not four

Rows 1 and 2 edit the same lines of the same file, so they were never going to be parallel. Row 4 is different and is the reason the grouping is written down: its files, the two measuring clients, are disjoint from row 2's, so a pool that decides readiness by file overlap would start it immediately - and it would fail, because row 4 imports a constant row 2 has not declared yet. **A readiness check that compares file lists cannot see an import.** Holding rows 2, 3 and 4 in one branch in commit order removes that failure instead of managing it. Row 3 is in the same branch for the same reason: it edits row 2's file.

The whole of P1 is about six lines of changed behaviour. A second pull request for any part of it buys a gating cycle and nothing else.

---

## 1c. The contracts, declared before any code

`CLAUDE.md` Guardrail #3 puts the contract before the logic. Nothing below is persisted, so nothing below needs a Pydantic model or a schema stamp - the contract here is the shape of a boundary value, the shape of a log record, and the exact text of what is deleted. A worker implements this section and invents nothing.

### C1 - `LLAMA_BASE_URL`, the one setting this plan adds

| Property | Value |
| --- | --- |
| Name | `LLAMA_BASE_URL` |
| Kind | Environment value, read once at module load of `backend/idhazh/llm/server.py`. Not a `config/` field (Table B row B4). |
| Value | Scheme, host and port, and nothing else. `http://192.168.1.20:8080`. A trailing `/` is accepted and dropped. |
| Default when unset or empty | `http://127.0.0.1:{LLAMA_PORT}`, and `LLAMA_PORT` itself defaults to `8080`. This is character-for-character today's behaviour. |
| Refused | A value with no scheme, a value with no host, or a value carrying a path, a query or a fragment. Refused at load with `ValueError` naming the variable and the value. |
| Why a path is refused | `_sibling()` builds every other route by replacing the whole path of the endpoint. A base URL with a path prefix would be silently dropped from four of the five routes, which is a wrong answer rather than an error. Supporting a prefix means changing `_sibling` and its test, and that is a separate change with a separate reason. |
| Why a whole URL and not a host | A host cannot carry a scheme, so a server behind TLS still needs a source edit. A host plus a port is two values that can disagree. And `LLAMA_HOST` is what `llama-server` itself calls its **bind** address, so an operator who set it would reasonably expect the server to listen there - it would not, and that is the same server-and-client-disagree failure the comment at `server.py` lines 42 to 47 was written to prevent. This repository already speaks base URLs: `--base-url` in `cli.py`, `--base` in two utilities. |
| Why not validated further | Whether the host answers is knowable only at the first request, and the first request already reports it. |

### C2 - the helper that reads it

Added directly above the constants in `backend/idhazh/llm/server.py`. `urlsplit` and `urlunsplit` are already imported at line 35; nothing new is imported for this.

```python
def _base_url(declared: str | None, *, port: int) -> str:
    """Scheme, host and port of the server this run talks to.

    One value for the whole run, so a run cannot ask one server to render a
    template and a different server to answer. A path, a query or a fragment is
    refused rather than dropped: `_sibling` builds every other route by replacing
    the path, so a prefix would survive on one route and vanish from four.
    """
    if not declared:
        return f"http://127.0.0.1:{port}"
    parts = urlsplit(declared.rstrip("/"))
    if not parts.scheme or not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError(
            "LLAMA_BASE_URL must be a scheme, a host and a port and nothing else, "
            f"not {declared!r}"
        )
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))
```

### C3 - the constants after row 2

The comment at lines 42 to 47 keeps its ruling and gains the new value. `DEFAULT_PORT` at line 48 does not change, so every port assertion in `backend/tests/workflows/test_model_server_jobs.py` passes untouched.

```python
DEFAULT_PORT: Final = int(os.environ.get("LLAMA_PORT") or 8080)
DEFAULT_BASE_URL: Final = _base_url(os.environ.get("LLAMA_BASE_URL"), port=DEFAULT_PORT)
DEFAULT_ENDPOINT: Final = f"{DEFAULT_BASE_URL}/v1/chat/completions"
```

and, below the 2026-09-12 route measurement that stays exactly as written:

```python
DEFAULT_COMPLETION_ENDPOINT: Final = f"{DEFAULT_BASE_URL}{_COMPLETION_PATH}"
```

`DEFAULT_HEALTH` is **deleted**. It is defined at line 50 and read nowhere in the repository. It would have been the one constant most likely to disagree with the others after this change, and the cheapest way to make sure it never does is to remove a name nothing uses.

Three names the comment must carry, in plain words: the value is the address of a machine, not a tuning knob; it is read once so every route agrees; and `idhazh.fingerprint` has nothing to classify from it (Guardrail #6, `CLAUDE.md` section 11).

### C4 - the log record row 3 adds

The only control that ships with the lever. It answers, from a run's own stderr, the one question the lever creates: which machine answered.

| Property | Value |
| --- | --- |
| Where it is emitted | Inside `post()`, the single place an item is sent. Not at module import - that fires during test collection, in every process that so much as imports the module. Not once per stage either: `prove_the_entry` looked like the right site and is not, because only `backend/utilities/prove_the_entry.py` calls it and no stage does. |
| How often | Once per process per distinct address, by `functools.lru_cache`. A run that talks to one server logs one line. |
| Level | `INFO` |
| Logger | `LOG: Final = logging.getLogger("idhazh")` at module level, matching the eight other modules in `backend/idhazh/`. `logging` and `functools.lru_cache` are new imports in this file. |
| What it prints | The scheme, the host and the port, and whether that is the built-in default. |
| What it must never print | **`parts.netloc`.** Netloc carries userinfo, so `http://user:token@box:8080` would put the token in the log verbatim. Use `parts.hostname` and `parts.port`, which drop it. Never the path, the query, a header, or any part of the payload (`CLAUDE.md` section 1b). |

```python
@lru_cache(maxsize=None)
def _note_origin(endpoint: str) -> None:
    """Say once which server this run is talking to.

    `hostname` and `port` rather than `netloc`: netloc carries userinfo, and a
    credential in an address must not reach a log record (`CLAUDE.md` section 1b).
    """
    parts = urlsplit(endpoint)
    LOG.info(
        "model server origin=%s://%s:%s default=%s",
        parts.scheme,
        parts.hostname,
        parts.port,
        endpoint == DEFAULT_ENDPOINT,
    )
```

### C5 - the four sentences row 1 deletes, and what replaces them

Each cites `CLAUDE.md` section 0a for a rule section 0a does not contain. Section 0a lists one non-goal and it is accessibility audit tooling. **Every replacement states a fact about what the code does. None of them states a scope rule** - the scope rule is the owner's to write and it is the decision request in section 0.

| id | File | The sentence, by its opening words | What replaces it |
| --- | --- | --- | --- |
| C5a | `backend/idhazh/llm/__init__.py`, the second paragraph | "Nothing in this package reaches any origin but loopback. Hosted inference is a project non-goal..." | "The address this package talks to defaults to loopback and is read in one place, `idhazh.llm.server`, for the whole run. The OpenAI-shaped transport here exists because it is the format local runtimes already speak." |
| C5b | `backend/idhazh/llm/server.py`, module docstring, third line | "Nothing here is hosted - `CLAUDE.md` section 0a forbids that." | "The address is a process-boundary value and defaults to loopback. Nothing in this module starts a server." The rest of that paragraph, beginning "Two transports," is unchanged. |
| C5c | `backend/idhazh/llm/server.py`, the `post()` docstring at line 962 | "Loopback only, by construction." | "One address for the whole run, and `_note_origin` says once which one." |
| C5d | `docs/how-to/run-the-pipeline.md`, lines 45 to 48 | "The summarize stage talks to `127.0.0.1:8080` and nothing else... There is no hosted inference anywhere in this project (section 0a)." | The paragraph in C8 below. |

C5c cannot be written until row 3 exists, so row 1 leaves that one sentence for row 3 and row 3 deletes it. Every other part of C5 lands in row 1.

### C6 - the two command defaults row 4 changes

Both are clients: neither starts a server, and neither contains a `subprocess.Popen`. That is the whole test that separates them from the three instruments in Table B row B2.

| File | Line | Today | After |
| --- | --- | --- | --- |
| `backend/utilities/measure_budgets.py` | 607 | `read.add_argument("--base", default="http://127.0.0.1:8080")` | `default=DEFAULT_BASE_URL` |
| `backend/utilities/measure_judge_call.py` | 741 | `parser.add_argument("--base", default="http://127.0.0.1:8080")` | `default=DEFAULT_BASE_URL` |

Both import `DEFAULT_BASE_URL` from `idhazh.llm.server`. Neither loses its `--base` flag: an explicit flag still beats the value, and `.github/workflows/measure.yml` line 1017 passes `--base "http://127.0.0.1:${LLAMA_PORT}"` explicitly, so that job's behaviour does not change at all.

### C7 - the test row 5 adds, and the test it repairs

**The new one.** A census over `.github/`, asserting that no file there sets `LLAMA_BASE_URL`. Unit tier. It reads a fixed directory of workflow files, not a collection any run appends to, so it satisfies `CLAUDE.md` section 13 and Guardrail #12. It goes red only when a person edits the tree, which is the edit this plan needs caught.

```
For every *.yml and *.yaml under .github/:
    assert "LLAMA_BASE_URL" not in the file's text
Failure message: names the file and says that a job talks to the server it
started, so the address it uses is the loopback port `LLAMA_PORT` names.
```

**The repair.** `backend/tests/workflows/test_model_server_jobs.py` asserts around line 457 that `DEFAULT_ENDPOINT` begins with the workflows' loopback address. That assertion goes red for any developer who has exported `LLAMA_BASE_URL` and then runs the suite, for a reason unrelated to their change. The fix is one line: `monkeypatch.delenv("LLAMA_BASE_URL", raising=False)` and a reload of `idhazh.llm.server` before the assertion. Safe to write before row 2 lands, because deleting a variable that does not exist is a no-op.

**The pattern for row 2's own test**, which must exercise the set case in a module whose constants are computed at import:

```python
def test_a_declared_base_url_moves_every_route(monkeypatch):
    monkeypatch.setenv("LLAMA_BASE_URL", "http://192.168.1.20:9090")
    module = importlib.reload(idhazh.llm.server)
    try:
        assert module.DEFAULT_ENDPOINT == "http://192.168.1.20:9090/v1/chat/completions"
    finally:
        monkeypatch.delenv("LLAMA_BASE_URL")
        importlib.reload(idhazh.llm.server)
```

The reload in `finally` is not optional: a module left reloaded with a foreign address leaks into every test that runs after it in the same process.

### C8 - the documentation sentences

**`docs/how-to/run-the-pipeline.md`**, replacing lines 45 to 48. This page, not `docs/architecture/summarize/model-boundary.md`, is where the change is recorded: it is where the developer this plan is for actually reads, it is the page whose current text becomes false, and it is not a page any other live plan owns.

> The summarize stage talks to `http://127.0.0.1:8080`. Set `LLAMA_PORT` before both commands to move the port - the server command and the client read the same variable. To use a server on another machine, set `LLAMA_BASE_URL` to its scheme, host and port, for example `http://192.168.1.20:8080`. The client reads it; the server command ignores it, because that server is not this command's to start. Every job in `.github/` runs its own server on loopback, and a test refuses any job that sets `LLAMA_BASE_URL`.

**`docs/architecture/contracts/determinism.md`**, row 6. One sentence appended to the paragraph that already discusses `/props`, because that page owns the run record:

> A run that sets `LLAMA_BASE_URL` stamps the second machine's answers with this machine's `runtime_build` and `runner_class`, both of which are read from this process's environment. The record validates and is wrong, and reconciling it against `/props` is not done.

`python backend/utilities/doc_load.py` runs before and after the documentation edit in each pull request, and the split test is applied to any page a section is added to (`CLAUDE.md` section 9). Both edits here replace or extend existing text rather than adding a heading, so neither page is expected to move.

### C9 - the commit order in P1

One commit per row, in this order. A worker who follows it never has an import that points at a name that does not exist yet.

| Commit | Row | Hat |
| --- | --- | --- |
| 1 | 1 | structural - text only, no behaviour |
| 2 | 2 | behavioural - the setting, the constants, the deletion, the test, the doc |
| 3 | 3 | behavioural - the logger and the record |
| 4 | 4 | behavioural - the two defaults |

---

## 2. Row 1 - Delete the rule that is not written

**Scope.** Remove the four claims that `CLAUDE.md` section 0a forbids hosted inference, and replace each with a statement of what the code actually does, per contract C5.

**Files touched.** `backend/idhazh/llm/__init__.py`, `backend/idhazh/llm/server.py`, `docs/how-to/run-the-pipeline.md`.

**Acceptance gates.**

- `ruff check .` from the repository root is clean.
- `python backend/utilities/doc_load.py` before and after the documentation edit; no page crosses a test it was passing.
- No new heading is added to `run-the-pipeline.md`, so no split test is owed.
- No browser smoke: nothing published changes (`CLAUDE.md` section 12).

**Oracle.** `git grep -n "section 0a" -- backend/idhazh/llm docs/how-to/run-the-pipeline.md` returns nothing.

**What the oracle cannot settle.** Whether the project should have the rule those sentences described. That is the decision request in section 0 and it is the owner's.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 1.1 | An agent makes this correction and reports it; it is not owner-gated | A rule that is not in the contract cannot gate a plan, and deleting a wrong cross-reference changes no behaviour, which is level 0 work (`CLAUDE.md` section 6). Fowler, reversing an earlier call after the section 0a text was read. |
| 1.2 | Every replacement states a fact, never a scope rule | An agent may not write a project rule for itself (`CLAUDE.md` section 1). The facts are true today and stay true after row 2. |
| 1.3 | The `post()` sentence, C5c, is left to row 3 | Its replacement names `_note_origin`, which row 3 creates. Naming a function before it exists is the defect this plan is otherwise removing. |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 1.R1 | Fix the citation to point at Guardrail #11 instead | Guardrail #11 is about fetched text becoming instruction, not about where it is sent. The citation would be wrong in a new way. | One line, and a false statement left in three files. |
| 1.R2 | Leave the sentences and add section 0a to the contract | It writes a project rule to make four comments true, in a plan about an environment value. And the rule as written would forbid a second machine on the developer's own desk, which is what this plan exists to allow. | One line in `CLAUDE.md`, the owner's approval, and the plan's own purpose. |
| 1.R3 | Delete the sentences and write nothing at all | Leaves no statement of what the module does with its address. | Nothing to write. A reader learns less than they do today. |

---

## 3. Row 2 - One address, and a run can set it

**Scope.** Add `_base_url` and `DEFAULT_BASE_URL` per contracts C1 and C2, rebuild `DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` from it per C3, delete `DEFAULT_HEALTH`, and record the change in `docs/how-to/run-the-pipeline.md` per C8.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`, `docs/how-to/run-the-pipeline.md`, and `CLAUDE.md` if the owner takes option A1.

**Acceptance gates.**

- `ruff check .` clean from the repository root.
- `pytest backend/tests/test_summarize.py backend/tests/workflows/test_model_server_jobs.py` green. Both, not either: the second is the one that proves CI is untouched.
- The unit test from C7 passes in both directions - unset gives today's address, set gives the declared one - and the refusal case raises for a value with no scheme.
- The existing assertion at `backend/tests/test_summarize.py` line 482, `completion_url("http://127.0.0.1:8181") == "http://127.0.0.1:8181/completions"`, still passes unchanged. It is the proof that the derivation of sibling routes did not move.
- `python backend/utilities/doc_load.py` before and after.
- CI is authoritative for the full suite (`CLAUDE.md` section 9).

**Oracle.** With `LLAMA_BASE_URL` unset, `DEFAULT_ENDPOINT` and `DEFAULT_COMPLETION_ENDPOINT` are byte-identical to `origin/main`. With it set to `http://192.168.1.20:9090`, both carry that host and port. `git grep -c DEFAULT_HEALTH` returns nothing.

**What the oracle cannot settle.** Whether a real second machine answers. Nothing in this repository binds a server off loopback, so the first genuine end-to-end proof is a person running a server elsewhere by hand. The plan does not claim otherwise, and the trigger under ESCALATE #1 is what guards the half-done version of it.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 2.1 | A whole base URL, `LLAMA_BASE_URL`, not a host and not a host plus a port | C1's table gives the four reasons. The shortest is that a host cannot carry a scheme, so a TLS server would still need the source edit this plan exists to remove. |
| 2.2 | No `default_base_url()` accessor function | The module already has exactly one place that composes an address, `_sibling`. A second composition point for two call sites is an abstraction two callers have not earned. |
| 2.3 | `DEFAULT_HEALTH` is deleted, and no `health_url()` replaces it | It has zero readers. A replacement would land with zero readers too, which is the same defect with a newer name. It goes in when its first caller does. |
| 2.4 | A path, query or fragment in the value is refused, not accepted and not silently dropped | `_sibling` replaces the whole path, so a prefix would hold on one route and vanish from four. A wrong answer is worse than an error. |
| 2.5 | `LLAMA_PORT` survives untouched and still builds the default | Every port assertion in `test_model_server_jobs.py` then passes with no edit, and no job in `.github/` changes at all. |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 2.R1 | `LLAMA_HOST` | Cannot express a scheme or a port on its own, so the source edit survives for a TLS server. And `llama-server` already uses that name for its **bind** address: an operator who set it would expect the server to listen there, it would not, and client and server would then disagree about where the model is - the failure the comment at lines 42 to 47 exists to prevent. | One line, and the same edit again the first time someone needs `https`. |
| 2.R2 | A `config/` field | Table B row B4. It is a machine address, not a knob that changes an output, and a field would give `idhazh.fingerprint` something to classify. | A schema field, a stamp, a changelog line and a migration, for a value no output depends on. |
| 2.R3 | A `--endpoint` flag on every stage that already takes the argument | Six stage functions take an endpoint that nothing fills. Wiring all six is a real improvement and a bigger argument surface than this plan's reason needs. One environment value reaches all 26 import sites at once. | Six flags, six help strings, six tests, and a command-line surface nobody asked for. Worth revisiting when a run genuinely needs two different servers in one pipeline. |
| 2.R4 | Keep `DEFAULT_HEALTH` and rebuild it from the base too | Three lines that agree is better than three lines where one is never checked. An unread constant is the one most likely to drift. | One line, and a name that still has no readers. |

---

## 4. Row 3 - The run says which server answered

**Scope.** Add a module logger and the one-shot origin record in `post()`, per contract C4, and apply C5c.

**Files touched.** `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`.

**Acceptance gates.**

- `ruff check .` clean.
- A unit test asserting the record contains the host and the port and **does not contain** a userinfo string. Drive it with `caplog` and an endpoint of the form `http://user:token@box:8080/v1/chat/completions`; assert `"token" not in caplog.text`.
- A unit test asserting a second `post()` to the same address adds no second record.
- No secret, header or payload fragment appears in any record (`CLAUDE.md` section 1b).

**Oracle.** Running the summarize stage prints exactly one `model server origin=` line at `INFO`, carrying the scheme, host and port, and `default=True` when nothing is set.

**What the oracle cannot settle.** Whether anybody reads it. It costs eight lines and it is the only thing in the run that can answer "which machine produced this" after the fact, which is the question the setting creates.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 3.1 | Emitted from `post()`, memoised with `lru_cache`, not from module import | Module import fires in every process that imports the module, including test collection. `post()` is the single place an item is sent, so a process that logs is a process that actually talked to a server. |
| 3.2 | Not from `prove_the_entry` | It looked like the natural once-per-stage site and it is not one: its only caller in the repository is `backend/utilities/prove_the_entry.py`, a hand-run utility. No stage calls it, so the record would never fire in production. |
| 3.3 | `parts.hostname` and `parts.port`, never `parts.netloc` | Netloc carries userinfo. A credential in an address must not reach a log record. |
| 3.4 | `LOG: Final = logging.getLogger("idhazh")` | The name eight other modules in `backend/idhazh/` already use, so the record lands under the same configuration as the rest of the run. |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 3.R1 | Put the address in the run manifest instead of a log record | A manifest field is a persisted shape: a version stamp, a changelog line, a read-side migration and a fixture (`CLAUDE.md` section 11). It also raises the reconciliation question in Table B row B3, which this plan defers. | The full section 11 cost, for a value that is the same in every run CI makes. |
| 3.R2 | Log per item | Answers the same question thousands of times per run and buries everything else. | Nothing to write, and a log a person stops reading. |
| 3.R3 | Log nothing | The setting then changes where article text goes with no trace in the run's own output. | Nothing. It is the option this plan refuses, because a lever with no control is what Guardrail #11 is about. |

---

## 5. Row 4 - The two measuring clients read the address

**Scope.** Change the two `--base` defaults to `DEFAULT_BASE_URL`, per contract C6.

**Files touched.** `backend/utilities/measure_budgets.py`, `backend/utilities/measure_judge_call.py`.

**Acceptance gates.**

- `ruff check .` clean.
- Both scripts still parse their arguments and still accept an explicit `--base`.
- `.github/workflows/measure.yml` is not edited. It passes `--base` explicitly at line 1017, so that job's behaviour is identical.

**Oracle.** `git grep -n '127\.0\.0\.1' -- backend/utilities` returns exactly six address lines, all inside `measure_probability_mode.py`, `measure_two_calls.py` and `runtime_sweep.py`, plus `capture_server_argv.py` line 34 where `8080` is a port constant and `slot_probe.py` line 16 where it is an example inside a docstring. Every one of those files either starts its own server or is documenting one.

**What the oracle cannot settle.** Nothing outstanding. It is stated as a list of survivors rather than as "zero occurrences" precisely because zero is not the correct answer and an earlier draft of this plan claimed it was.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 4.1 | These two move and the other three do not | The sorting rule in section 0: these two have no `subprocess.Popen` and talk to a server somebody else started. The other three start their own with `Popen` and then find it by address. |
| 4.2 | The `--base` flag survives on both | An explicit flag beats an environment value, and `measure.yml` relies on that. |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 4.R1 | Move all eight addresses under `backend/utilities/` | Six of them are how a parent process finds the child it just started. A setting there lets an instrument measure a server it is not running, and then report a number about the wrong binary. | Six lines, and a class of silently wrong measurement. |
| 4.R2 | Leave these two alone as well | The two measuring clients are exactly the tools a developer on a second machine reaches for, and they would still need a flag every time. | Nothing to write, and the plan's beneficiary keeps typing an address. |

---

## 6. Row 5 - No job may set the address

**Scope.** Add the `.github/` census test and repair the environment sensitivity of the existing endpoint assertion, per contract C7.

**Files touched.** `backend/tests/workflows/test_model_server_jobs.py`.

**Acceptance gates.**

- `pytest backend/tests/workflows/test_model_server_jobs.py` green.
- The new test goes red when a `LLAMA_BASE_URL` line is added to any workflow file, and green again when it is removed. Prove it once, by hand, and restore the file from the commit rather than from the working tree.
- The repaired assertion passes with `LLAMA_BASE_URL` exported in the shell.

**Oracle.** With `$env:LLAMA_BASE_URL = 'http://192.168.1.20:9090'` set in the shell, the whole of `backend/tests/workflows/` is green.

**What the oracle cannot settle.** A person running the pipeline by hand. The test binds jobs, not people. The written rule for people is the decision request in section 0.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 5.1 | The census is unit tier and reads a fixed directory | `.github/` is not a collection a run appends to, so the test's cost does not grow with the repository (Guardrail #12, `CLAUDE.md` section 13). |
| 5.2 | This row shares no file with P1 and starts at the same time | It needs only the agreed name of the value, which contract C1 fixes. |
| 5.3 | The repair is safe to land before row 2 | Deleting an environment variable that does not exist yet is a no-op. |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 5.R1 | Refuse the value in code when a CI environment variable is present | Puts a rule about the build inside the module the build uses, and it can be defeated by unsetting one variable. A test states the rule where a reviewer sees it. | Three lines, and a control that lives on the wrong side. |
| 5.R2 | No census at all | The setting could then be added to a workflow in one line, and article text from the open web would leave the runner with no gate. | Nothing to write. It is the control the section 0 decision request is built around. |

---

## 7. Row 6 - Say what the run record cannot know

**Scope.** Append one sentence to the `/props` paragraph of `docs/architecture/contracts/determinism.md`, per contract C8.

**Files touched.** `docs/architecture/contracts/determinism.md`.

**Acceptance gates.**

- `python backend/utilities/doc_load.py` before and after; the page does not cross a test it was passing.
- No heading is added, so no split test is owed.
- No local application suite: this is a documentation-only closure (`CLAUDE.md` section 9).

**Oracle.** The page names `LLAMA_BASE_URL` and says which two fingerprint fields become wrong.

**What the oracle cannot settle.** The defect itself. This row records it where the record is owned; fixing it is Table B row B3, and the measurement that would size it is named there.

**Decisions.**

| id | Decision | Reason |
| --- | --- | --- |
| 6.1 | The sentence goes in `determinism.md`, not only in this plan | A plan under `TODO/` is a cache, not the memory. A deferred defect written only here disappears when the plan closes (Guardrail #4). |
| 6.2 | One sentence, not a section | A deferred defect that has not been sized does not earn a heading, and a heading would put this page back through the split test for no gain. |

**Rejected alternatives.**

| id | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| 6.R1 | Fix the reconciliation in this plan | It needs an unrecorded state on a persisted shape: a version stamp, a changelog line, a read-side migration and a fixture. That is a level 5 conversation about a contract, not a line in a plan about an environment value. | The whole of `CLAUDE.md` section 11, plus a ruling on what a run should do when the server it reached is not the one the fingerprint describes. |
| 6.R2 | Block row 2 until the record is honest | CI never sets the value, so no published run can produce a wrong record. The only person who can is the one who set it deliberately, and this row is what tells them. | Two pull requests held for a defect that cannot occur in any run this project publishes. |

---

## See also

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - row 21, whose surviving half is this plan. Table C records the rest.
- [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) - hands the host to this plan at its line 34. Shares one file, `backend/idhazh/llm/server.py`, and no lines.
- [`../docs/how-to/run-the-pipeline.md`](../docs/how-to/run-the-pipeline.md) - where the change is recorded and where the developer this plan is for reads.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - owns the run record that row 6 annotates.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the pool, readiness, and the execution stamp.
