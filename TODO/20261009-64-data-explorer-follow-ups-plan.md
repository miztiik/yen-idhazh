# Plan 64 - Data explorer follow-ups

**Last Updated**: 2026-10-09

**Level**: 3 overall; row 1 is measurement only and any trust-boundary change is Level 5.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Give each verified open finding from the delivered Data explorer a row that can settle it. |
| Hard scope - in | Remeasure extraction before changing its dependency ceiling; make the corpus-history tests independent of implicit bare-repository discovery; measure browser range reads from the committed archive; make choosing an example or saved question undoable. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | 1. Changing the trust boundary, contamination meaning, a persisted contract or the model requires owner approval before implementation.<br>2. A measurement cannot settle its question: report what is missing and the smallest measurement that would settle it; do not treat an unmeasured path as passing.<br>3. A proposed archive change needs another host, content-policy origin or publication mechanism: ask the owner.<br>4. A row overlaps an active row's named files: hold that row or agree a release point before editing. |
| Chosen strategy | Keep verified defects separate from measurements. Retain current production behavior until a measurement supports a change. This closure carries findings, not approval to weaken their controls. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Only row 2 is authorized by the owner on 2026-10-09. Rows 1, 3 and 4 remain AUTHOR-AND-STOP; measuring rows run alone. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Search-engine requirements for the console | The client-only explorer keeps the common fallback; exclusion from search results is not guaranteed. | A new owner request; the current [delivery rule](../docs/architecture/publishing/data-explorer-state.md#design-rationale) requires no crawler-specific document. |
| Wider console migrations and new chart types | Existing purpose-built panels keep their current readers; the explorer keeps its delivered charts. | Their owning plans and a separately approved outcome. |
| Changing production Git configuration or rewriting history | Test fixes cannot repair a separately misconfigured production runner. | A demonstrated production failure and owner approval for the required operation. |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Extraction is remeasured before its trafilatura ceiling changes | - | A | PENDING | - | - | - |
| 2 | Corpus-history tests name their bare repository explicitly | - | B | DONE | upgraded-lamp | - | owner |
| 3 | Archive range reads are measured before whole-file reads change | - | C | PENDING | - | - | - |
| 4 | Choosing an example is one undoable edit | - | B | PENDING | - | - | - |

## 2. Row #1 - Extraction is remeasured before its trafilatura ceiling changes

- **Scope:** Compare trafilatura 2.2 and 2.3 on the extraction tests' named committed HTML fixtures, then record whether an upgrade preserves the existing controls.
- **Files touched:**
  - `docs/reference/benchmarks/extraction-release-comparison.md`
  - `docs/architecture/sources/trust-boundary.md`
  - `TODO/20261009-64-data-explorer-follow-ups-plan.md`
- **Acceptance gates:** Use isolated environments, never the shared Python installation. Run `backend/tests/test_extract.py` and `backend/tests/test_extraction_health.py` against each dependency version with the same fixtures and settings. Tests do not fetch pages. Record fixture identity, extracted quantities, contamination and not-prose outcomes, failures, Python version and hardware. Run `doc_load.py` before and after the named Markdown edits. CI uses the unchanged production dependency.
- **Oracle:** Paired readings over the same named fixtures show which extraction controls change with the dependency alone. This cannot establish quality on pages the fixtures do not represent.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `pyproject.toml` still declares `trafilatura>=1.12,<2.3`; `trust-boundary.md` requires remeasurement before lifting it. | Current committed dependency and owning architecture page, verified at Plan 55 closure. |
| 2 | This row records a decision-quality comparison, not a dependency upgrade. If an upgrade needs altered controls, ask the owner and add its implementation row before this measurement closes. If parity supports an upgrade without altered controls, add a dependency-upgrade row naming its exact version, fixtures and gates. | CLAUDE.md sections 0d and 6. |
| 3 | Keep one current benchmark record; replace its readings on a rerun. | Documentation structure. |

| # | Rejected alternative | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Lift the ceiling and change failing expected values until green | A green test would not prove that the contamination control still works. | Paired fixture readings and owner approval for any changed boundary. | Existing extraction contract. |

## 3. Row #2 - Corpus-history tests name their bare repository explicitly

- **Scope:** Make the corpus-history test helper address its generated bare origin explicitly instead of relying on the machine to permit discovery from the working directory.
- **Files touched:**
  - `backend/tests/gardener/test_corpus_history.py`
  - `docs/reference/agent-notes/git-and-github.md`
  - `TODO/20261009-64-data-explorer-follow-ups-plan.md`
- **Acceptance gates:** First reproduce `test_a_wake_with_nothing_old_enough_records_the_run_and_pushes_without_force` with `safe.bareRepository=explicit` set for its test subprocesses. Use command-scoped settings, not shared Git configuration. Then run the named corpus-history module under both `explicit` and `all`. Use the shared selector for local lint and type checks. CI runs the backend suite.
- **Oracle:** The same generated repositories and history assertions pass under both discovery policies without weakening either assertion. This does not test unrelated Git settings or authorize a history rewrite.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Closure reproduced the failure in `History.on_origin()` through `dated_git()`: Git refused implicit access to the test's bare origin under `safe.bareRepository=explicit`. | Direct failing test on final main. |
| 2 | Pass `--git-dir` for the generated bare origin in `History.on_origin()`. Keep its existing seed identity, dates and real local repositories. Do not clear the operator's configuration to obtain a pass. | Git's explicit-repository interface; CLAUDE.md sections 8 and 13. |
| 3 | Add a portable agent-note warning beside Git test commands, not a workstation configuration recipe. | Documentation structure. |

| # | Rejected alternative | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Set the machine's bare-repository policy to `all` | Changes other users' Git behavior and leaves the test dependent on its environment. | A global configuration change with no test-isolation benefit. | CLAUDE.md section 8. |

## 4. Row #3 - Archive range reads are measured before whole-file reads change

- **Scope:** Determine whether the browser's existing DuckDB reader can read the committed archive by byte range and whether that reduces a narrow question's transfer.
- **Files touched:**
  - `docs/reference/benchmarks/archive-range-reads.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `TODO/20261009-64-data-explorer-follow-ups-plan.md`
- **Acceptance gates:** Observe one named public parquet file at the committed archive address from the site's browser origin, with the shipped content policy. Record Range response status, Content-Range, Accept-Ranges, cross-origin header visibility and the engine's actual requests. Compare identical questions against one generated multi-month year fixture on the existing local range server; record answer parity and whole-file versus ranged bytes. Live host observations are measurements, not networked tests. Use existing `ledger-ranges.spec.ts` for fixture correctness. Run `doc_load.py` for the named record and architecture page.
- **Oracle:** The same question returns the same rows while a request trace establishes what ranges actually transferred. A local fixture cannot prove the archive host supports those requests, and a small public file cannot price a production year file.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `ask-reader.ts` enables `RANGED_PERIODS` only for the site keeper; archive files are held whole. The owning page documents that behavior. | Direct code and docs at Plan 55 closure. |
| 2 | Keep whole-file archive reads during this measurement. A viable ranged path gets an implementation row with explicit failure behavior, answer-parity tests and named files before this row closes. If the host cannot support it, record the observed reason and the next condition that would justify remeasurement. | Existing archive contract; CLAUDE.md Guardrail #10. |
| 3 | Do not upload fixtures to a third party or change the configured archive address to obtain a measurement. | Existing operator-controlled destination and publication rules. |

| # | Rejected alternative | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Enable ranges because the site already supports them | The archive is a different host with different cross-origin behavior. | A host and engine request trace, then a tested implementation row. | Existing archive contract. |

## 5. Row #4 - Choosing an example is one undoable edit

- **Scope:** Make choosing an example or saved question replace the SQL and its selected ledgers and span as one edit that Undo can restore, without running the question.
- **Files touched:**
  - `frontend/src/lib/console/explorer/QueryEditor.svelte`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/tests/console-data-explorer.spec.ts`
  - `docs/how-to/query-a-ledger-from-the-console.md`
  - `docs/concepts/console-design/how-the-data-explorer-shares-the-window.md`
  - `TODO/20261009-64-data-explorer-follow-ups-plan.md`
- **Acceptance gates:** Read the editor's existing native textarea and input path before adding a replacement operation. Use the selector, then the explorer route spec and its selected checks. Browser smoke covers 390, 768 and 1440 px, both themes, the explorer and one other console page. Check keyboard Undo and Redo, empty text, a selection within typed SQL, two successive choices of examples or saved questions and no automatic Run. Keep native typing history; do not substitute a second editor. Run `doc_load.py` for changed Markdown.
- **Oracle:** Type a question, choose different ledgers and a custom span, choose an example, then press Ctrl+Z in the editor: the prior SQL, ledgers and exact dates return; Redo restores the example, and neither action runs it. Repeat with a saved question. This cannot certify every browser's native undo behavior, so record the browsers exercised.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `pick(example)` and `pickSaved(question)` directly assign SQL; neither offers a replacement operation that preserves textarea undo. The original question-strip rule promised one undoable edit for both choices. | Direct code and the delivered plan's section 2.16, rule 3. |
| 2 | Preserve the original one-edit intent. Expose replacement through the existing editor and keep any companion ledger/span history in runtime memory only. No saved-question contract or storage format changes. | Delivered Data explorer's example-selection intent; CLAUDE.md section 0d. |
| 3 | Document Undo only when its browser test passes. Existing docs correctly make no such promise. | CLAUDE.md sections 9 and 13. |

| # | Rejected alternative | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep direct assignment and describe the example as undoable | The typed question still has no verified recovery path. | A real native-editor replacement operation and the end-to-end oracle. | Original Data explorer intent. |

## See also

- [Execute a plan](../docs/how-to/execute-a-plan.md)
- [Query a ledger](../docs/how-to/query-a-ledger-from-the-console.md)
- [Extraction trust boundary](../docs/architecture/sources/trust-boundary.md)
- [Written-question reader](../docs/architecture/publishing/how-the-query-door-answers-a-written-question.md)
- [Git and GitHub checks](../docs/reference/agent-notes/git-and-github.md)
