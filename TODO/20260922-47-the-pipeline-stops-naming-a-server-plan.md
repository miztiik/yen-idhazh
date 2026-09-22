# The pipeline stops naming a server

**Last Updated**: 2026-09-22

**Level**: 2. Three module constants gain an environment value, and five operator instruments read it instead of spelling an address. No persisted shape moves, no route changes, and no committed column is removed. Runs AUTO once the user authorizes.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan; keep parallel N = 1 row in flight - one, because row 2 imports the helper row 1 declares; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 39 row 21 is the one row of that plan no successor picked up, and most of what it asked for is now wrong. The decode stamp it wanted deleted went in #1036. The port it wanted a job to set is already `LLAMA_PORT`, read at `backend/idhazh/llm/server.py:48` and set by four workflows. What is left is one line of it that is still true: the **host** is spelled `127.0.0.1` in three module constants, reachable by no parameter, no config field and no environment variable, so pointing this pipeline at any other compatible server needs a source edit. Plan 40's fork probe and any future hosted comparison both need that edit not to exist. |
| The rule | **A process-boundary value is an environment value, not a config field.** `server.py:42-47` already states it for the port: two answers would leave a server listening on one address and a summarizer posting to another, and `idhazh.fingerprint` has nothing to classify. The host is the same kind of value and gets the same treatment. |
| Hard scope - in | Give the host the shape the port already has: one environment variable, read once at module scope, defaulting to what is spelled today. Repoint the five operator instruments that spell an address of their own at the same helper. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 39 row 21, which is listed there as orphaned. Three quarters of that row is refused or already done; the scope-out table prices each part. |
| Assumes | Nothing. No plan on disk touches `backend/idhazh/llm/server.py`, and this plan touches no file any of plans 40, 43, 44, 45 or 46 owns. |
| ESCALATE triggers | (1) If the default address this plan computes is not byte-identical to the string on `main` today, stop - every call site defaults to it and a changed default is a silent repoint of the whole pipeline. (2) If any change here reaches a request body, a route path or a committed column, stop: this plan moves an address and nothing else. (3) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Two rows, one pull request, two commits. Row 2 imports what row 1 declares, so they are never independent; splitting them into two pull requests buys nothing at N = 1 and costs a second 479 s gating wait. Carmack rules the process boundary; Fowler the module structure. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 - row 2 imports row 1's helper, so there is never a second ready row.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Replacing the four request builders with one** (plan 39 row 21's headline) | Four builders stay at `server.py:496`, `:554`, `:608`, `:783` | **Refused: they are four shapes, not four spellings of one.** `request_payload` posts a `messages` array to the chat route; `completion_payload` posts a `prompt` string to the native route; `grammar_completion_payload` carries a `grammar` field nothing else has; `continued_completion_payload` extends a prior body rather than building one. Each carries a different Guardrail #11 control, named in its own docstring - `response_format`, `json_schema`, `grammar`, and a prompt that is the previous prompt extended. Merging them merges four controls into one branch nobody can read. **What brings it in:** evidence that two of them build the same body, which a field-by-field diff of the four return values would settle in an afternoon |
| **Moving every call to the OpenAI-compatible `/v1/completions` route** ("the widely-supported shape") | The pipeline keeps posting to llama-server's own `/completions` | **Refused by a measurement that postdates plan 39 row 21.** `server.py:58-66`, measured 2026-09-12 on build b10444-5f754ea0e: both routes ignore `response_format` outright and both honour a top-level `json_schema`, but on the compatibility route that field survives a rewriting layer which already drops `response_format`, and no workflow pins a llama.cpp build. A build that started stripping it would turn constrained decoding off for every item at once, silently. That is a Guardrail #11 control and a reader-safety boundary. **What brings it in:** a pinned llama.cpp build plus a gate that fails when a constrained reply comes back unconstrained - both real rows, and neither is this one |
| **Deleting `slot_id`, `kv_tokens_at_start` and `prefix_shared_with_previous`** (plan 39 row 21's "two llama-specific slot cells"; there are three) | Three columns stay on `backend/idhazh/contracts/item_health.py` | **Refused: they have a named instrument and a recorded reason.** `backend/utilities/slot_probe.py` exists for exactly these three and names them in its first line; `backend/utilities/item_health_provenance.py:236-238` reads them; `docs/architecture/summarize/model-boundary.md:252-254` maps each to its llama-server field and `docs/architecture/sources/item-health-columns.md:303-304` records that they were the last three columns given a producer, deliberately. Plan 43 row 2's keep-rule binds here: a utility a page names as the instrument behind a reading is kept, whatever a caller census says. Measured 2026-09-22 across 30 committed item-health files: **1,668 of 14,346 rows carry all three, 11.6 percent** - the first call of a two-call stage, which is sparse by design rather than dead. **What brings it in:** the owner ruling that per-item cache provenance is not worth three columns, which is a measurement decision and theirs |
| **Deleting the decode-identity stamp** | Nothing | **Already done.** Plan 41's row "The decode stamp and the dead fingerprint go" merged in #1036 |
| **Making the host a `config/` field** | It stays an environment value | **Refused for the reason the port already carries at `server.py:42-47`.** A config field would reach `idhazh.fingerprint`, which classifies every config value into the run record's inputs digest, and an address is not an input that changes an output. Two committed runs against the same model on two hosts would stop comparing. **What brings it in:** a design where one run legitimately talks to more than one server, which nothing today does |

### What a change costs today

Measured on `origin/main`, 2026-09-22.

| Reading | Value | Where |
| --- | --- | --- |
| Places the host `127.0.0.1` is spelled in `backend/idhazh/` | **3** | `server.py:49`, `:50`, `:67` |
| Places it is spelled in `backend/utilities/` | **8, across 5 files** | `measure_budgets.py:607`, `measure_judge_call.py:741`, `measure_probability_mode.py:170` and `:172`, `measure_two_calls.py:109` and `:926`, `runtime_sweep.py:363` and `:379` |
| Config fields, CLI flags or environment variables that set the host | **0** | `config/`, `backend/idhazh/contracts/knobs/`, `backend/idhazh/cli.py` all searched |
| Environment variables that set the **port** | **1**, `LLAMA_PORT`, read at `server.py:48` | set by `digest.yml:82`, `llm-council.yml:63`, `measure.yml:113`, `validate.yml:87`, and `.github/actions/model-server/action.yml:13` |
| Call sites that take an `endpoint` and default it to `DEFAULT_ENDPOINT` | **26**, in 11 modules | `git grep -n DEFAULT_ENDPOINT -- backend` |
| Of those, how many already rebuild a second URL from the endpoint they were given | **4** - `props_url`, `completion_url`, `apply_template_url`, `tokenize_url` | `server.py:983`, `:988`, `:993`, `:998` |
| Call sites that pass a host other than the default today | **0** | derived from the census above |
| What the change is, in lines | **3 constants and one helper in `server.py`, 8 lines in 5 utilities** | derived |

## Section 0b - What this plan does, in one list

1. The host becomes an environment value read once beside the port, and the three module constants compose from it.
2. The five operator instruments that spell an address of their own read the same helper.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Pull request | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The host is a value a job sets, the way the port already is | - | P1 | PENDING | - | - | - |
| 2 | The instruments stop spelling an address of their own | 1 | P1 | PENDING | - | - | - |

### Section 1a - The one pull request

| PR | Rows | Kind | Files it owns |
| --- | --- | --- | --- |
| **P1 - the address** | 1, 2 | behavioural, **two commits**: the constant, then the instruments | `backend/idhazh/llm/server.py`, `backend/tests/test_summarize.py`, `backend/utilities/measure_budgets.py`, `measure_judge_call.py`, `measure_probability_mode.py`, `measure_two_calls.py`, `runtime_sweep.py`, `docs/architecture/summarize/model-boundary.md` |

**Why one pull request.** Row 2 imports the helper row 1 declares, so it cannot open first and cannot open beside it. A second pull request would cost one more 479 s gating wait and one more local gate pass at 452 to 1,098 s, measured 2026-09-22, and buy an independent revert of eight lines in five hand-run instruments.

**Why two commits.** Row 1 changes what every production call site resolves to. Row 2 changes five files nothing imports. A reviewer reading `git log -p` can check the first without the second in the way.

### Section 1b - The order

| Order | Row | Held until |
| --- | --- | --- |
| 1 | **1** | nothing. It can open the day the user authorizes |
| 2 | **2** | row 1 - the helper does not exist before it |

**Peak workers: 1.**

**This plan shares no file with plans 40, 43, 44, 45 or 46**, so it may run at any point in their sequence. Plan 40's fork probe is the one that benefits from it landing first: `runtime_sweep.py` is in row 2's list and plan 40 dispatches through it.

## Section 1c - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent the shape below; it reads this section.** No persisted payload changes, so CLAUDE.md section 11 does not apply and no version stamp or changelog entry is owed.

### C1 - The host value (row 1)

**An environment variable, not a config field.** It copies `DEFAULT_PORT` at `backend/idhazh/llm/server.py:48` exactly, including the reason written above it at `:42-47`.

| Property | Value |
| --- | --- |
| Name | `LLAMA_HOST` |
| Declared | `DEFAULT_HOST: Final = os.environ.get("LLAMA_HOST") or "127.0.0.1"`, on the line after `DEFAULT_PORT` at `server.py:48` |
| Default | `"127.0.0.1"` - the string spelled in all three constants today, so an unset variable produces byte-identical behaviour |
| Not a config field | For the reason `server.py:42-47` gives for the port: it is a process-boundary value, `idhazh.fingerprint` has nothing to classify, and an address is not an input that changes an output (Guardrail #6, CLAUDE.md section 11) |
| Not validated | A bad host fails at the first request with a connection error naming the address. There is no earlier moment at which a wrong one is knowable, so a check here would only restate the failure |
| Comment it carries | One line saying what it is for: a job that runs the server somewhere other than its own runner sets this, and nothing else reads it |

**The three constants recompose from it, and their spelling is otherwise unchanged:**

| Constant | Line | After |
| --- | --- | --- |
| `DEFAULT_ENDPOINT` | `server.py:49` | `f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/v1/chat/completions"` |
| `DEFAULT_HEALTH` | `server.py:50` | `f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/health"` |
| `DEFAULT_COMPLETION_ENDPOINT` | `server.py:67` | `f"http://{DEFAULT_HOST}:{DEFAULT_PORT}{_COMPLETION_PATH}"` |

**Nothing downstream changes.** The four URL builders at `server.py:983`, `:988`, `:993` and `:998` already take an endpoint and rebuild from it, so they carry a non-default host with no edit. The 26 call sites that default to `DEFAULT_ENDPOINT` inherit the new default. `backend/idhazh/cli.py:502` already exposes `--endpoint`.

### C2 - What the instruments read (row 2)

**One exported helper, not five copies of a format string.**

| Property | Value |
| --- | --- |
| Name | `default_base_url()` in `backend/idhazh/llm/server.py`, beside the four URL builders at `:983-1001` |
| Returns | `f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"` - scheme, host and port, no path |
| Why a function and not a constant | The five instruments each append a different path, and two of them take a port on the command line that overrides the environment. A function taking an optional port keeps one composition point: `default_base_url(port: int = DEFAULT_PORT) -> str` |
| Who calls it | the five files in row 2, and nothing in `backend/idhazh/` - the production path already composes from `DEFAULT_ENDPOINT` |

| File | Line | Reads today | After |
| --- | --- | --- | --- |
| `backend/utilities/measure_budgets.py` | `:607` | `--base` default `"http://127.0.0.1:8080"` | `default_base_url()` |
| `backend/utilities/measure_judge_call.py` | `:741` | `--base` default `"http://127.0.0.1:8080"` | `default_base_url()` |
| `backend/utilities/measure_probability_mode.py` | `:170`, `:172` | composes a chat endpoint and a health URL from a port | `default_base_url(port)` plus the two paths |
| `backend/utilities/measure_two_calls.py` | `:109`, `:926` | a health URL from a port, and a base from `args.server_port` | `default_base_url(port)` |
| `backend/utilities/runtime_sweep.py` | `:363`, `:379` | a health URL and a `/v1/models` URL from a port | `default_base_url(port)` plus the two paths |

**The two `8080` literals go with the strings that carry them.** `measure_budgets.py:607` and `measure_judge_call.py:741` are the only places the port is spelled a second time; after this row the port has one home, at `server.py:48`.

## Section 2 - Row 1 - The host is a value a job sets, the way the port already is

- **Scope:** Add `DEFAULT_HOST` beside `DEFAULT_PORT`, reading `LLAMA_HOST` with today's literal as the default, and compose the three address constants from it.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`:48-50` and `:67`, plus the helper in C2 so row 2 has something to import)
  - `backend/tests/test_summarize.py` (the new unit test below)
  - `docs/architecture/summarize/model-boundary.md` (the page that owns this boundary; it documents the slot columns at `:252-254` and is where the address belongs)
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'summarize or server or boundary' -q`, and `python backend/utilities/doc_load.py` before and after the doc edit; CI - full suite.
- **Oracle:** with `LLAMA_HOST` unset, all three constants are **byte-identical** to the strings on `main` - asserted by a test that compares each against its literal; and with `LLAMA_HOST` set to another value, all three carry it while the port, the paths and the scheme are unchanged. **This fails on the base tree today**: there is no `DEFAULT_HOST` to import, so the second half does not compile. **What it cannot settle:** whether a remote llama-server answers identically to a local one. Nothing here talks to a second server, and the first thing that does is plan 40's probe.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | An environment variable, not a config field. C1 gives the reason and `server.py:42-47` already carries it for the port | Carmack |
 | 2 | The default is the literal spelled today, not a new one. Twenty-six call sites default to `DEFAULT_ENDPOINT`, so a changed default is a silent repoint of the whole pipeline - ESCALATE trigger 1 exists for exactly this | Carmack |
 | 3 | `DEFAULT_HOST` is exported, not private. `backend/utilities/slot_probe.py:37` and `prompt_loop.py:54` already import `DEFAULT_ENDPOINT` from this module, so the module's address surface is public and this joins it | Fowler |
 | 4 | No validation. A bad host is knowable only at the first request, where the connection error already names it; a check would restate the failure one moment earlier and add a refusal path to test | Fowler |
 | 5 | The test asserts the unset case by literal rather than by recomputing the same f-string. A test that builds the expected value the way the code does passes when both are wrong | Fowler |
 | 6 | `docs/architecture/summarize/model-boundary.md` is the page. It already owns what the reply's fields mean; the address the reply comes from belongs beside them, not on a new page | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | A `config/` field under `knobs/` | It reaches `idhazh.fingerprint`, which folds every config value into the run record's inputs digest. Two runs of the same model on two hosts would stop comparing, and the address is not an input that changes an output | One knob, one schema regeneration, and every committed run record's digest changing meaning | Carmack |
 | 2 | A CLI flag only, with no environment variable | `backend/idhazh/cli.py:502` already has `--endpoint`, and it is not enough: the stages compose `DEFAULT_ENDPOINT` at import time in 11 modules, so a flag would have to be threaded through all of them | Eleven signatures widened to carry a value the environment can already supply in one line | Fowler |
 | 3 | Leave the host alone and let callers pass a full endpoint | It is the position today, and it is why this row exists. A caller can pass one; nothing sets one, so the only way to reach another server is to edit the module | Nothing to take. The cost lands on plan 40, whose probe would carry a source edit it cannot merge | Carmack |
 | 4 | Change `DEFAULT_HEALTH` and `DEFAULT_COMPLETION_ENDPOINT` to derive from `DEFAULT_ENDPOINT` rather than from the parts | Tempting, and wrong here: `DEFAULT_ENDPOINT` carries the chat path, so deriving the other two means stripping a path off a string. The four URL builders at `:983-1001` already do exactly that for a **caller-supplied** endpoint, where there is no alternative; at module scope the parts are in hand | A string-surgery step at import time where a format string does | Fowler |

## Section 3 - Row 2 - The instruments stop spelling an address of their own

- **Scope:** Replace the eight hand-spelled addresses in five operator instruments with `default_base_url()`, so the host and the port each have one home.
- **Files touched:**
  - `backend/utilities/measure_budgets.py` (`:607`)
  - `backend/utilities/measure_judge_call.py` (`:741`)
  - `backend/utilities/measure_probability_mode.py` (`:170`, `:172`)
  - `backend/utilities/measure_two_calls.py` (`:109`, `:926`)
  - `backend/utilities/runtime_sweep.py` (`:363`, `:379`)
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'utilities or sweep or measure' -q`, plus `python -c "import ast,sys; [ast.parse(open(p,encoding='utf-8').read()) for p in sys.argv[1:]]"` over the five files; CI - full suite.
- **Oracle:** a census finds **zero** occurrences of the literal `127.0.0.1` and zero of the literal `8080` under `backend/utilities/`, and each of the five instruments still resolves to its previous address with `LLAMA_HOST` unset - proved by printing each one's computed base before and after and diffing. **This fails on the base tree today**: the census finds eight and two. **What it cannot settle:** whether any of the five still runs. None is called by a test or a workflow; they are hand-run, and `runtime_sweep.py` is the only one a live plan dispatches. A syntax parse is what this row can prove, and it is named in the gates rather than implied.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | These five are kept, not deleted. Plan 43 row 2's rule binds: a utility a `docs/` page names as the instrument behind a recorded reading stays, whatever a caller census says. Four of the five are cited under **Instrument** on a benchmark page | Owner, 2026-09-22, via plan 43 row 2 decision 1 |
 | 2 | The helper takes an optional port because three of the five already accept one on the command line. A helper that ignored it would make those three spell the address again | Carmack |
 | 3 | The row is its own commit inside row 1's pull request. It touches no production path, and a reviewer should be able to see that in the diff shape | Fowler |
 | 4 | The oracle is a census plus a printed-value diff, not a live request. Nothing here starts a server, and a row that needed one would be a dispatch rather than a commit | Carmack |
 | 5 | `backend/utilities/slot_probe.py:192` and `prompt_loop.py:592` are **not** in this row. They already default to `DEFAULT_ENDPOINT` and inherit row 1 for free; naming them would be churn | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Leave the instruments alone | The host would have two homes, and the one a person runs by hand would be the stale one. Plan 40 dispatches `runtime_sweep.py`, so the instrument that most needs a remote address is the one that would not have it | Nothing to take today; the cost lands the first time somebody runs a sweep against a server that is not on the runner | Carmack |
 | 2 | Give each instrument its own `--host` flag | Five flags for one value, and a person running two instruments in one session has to pass it twice | Five argument declarations and a help string each, against one environment variable that covers all five | Fowler |
 | 3 | Fold this row into row 1 | One commit instead of two | A diff where a change to every production call site's default sits beside eight lines in hand-run tools, and a reviewer has to separate them by reading | Fowler |
 | 4 | Delete the two `8080` literals by making the helper refuse a missing port | `DEFAULT_PORT` already defaults to 8080 at `server.py:48`; a refusal would break every local run that does not export `LLAMA_PORT` | One refusal path, and a developer running a utility on a fresh clone getting an error where they had a working default | Carmack |

## See also

- [`20260921-39-delete-the-scaffolding-plan.md`](20260921-39-delete-the-scaffolding-plan.md) - row 21, the orphan this plan takes. Its section 1 records what landed and what did not.
- [`20260921-40-bonsai-probe-plan.md`](20260921-40-bonsai-probe-plan.md) - the first thing that would use a host it did not have to edit into place.
- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the page that owns this boundary and gains the address.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.
