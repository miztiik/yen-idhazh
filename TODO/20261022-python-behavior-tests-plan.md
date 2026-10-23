# Python tests that prove behavior

**Last Updated**: 2026-10-23
**Level**: 3 - change test coverage across reader and writer boundaries without changing production behavior.

## 0 - Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Intent | Python tests catch broken implementation behavior, not changes to the quality or formatting of current output data. |
| A2 | Status | Execution authorized by kumarsnaveen on 2026-10-23. The owner also authorized the structural follow-on work needed to complete the original suite-wide intent. |
| A3 | Hard scope - in | Review the Python suite against Table C; replace blanket fixture-format checks; remove proven duplicate data checks; preserve reader, writer, migration, identity, failure-handling and safety behavior. |
| A4 | Chosen strategy | Semantic reader/writer checks plus focused tests where exact bytes have a consumer. Fowler ruled this construction on 2026-10-22; the owner set the behavior-focused intent. |
| A5 | Contract impact | No persisted shape, version stamp, migration, serializer, digest algorithm, production validation rule, configuration knob or dependency changes. Session review reports are not a new application artifact. |
| A6 | Evidence baseline | Investigated against `0d2268015334e4028448b1f564a76ce51fd69968`. Recheck changed targets against current `origin/main` before dispatch. The earlier chat's keyword counts and deletion percentages are not verified findings or targets. |
| A7 | Inventory method | Before the first implementation edit, collect the suite once with `python -m pytest --collect-only -n 0 -q -o addopts="" backend/tests`. Keep the result and base commit in the session report. Record collected parameter cases separately from test functions; collection does not certify a passing test run. |
| A8 | Review record | For each candidate, record its full pytest identifier, asserted behavior, input source, primary Table C category, secondary categories, proposed action, remaining test, and concrete broken-code edit that remaining test detects. Unrelated behavior tests get a separate primary category. Primary counts must partition the collected list; secondary counts may overlap and must say so. Read assertions and called helpers; names and keywords only find candidates. |
| A9 | Deletion rule | A deleted check either has a named surviving behavior proof or asserts only incidental fixture/data content with no dependent behavior. Preserve input conditions needed to make a surviving test meaningful. An uncertain case stays until its responsibility is resolved. |
| A10 | Existing work | Do not adopt, restore or commit unrelated working-tree edits. In particular, re-read the main-branch versions of `test_feed_ingest_audit.py` and `test_source_classification_history.py` rather than treating local deletions as approved cleanup. |
| A11 | ESCALATE triggers | 1. A proposed change alters a persisted shape, emitted bytes, digest meaning, historical acceptance or the trust boundary: Level 5, pause for the owner. 2. A production validator or publication rule would be weakened or a new runtime check is needed: surface the scope change. 3. A needed consumer proof requires changing the published surface: revise the scope before implementation. 4. Evidence conflicts with an owner decision or an advisor conflict remains unresolved: pause under the execution contract. |
| A12 | Execution | Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

Table B - Work excluded from this plan

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Removing production quality checks or changing model evaluation | Publication and model-quality decisions retain their present cost and behavior. | An owner decision naming the changed publication or evaluation guarantee. |
| B2 | Reformatting, regenerating or deleting committed fixtures and live data | Some files may retain formatting that differs from the current writer. Their readers must still work. | A separate data-maintenance need, with named inputs and preserved historical evidence. |
| B3 | A permanent inventory tool, new test framework, new CI job, test skips or timing target | Classification remains a one-time review rather than a new maintenance surface; no speed gain is promised. | A repeated operator need or a measured cost that changes the implementation choice. |
| B4 | Frontend test deletion or a larger browser matrix | Existing frontend coverage and its running cost remain. | A separate owner request or a distinct uncovered failure found during the review. |

Table C - How to judge each category

| ID | Category | Keep as implementation behavior | Remove or improve |
| --- | --- | --- | --- |
| C1 | Golden-file or snapshot | A small independent expected result for a real protocol, renderer or writer guarantee. | Whole-fixture byte comparisons whose only failure is unrelated formatting. |
| C2 | Deterministic serialization | Values survive writing and reading; migrated output becomes stable on the next read; unchanged writes stay stable where required. | Requiring an old fixture's formatting to match today's writer. |
| C3 | Checksum or digest | Known identity values, changed-input sensitivity, unchanged-input stability and refusal of mismatched inputs. | Repeated checks that current stored files happen to carry the expected digest. |
| C4 | Encoding or formatting | Sorting, escaping, separators, record layout, physical line boundaries and final newline at the function that owns them. | Repeating those rules over every fixture or asserting current file whitespace. |
| C5 | Schema or contract | Actual validators, populated-value preservation, historical reads and Python/TypeScript bindings. | Duplicate copies of the same rule or tests that only repeat a library's declaration without testing a project guarantee. |
| C6 | Completeness | Defined behavior for absent files, missing fields, null values, partial results and empty input. | Asserting that current production data happens to contain no gaps. |
| C7 | Uniqueness | Deduplication, replacement identities and duplicate-input refusals on chosen examples. | Repeated uniqueness scans over stored datasets. |
| C8 | Validity | Accepted and rejected inputs, boundary values and useful failure reporting through the real validator. | Revalidating frozen output without testing the validating code. |
| C9 | Referential integrity | A real reader or writer accepts valid links and refuses or degrades broken ones as specified. | Repeated assertions that today's stored links all resolve. |
| C10 | Cross-field consistency | Derived values, totals, paired fields and impossible-state refusals on deliberately varied inputs. | Recomputing current dataset totals without exercising the implementation rule. |
| C11 | Freshness | UTC boundary arithmetic, ordering and expiry behavior using fixed instants. | Tests that become red only because a stored date grows older. |
| C12 | Coverage | A fixture condition essential to exercise a named consumer branch, or real selection coverage behavior. | Demanding arbitrary source, topic, band or length distributions from current data. |
| C13 | Reconciliation | Real producer/reader composition proves records are neither lost nor invented, including failure paths. | Repeating the same current counts at every downstream stage. |
| C14 | Distribution or drift | Detector arithmetic, comparability, sample handling and alert behavior on controlled observations. | Requiring a current dataset or model's quality score to stay within a unit-test threshold. |

## 1 - Status Reckoner

Table D - PR outcomes

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Semantic contracts and focused byte guarantees | - | A | DONE | - | - | - |
| D2 | 2 | Vector tests independent of the current asset | - | A | DONE | - | - | - |
| D3 | 3 | Finish the behavior review and remove proven fixture-only checks | 1, 2 | B | PENDING | - | - | - |
| D5 | 5 | Expectations derived from the test's own input | 2 | D | DONE | input-based-vector-expectations | #1654 | - |

## 2 - Row #1 - Semantic contracts and focused byte guarantees

- **Scope:** Ship a PR that tests reader/writer values and migration behavior without treating every fixture's bytes as a separate formatting contract.
- **Files touched:**
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/test_json_serialization.py` - new, focused formatter tests.
  - `backend/tests/contracts/test_desks.py`
  - `backend/tests/contracts/test_curated_registries.py`
  - `backend/tests/contracts/test_record_layouts.py`
  - `backend/tests/test_visual_validator.py`
  - `backend/tests/contracts/test_committed_days.py` - docstring only. Added 2026-10-23, before dispatch: it named a `test_contracts.py` that does not exist and a byte-identical round trip that this row retires (reference search: no other hit outside the listed files).
  - `docs/architecture/contracts/schemas.md`
  - `TODO/20260828-band-calibration-handover.md`
  - `TODO/20260910-23-article-classification-plan.md`
  - `TODO/20260910-25-placement-plan.md`
- **Acceptance gates:**
  - Local: use `npm run test:changed -- --list`, then the selected checks from [the gate guide](../docs/how-to/run-the-gates.md). Record selected inputs and results; do not repeat an unchanged focused check.
  - Local focused coverage: the listed test modules, including the new module, named fixture coverage, existing migration cases and published layout wiring.
  - Local negative proof: in a disposable checkout, remove a consumed field from a writer or its historical migration and confirm the relevant surviving test fails for that loss. Separately change a formatter's newline or escaping and confirm its focused byte test fails. Do not edit the working implementation to perform this check.
  - CI: the normal full backend suite and applicable contract bindings on the merge candidate; no additional job or live pipeline run.
- **Oracle:** A writer that loses a consumed value or breaks a historical migration fails the semantic checks, while a fixture-only whitespace edit does not; a formatter change still fails its independent byte expectation. This does not establish article or summary quality.

Table E - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| E1 | Rename `test_fixture_round_trips_byte_identically` to `test_fixture_round_trips_without_losing_values`. Validate the named fixture, compare the emitted keys and values to the contract's expected wire representation, and compare the reloaded model to the original validated model. Parsing successfully is not sufficient; a writer dropping an optional populated field must fail. Reuse populated-value cases rather than adding every possible field combination. | Fowler; direct inspection of the current test and the contract writers. |
| E2 | Preserve main's migration-aware distinction: when loading advances a stamp, require the original stamp to precede the current schema stamp, assert expected migrated values in the named migration cases, and require the next serialization to equal the first. Do not compare migrated output against historical fixture bytes or rewrite that fixture. | Fowler; current main's migration predicate and `CLAUDE.md` section 11. |
| E3 | Move the canonical serializer test out of the desk tests and the generic record formatter tests out of the curated-registry tests into the new formatter module. Cover `canonical_json`, `compact_json`, and `records_json`, including selected record lists, with small independent expected strings. Do not compute the expected bytes with the function being checked. | Fowler; existing formatter tests and `backend/idhazh/contracts/base.py`. |
| E4 | Keep contract-to-writer selection checks in `test_record_layouts.py`: choosing the wrong serializer is a separate defect from a broken formatter. Remove only repeated assertions already owned by the formatter tests. Curated config validation remains; its current file whitespace stops being a pytest guarantee. | Fowler; direct inspection of both test modules. |
| E5 | Replace `test_a_named_fixture_round_trips_byte_identically` with semantic preservation through `ElementTable` and `VisualPlan`, retaining the existing validator-disposition cases. A deliberately wrong quantity remains available to test the validator; it is not repaired as fixture hygiene. | Fowler's deletion conditions; existing named visual fixtures and validator tests. |
| E6 | Revise the serialization and fixture-maintenance sections of the schema page without changing producer-format requirements. Repair the old test-name references in the listed plans; historical descriptions remain historical rather than instructions to restore blanket byte parity. The page stays whole because both sections answer how contracts are written and checked. | Existing schema ownership and the verified reference search. |
| E7 | Current main's `test_named_canonical_observations_round_trip` already compares feed audit model values rather than fixture formatting. Do not reimplement that change or sweep the uncommitted local deletions into this PR. Historical source-classification checks remain unless a named surviving test proves the same responsibility. | Direct main-branch diff and the existing-work boundary in Table A. |

Table F - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | Delete all fixture round trips | A lossy writer or removed migration could pass validation-only tests. | Replace each lost reader/writer and historical compatibility proof first; otherwise obtain owner approval for the lost guarantee. | Fowler. |
| F2 | Normalize every fixture whenever a serializer changes | This keeps test coupling to data presentation instead of isolating the formatter's behavior. | Continued fixture churn and risk of erasing historical input evidence. | Fowler. |
| F3 | Change serializer output to reduce the tests | That changes the system rather than its redundant coverage, including bytes used by digests. | Level-5 design consultation and any required compatibility work. | Fowler; the contract-impact boundary. |

## 3 - Row #2 - Vector tests independent of the current asset

- **Scope:** Ship a PR that proves the binary vector writer and reader using generated inputs rather than the current committed vector file's size and contents.
- **Files touched:**
  - `backend/tests/test_assemble_embeddings.py`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: inspect and run the shared selector as in Row #1; record the focused `test_assemble_embeddings.py` result, including any model-dependent exclusions separately.
  - Local focused coverage: run the generated pack/read, missing-file, stale-vocabulary, wrong-encoder and malformed-header/body cases without downloaded model weights.
  - Local negative proof: a disposable reader that accepts the wrong vocabulary or encoder must fail the refusal cases. A damaged header/body must reach its intended refusal rather than pass through a different earlier error.
  - CI: the normal backend suite and existing assembly integration checks.
- **Oracle:** A bounded generated file is decoded to its known vectors and identity, while deliberately missing or invalid files take the specified absence or refusal path, without reading the live vector asset. This cannot establish whether the currently committed asset was rebuilt from the intended model.

Table G - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| G1 | Replace the live-file assertions in `TestTheCommittedLabelVectors` with generated codec cases and rename the class for that behavior. Remove the fixed body-size expectation and `committed_vectors()` helper after replacing all its callers, including the later day-metric integration cases. Keep unrelated real-encoder tests and their existing preparation requirements. | Direct assertion and caller inspection; Fowler's distinction between asset hygiene and codec behavior. |
| G2 | Use a bounded taxonomy fixture or a small constructed taxonomy with active and retired entries. Derive protocol dimensions and expected payload length from chosen input vectors and the existing format constants, not today's label count. Prove that active label text changes move the digest and retired-only edits do not. | Existing digest implementation and behavior tests. |
| G3 | Exercise the real packer and reader. Retain known-vector expectations that do not merely repeat the packer's own computation. Generate structurally valid stale inputs or keep the named recorded stale fixture with the precondition needed to prove the intended error. Fold fixture-validity-only assertions into that behavioral case rather than retaining a separate data audit. | Fowler's non-vacuous deletion rule. |
| G4 | The real reader already returns no measurement when the asset is absent and refuses mismatched vocabulary, encoder, dimensions or body length. Preserve these production checks; do not add a second asset audit command or rebuild the real asset during pytest. | Direct inspection of `read_taxonomy_vectors` in `backend/idhazh/assemble.py`. |
| G5 | Update only the gate guide's existing bounded-input testing guidance to explain generated derived-asset cases. Link to `CLAUDE.md` section 13 rather than copying policy or adding a second test-rule page. | Existing gate-guide ownership. |

Table H - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Keep a fixed size or label-count assertion against the current binary | A valid vocabulary or asset update changes the test without breaking the reader. | Continued coupling to current data and manual expectation changes. | Owner intent; direct test inspection. |
| H2 | Replace the reader or encoder with a mock | The binary reader and its refusal paths are the capability being checked. | An explicit owner exception and reduced format/integration evidence. | Existing fixture policy. |
| H3 | Delete stale-file checks as data-quality tests | Accepting mismatched vocabulary produces a plausible measurement with the wrong meaning. | Loss of the existing runtime refusal proof and owner approval for that loss. | Fowler; actual reader behavior. |

## 4 - Row #3 - Finish the behavior review and remove proven fixture-only checks

- **Scope:** Ship a PR that removes redundant canary-data assertions, closes the suite review across Table C, and leaves every retained guarantee with an identified behavior test.
- **Files touched:**
  - `backend/tests/test_canary_day.py`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: finish the review record defined in Table A and report verified function and collected-case counts with the base commit, scope and overlaps. Compare the initial and final collected identifiers; each disappearance must match a recorded removal, merge or rename.
  - Local: use the shared selector for changed Python tests. Where existing frontend consumer coverage supplies the deletion proof, run `npm run test:changed -- --spec console-compression-rows.spec.ts`; do not create a second browser journey.
  - Local focused coverage: retain real canary build/file/read integration, record identity, band/cut propagation, repeated-write behavior and explicit empty or missing-data behavior where those are distinct failures.
  - Local negative proof: a disposable writer that drops a canary record or substitutes a wrong band/cut value must fail the remaining integration test. A setup-only assertion is not its replacement.
  - CI: the full backend suite and already-selected frontend coverage on the merge candidate. Existing skips or an unavailable model do not certify the focused model-free proofs.
- **Oracle:** No removed implementation responsibility is left without a named surviving test that detects its concrete broken-code edit; the collected-identifier comparison accounts for every removal. This does not measure live source reliability, generated-summary quality or suite speed.

Table I - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| I1 | Review repeated canary checks such as broad length distribution, all configured target zones, fixed item totals and exact note wording. Remove a condition only when it is incidental data content or its dependent behavior has a named proof. Keep the smallest conditions needed for the existing representative consumer journey to exercise its intended state. | Fowler's non-vacuous deletion rule and `CLAUDE.md` section 13.5. |
| I2 | Consolidate repeated builder-to-ledger comparisons into the real file/read integration where they prove the same mapping. Vary meaningful input values so a wrong default or dropped field fails; do not copy all fixture-detail assertions into a larger test or a new helper. | Direct `score_rows` and canary test inspection. |
| I3 | `frontend/tests/console-compression-rows.spec.ts` already drives the real summary-length and cut readers with missing, unchanged and cut lengths. That is behavior evidence, not a reason to add another Python fixture-quality assertion or more browser cases. | Direct consumer-test inspection. |
| I4 | Preserve `test_drift.py` detector cases, `test_retrieval_eval.py` ranking arithmetic, `test_publication_inventory.py` consistency/refusal cases, and generated publication-check cases in `test_published_assets.py` and `contracts/test_committed_days.py`. Their quality-related names do not make them data audits. Keep backfill idempotence and untouched-file byte comparisons where they prove no unintended write. | Direct representative test inspection; Table C. |
| I5 | Close every Table C category in the review record, including categories with no justified deletion. Report actual decisions, not a quota. If the review identifies an additional edit, first add its exact paths, reference-search results, acceptance proof and real dependencies to this plan before dispatch; changed guarantees follow Table A's escalation rules. | Owner intent; the plan-authoring and execution contracts. |
| I6 | Finish the testing-guidance update begun in Row #2, stating where data checks belong and how behavior-based deletion evidence is reviewed. Link to the schema page for byte/semantic ownership. Keep decisions out of permanent count tables; Git and the session report hold the review's snapshot. | Existing documentation ownership. |

Table J - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Delete a fixed percentage from each category | The previous estimates do not identify a removable test or the behavior it protects. | A source-backed review of each proposed deletion; the review, not the percentage, decides. | Evidence baseline; owner intent. |
| J2 | Delete everything mentioning quality, missing data, totals or drift | Those terms also describe validation, selection and failure-handling implementations. | Specific lost reader, safety and correctness guarantees, each requiring owner approval. | Fowler; directly inspected counterexamples. |
| J3 | Move every data assertion into a new producer check or scheduled suite | Many checks are already enforced, or concern only a test fixture; relocating all of them preserves the redundancy. | Extra runtime reads and another maintenance surface; a genuine uncovered production invariant must be priced separately. | Existing producer ownership and the contract-impact boundary. |
| J4 | Treat fewer tests as proof of faster CI | Collected count does not measure runtime and shared-runner noise can dominate. | Paired runs on identified hardware if a later implementation decision actually needs a speed measurement. | Existing measurement policy. |

## 6 - Row #5 - Expectations derived from the test's own input

- **Scope:** Replace fixture-derived identities, counts and dates with expectations
  from the input handed to the implementation. Keep independent vector values,
  stale-input refusals and completed/failed-step outcomes.
- **Files touched:** `backend/tests/test_backfill_vectors.py`,
  `backend/tests/test_corpus_harvest.py`, `backend/tests/test_canary_packing.py`.
- **Reference checks:** The review names six backfill cases, the census recount
  case and the council-record packing case. Each identifier was rechecked
  against this branch before editing.
- **Changes and acceptance proof:**
  - `TestWhichItemsEarnAVector::test_readable_items_all_earn_one`: expected ids
    come from the supplied day's items; dropping a readable item must fail.
  - `TestWhichItemsEarnAVector::test_an_item_the_encoder_cannot_read_earns_nothing`:
    expected ids exclude the item the test made unreadable; including it must fail.
  - `TestTheBackfill::test_an_item_that_earns_nothing_gets_nothing` and
    `test_a_surplus_vector_is_dropped`: the written ids exclude the unreadable
    item and retain the others; keeping its vector must fail both checks.
  - `TestTheBackfill::test_a_wrong_day_is_re_encoded_whole`: expected ids/count
    come from the supplied day, while independently chosen stale vector values
    must be replaced; topping up the stale block must fail.
  - `TestTheBackfill::test_a_repaired_day_takes_its_month_index_with_it`:
    the index month comes from the supplied day, and its known-date path stays
    an independent `2026-08.json` naming check; leaving it stale must fail.
  - `test_the_census_is_recounted_from_the_window_never_incremented`:
    expected model, vertical and date values come from the scored input row,
    not rows read back from the implementation. A deliberately inflated prior
    model count proves recounting; incrementing instead must fail.
  - `test_published_council_records_keep_completed_and_failed_steps`:
    read-back records equal the filed records, including both outcomes; dropping
    the failed step or changing an outcome must fail. Keep the explicit
    `("failed", "raised")` and `("completed", None)` expectations and the
    independently supplied start time; whole-record equality alone only proves
    packing preserves what the fixture writer supplied.
- **Gates:** Shared changed-test selector and the directly selected checks it
  names. Run fault checks in disposable copies, not in the working implementation.
- **KEEP:** The stale vector remains independently chosen as `vector(0.25)`;
  the repaired vector must differ from it. The known-date month-index path and
  the canary outcome, fault and start-time expectations remain independent
  checks. Removing these expectations adds no input-derived coverage.
- **Negative proofs (2026-10-23):** In a disposable archive, each listed
  production mutation failed the named test at the shown assertion. The archive
  imported its own `backend/idhazh`; the real local encoder and tokenizer were
  included for backfill proofs.
  1. `test_readable_items_all_earn_one` - omit the first readable id;
     `assert earns_a_vector(payload, embedder()) == {item.item_id for item in payload.items}`.
  2. `test_an_item_the_encoder_cannot_read_earns_nothing` - include every item;
     `assert earns_a_vector(payload, embedder()) == expected`.
  3. `test_an_item_that_earns_nothing_gets_nothing` - treat every item as earned;
     `assert set(repaired.embeddings.vectors) == expected`.
  4. `test_a_surplus_vector_is_dropped` - accept a superset of earned ids;
     `assert set(repaired.embeddings.vectors) == expected`.
  5. `test_a_wrong_day_is_re_encoded_whole` - merge stale vectors into the new
     block; `assert repaired.embeddings.vectors[stale_id] != stale`.
  6. `test_a_repaired_day_takes_its_month_index_with_it` - skip rebuilding the
     month index; `assert index_path.is_file()`.
  7. `test_the_census_is_recounted_from_the_window_never_incremented` - start
     counts from previous metadata; `assert recounted.models == expected_models`.
  8. `test_published_council_records_keep_completed_and_failed_steps` - drop
     failed rows; `assert packed == filed`.
- **Selector (2026-10-23):** `npm run test:changed` from `frontend/` selected
  exactly the three files in this row and reused completed run `d51d38cfefb4`
  with exit 0: ruff passed, mypy reported no issues in 831 source files, and
  70 pytest cases passed. `git diff --check` passed.
- **Dependencies:** Row 2's generated vector tests. Row 4 and this row touch no
  common application/test file; serialize edits to this shared plan.

## See also

- [Plan execution](../docs/how-to/execute-a-plan.md).
- [Engineering contract](../CLAUDE.md#13-test-coverage-policy).
- [Contracts and serialization](../docs/architecture/contracts/schemas.md).
- [Local and CI checks](../docs/how-to/run-the-gates.md).
- [Publication validation](../docs/architecture/publishing/what-stops-a-broken-day-being-published.md).
