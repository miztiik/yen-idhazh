# Python tests that prove behavior

**Last Updated**: 2026-10-22
**Level**: 3 - change test coverage across reader and writer boundaries without changing production behavior.

## 0 - Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Intent | Python tests catch broken implementation behavior, not changes to the quality or formatting of current output data. |
| A2 | Status | Execution authorized by kumarsnaveen on 2026-10-23. The owner also authorized the structural follow-on work needed to complete the original suite-wide intent. |
| A3 | Hard scope - in | Review the Python suite against Table C; replace blanket fixture-format checks; remove proven duplicate data checks; preserve reader, writer, migration, identity, failure-handling and safety behavior. |
| A4 | Chosen strategy | Semantic reader/writer checks plus focused tests where exact bytes have a consumer. Fowler ruled this construction on 2026-10-22; the owner set the behavior-focused intent. |
| A5 | Contract impact | No persisted shape, version stamp, migration, serializer, digest algorithm, production validation rule or dependency changes. Exception: Row 9 removes the unused `collect.watchlist_max_entities` configuration knob and its test-only entry cap, authorized by kumarsnaveen on 2026-10-23. Named config fixtures lose only that setting; historical retention and source-weight evidence stays intact. Session review reports are not a new application artifact. |
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
| D3 | 3 | Finish the behavior review and remove proven fixture-only checks | 1, 2 | B | IN-FLIGHT | - | - | - |
| D4 | 4 | Safe removals with named survivors | 1, 2 | C | DONE | - | [#1652](https://github.com/miztiik/yen-idhazh/pull/1652), merged at `75a4e12af6ad40f79691afba41b20ce71414c2e6` | - |
| D5 | 5 | Expectations derived from the test's own input | 2 | D | DONE | input-based-vector-expectations | [#1654](https://github.com/miztiik/yen-idhazh/pull/1654), merged at `3073686d6d28f824f53e8b45a88caddf2691932a` | - |
| D6 | 6 | Pipeline records follow the input that produced them | 1 | E | DONE | input-based-pipeline-records | [#1655](https://github.com/miztiik/yen-idhazh/pull/1655), merged at `6bb8dfea19613c116142131550c97fead234747d` | - |
| D7 | 7 | Config reader values and accurate migration test names | 1 | F | DONE | config-reader-behavior-proofs | [#1653](https://github.com/miztiik/yen-idhazh/pull/1653) | - |
| D8 | 8 | Workflow checks retain independent failure evidence | 1 | G | DONE | workflow-behavior-proofs | [#1656](https://github.com/miztiik/yen-idhazh/pull/1656), merged at `43bdd37d671275af2f904590f7ca69498cc74a91` | - |
| D9 | 9 | Remove the unused watchlist entry limit | 1 | H | DONE | remove-unused-watchlist-limit | [#1657](https://github.com/miztiik/yen-idhazh/pull/1657), merged at `f479997fec70f4f57b13a6d3a649b5d92a4fd5f7` | - |
| D10 | 10 | Independent historical reader proofs | 1 | I | DONE | independent-historical-reader-proofs | [#1659](https://github.com/miztiik/yen-idhazh/pull/1659), merged at `f0449de3db08c710e5b2292a03910da157bcb498` | - |
| D11 | 11 | Contract tests prove authored and constructed behavior | 1 | J | IN-FLIGHT | config-refusal-selection-proofs | - | - |
| D12 | 12 | Explicit controls and measurement behavior | 1 | K | IN-FLIGHT | explicit-control-behavior-proofs | [#1661](https://github.com/miztiik/yen-idhazh/pull/1661) | - |

The canary implementation for Row 3 is delivered separately from its suite-wide
review obligation. Rows 5 and 6 carry additional changes found by that review.
The review stays open until the previously screened functions have been read,
each proposed action has a disposition, and the final collection is reconciled.

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

## 5 - Row #4 - Safe removals (follow-on of the suite review)

- **Scope:** Remove only the named duplicate checks below. Production code,
  committed data, helpers and owner-held tests stay unchanged.
- **Approved correction:** The coordinator selected A1 on 2026-10-23 on
  kumarsnaveen's behalf under the owner's existing structural-fix and
  scope-expansion instruction; this was not a new direct owner answer.
  Strengthen the existing healthy-feed test to require a planned item from
  the lab feed, and use the two named config-file survivors for the file proof.
  The first proposed feed proof passed before that change. The constructed
  retired-knob refusal never reads the committed file and is not its proof.
- **Config-bound correction:** The coordinator cancelled brief item 5(b) after
  the body-level group-2 review. Keep the per-file `declared_for` equality:
  the active-model refusal does not check inactive files. This retains a
  guarantee rather than silently treating the constructed swap as its proof.
- **Base:** `9893c08d7174fb489a34209d91c6d7f9598df5d0`, current
  `origin/main` when work started.
- **Dependencies:** Rows 1 and 2 supply the completed prerequisites. Row 3's
  unfinished suite-wide review is not a prerequisite and remains open.
- **Reference search:** The retention module has other tests and stays. The
  model-loading test keeps loading every named model file and checking its
  declared pairing. The registry's committed-file
  validation moves into `test_the_committed_registry_loads_and_names_each_ledger`.
- **Acceptance:** Run the shared selector, all seven changed test modules with
  `pytest -n 0`, root ruff and mypy. Compare collected identifiers before and
  after. Apply each fault separately in a disposable `git archive` copy of this
  branch, never in the working implementation.

Table K - Removals and surviving proofs

| ID | Removed check | Surviving behavior test | Negative proof |
| --- | --- | --- | --- |
| K1 | `test_host_readings.py::test_the_two_proc_stat_captures_an_oracle_reads_are_committed` | `test_the_processor_busy_share_is_read_from_a_real_proc_stat_pair`; its zero-steal assertion stays | Delete the starting capture in the copy; the survivor must fail reading it. |
| K2 | `test_plan.py::test_every_feed_fixture_this_module_serves_parses` | `test_a_healthy_feed_is_read_and_its_entries_are_planned`, strengthened under the approved correction to require a planned item from the lab feed | Replace `tests/fixtures/feeds/lab-blog.xml` with non-XML in the copy; the corrected survivor must fail. |
| K3 | `test_appearance_config.py::test_the_committed_file_validates` | `contracts/test_app_config.py::test_config_file_validates[appearance.json]` | Rename one appearance contract field in the copy; the survivor must fail validation. |
| K4 | The explicit set and count assertions in `contracts/test_ledger_registry.py::test_the_committed_registry_names_every_ledger_exactly_once` | `test_a_ledger_with_no_entry_stops_the_build_naming_it`, `test_a_ledger_named_twice_stops_the_build_naming_it`, `test_an_entry_for_no_ledger_is_refused_by_the_name_it_carries`, `test_a_ledger_listed_in_two_families_stops_the_build_naming_both`; committed-file loading stays in its own named test | Remove the split-family refusal branch in the copy; the split-family survivor must fail. |
| K5 | `contracts/test_model_registry.py::test_every_committed_model_entry_declares_the_weights_its_settings_are_for` | `test_a_model_swap_can_no_longer_inherit_settings_nothing_declared_for_it` and the unchanged every-model-file pairing check | Remove the `declared_for` refusal in the copy; the swap survivor must fail. The per-file assertion retains committed pairing coverage. |
| K6 | KEEP the `declared_for` assertion in `contracts/test_model_registry.py::test_every_model_file_loads_and_not_only_the_one_the_pointer_names`; brief item 5(b) is cancelled | This is the only check of an inactive model file's pairing; the active swap does not cover it | Change only an inactive model's `declared_for` in the copy; the retained per-file check must fail. |
| K7 | `contracts/test_retention_knobs.py::test_the_committed_config_no_longer_emits_a_removed_name` | `contracts/test_retired_knobs.py::test_a_config_still_carrying_a_removed_knob_is_refused_by_name`, `contracts/test_app_config.py::test_config_file_validates[idhazh.json]`, `test_the_config_file_names_every_knob_it_owns[idhazh.json]` | Add a removed knob to the copied config and run the named survivors. |
| K8 | `contracts/test_app_config.py::test_the_committed_reject_ceiling_leaves_the_brief_gate_a_live_band` and only the committed-file assertion in `test_no_judges_own_measurement_reaches_the_shared_config_contract` | `test_a_reject_ceiling_under_the_brief_gate_is_refused` and `test_config_file_validates[idhazh.json]` | Remove the reject-ceiling refusal in the copy; the boundary survivor must fail. Config loading remains independently covered. |

### Feed inputs and the conditions their consumers need

The deleted parameter cases checked only an XML declaration, not whether a
feed parsed. That prefix is incidental formatting: valid XML need not carry
it. The real consumers read `tests/fixtures/feeds/` through `BODIES`,
`fetcher_over` and the plan stage. They retain their branch-selecting input:

- `lab-blog.xml`, `trade-press.xml`, `community.atom`: the healthy-feed test
  plans the shared headline, and now requires the lab feed as its source.
- `empty.xml`: `test_a_feed_that_answers_two_hundred_with_nothing_in_it_counts_as_read`
  checks a successful reply with no planned item from that feed.
- `undated.xml`: `test_an_undated_story_is_never_too_old` and
  `test_an_undated_entry_gets_the_age_we_first_saw_it` keep the undated item
  and check its assigned time.
- `future-dated.xml`: `test_a_date_too_far_in_the_future_is_not_a_date` checks
  both replaced and accepted future times.
- `cross-vertical-duplicate.xml`:
  `test_cross_vertical_duplicate_drops_once_before_the_safety_ceiling` checks
  the surviving item and the dropped duplicate.
- `prolific-outlet.xml`: `test_an_outlet_running_two_different_stories_keeps_both`
  requires more than one planned item from the outlet.
- `outlet-repeat-first.xml`, `outlet-repeat-second.xml`:
  `test_one_outlet_never_runs_the_identical_piece_twice` and
  `test_two_outlets_on_one_story_are_both_planned` distinguish shared and
  different mastheads.
- `front-page.xml`: the front-page consumer checks that a recorded vote is
  carried without changing rank; the separate address-exclusion check stays.

No other consumer or fixture condition is removed. The XML-prefix assertion
is not retained as a new fixture audit.

### Negative proof outcomes

Each fault ran separately in a disposable archive copy. All nine selected
survivor cases passed before faults. Each copied production or data edit was
restored from the archive after its check.

1. Missing starting capture: the processor-share survivor failed with
   `FileNotFoundError`; its zero-steal assertion stays unchanged.
2. Non-XML lab feed: the original healthy-feed survivor passed, disproving the
   brief's first claim. The approved source assertion passed with the real
   input, then failed with the non-XML input: the planned item's source was
   `trade-press`, not `lab-blog`.
3. Renamed `AppearanceConfig.motion`: `test_config_file_validates[appearance.json]`
   failed with the named extra-field validation error.
4. Removed split-family refusal: the split-family survivor failed because
   the remaining duplicate refusal did not name both families.
5. Removed model pairing refusal: the model-swap survivor failed because
   `ValueError` was not raised. It proves the active refusal only. The separate
   per-file equality stays to cover inactive model files.
6. Added `collect.quarantine_after_failures`: both
   `test_config_file_validates[idhazh.json]` and
   `test_the_config_file_names_every_knob_it_owns[idhazh.json]` failed naming
   the removed knob. The constructed retired-knob refusal passed, as expected
   after correcting the proof: it independently checks validator behavior,
   not the committed file.
7. Removed reject-ceiling refusal: the boundary survivor failed because
   `ValidationError` was not raised. The removed config-loading assertion
   remains covered by `test_config_file_validates[idhazh.json]`.
8. Inactive-model pairing: the retained every-model-file test passed unchanged
   input, then failed when only `declared_for` in
   `config/models/gemma-4-e4b-qat-no-draft.json` changed to a different digest.
   The assertion named that inactive file, confirming why brief item 5(b)
   must not remove it.

This row does not close the full suite review. Row 3 delivered only its canary
changes; review groups 2, 6, 7 and 8 still need assertion-level classification.
All held safety, history, persisted-format and config-bound checks stay.

### Collection reconciliation

An untouched archive of the recorded base collected 7,237 parameter cases
across 4,882 test functions. This branch collected 7,221 cases across 4,876
functions: 16 fewer cases and six fewer functions. The identifier comparison
contains only five nonparameterized deletions, the eleven cases of the deleted feed
prefix function, and the committed-registry test's rename. The partial assertion removal and the strengthened feed consumer preserve
their identifiers. The inactive-model pairing assertion stays unchanged.
The first checkout collection overlapped the edits and was discarded; these
counts use the untouched archive and the completed branch instead.

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

## 7 - Row #6 - Pipeline records follow the input that produced them

- **Scope:** Remove literal expectations copied from a fixture where the actual
  guarantee is preservation of the input, selection under test-owned settings,
  or reconciliation between a producer and its reader.
- **Files touched:** `backend/tests/pipeline/test_census_prefers_the_record.py`,
  `test_day_fragments.py`, `test_degrade.py`, `test_desk_field.py`,
  `test_eval_row.py`, `test_publish_window.py`, `test_recorded_inputs.py`,
  `test_two_calls.py`, `test_work_health_payload.py`, `test_work_order.py`,
  `test_work_records.py` in the same directory.
- **Reference checks:** Use the full identifiers in the group-5 review report.
  Its 30 rewrite proposals contain 26 pipeline cases and four council cases.
  Only the pipeline cases belong to this row. All 35 pipeline candidates and
  their helpers were read: 24 were rewritten and 11 retained. All 116 test
  identifiers remain; none were added, removed, renamed or skipped.
- **Changes and acceptance proof:**
  - Reconcile persisted item ids/counts with the exact plan supplied to the work
    stage. A dropped or extra item, changed recorded cell, or changed writer order
    must still fail.
  - Set ranking signals, desk counts, tracing switches and truncation flags in
    the test when those values select its branch. Check propagation against
    those independent inputs, not values produced by the function under test.
  - Derive capture counters and recorded-reply text from their raw input fields.
    Keep explicit arithmetic and refusal reasons.
  - Give fragment-order and failed-then-published cases test-owned run ids and
    outcomes. Preserve tie-breaking, day reconciliation and historical reads.
  - Keep the fresh-clone safety bound, recorded run/config digests, manifest wire
    keys and the historical run-record proof. They are guarantees, not incidental
    fixture values.
- **Gates:** Shared changed-test selector; disposable broken-code checks for each
  distinct preserved behavior. Record full changed and surviving identifiers.
- **KEEP:** The paused-family literal checks the exact ledger/family protocol
  identity and skip record. Replacing it with whatever config currently names
  could hide incorrect lifecycle wiring. The fresh-clone check retains its
  positive safety ceiling and usable feeds/taxonomy; loading alone is weaker.
  Recorded config digest inventories, historical item/run links, raw manifest
  keys, publication inventory setup, unchanged writes and independent arithmetic
  remain unchanged. The chosen two-item work-record input stays explicit; unlike
  the removed five-item census constants, it is not copied from fixture size.
- **Negative proofs (2026-10-23):** A disposable copy of main `3e4935c1f` plus
  these eleven edited test modules imported its own production package. Each
  of 25 named production faults caused its intended test failures: 28 failed
  executions cover all 24 rewritten identifiers, with no collection errors.
  Faults cover lost/invented rows, changed cells and writer order, fragment
  clock/id ordering and recovered failures, lost headings and metadata,
  truncation/ranking propagation, raw shard totals, desk counts, run identity,
  null feed floors, later-run counts, trace parents, cut-reply recovery, band
  and original-position ordering, and capture-directory placement.
  Full identifiers, exact edits and output links are recorded in the phase's
  external `row6-proof-report.json` and `row6-negative-results.json`.
  All copied test hashes matched, all mutated production files were restored,
  and the disposable copy was removed after verification.
- **Selector (2026-10-23):** From `frontend/`,
  `npm run test:changed -- --python <absolute-python-executable>` selected
  exactly these eleven modules. Whitespace and ruff passed; mypy reported no issues
  in 834 source files; all 116 pytest tests passed with zero skips.
  Record: `backend/var/checks/7afab1b065bc5c0bee7ce2e70fbd1efee601a2592015dee79fbf4f544ad3eb8c.json`.
  No production, config, data, frontend or dependency change was made.
- **Plan integration:** The coordinator released the serialized edit slot on
  2026-10-23. Its correction selects Row 7's frozen full plan as the base,
  imports only D5/Row5 from Row 5 commit `d13c8f3`, and then adds D6/Row6.
  Other delivered rows and the open D3 review are preserved.
- **Dependencies:** Row 1's byte/value ownership. No production, persisted format,
  configuration or frontend change. Serialize edits to this shared plan.

## 8 - Row #7 - Config reader values and accurate migration test names

- **Scope:** Check config readers against the named file's own input values,
  retain independent digest computation, and stop migration-test names from
  claiming to scan current publication data.
- **Files touched:** `backend/tests/contracts/test_council_config.py`,
  `test_content_similarity_judge_config.py`, `test_feed_ingest_config.py`,
  `test_committed_days.py` in that directory, and `docs/how-to/run-the-gates.md`.
- **Reference checks:** The named functions below exist in the coordinator's
  current tree. `test_curated_registries.py` already has Row 1's semantic check;
  do not reimplement the obsolete group-1 rewrite. The similarity metrics path
  test preserves an independent historical address and stays unchanged.
- **Changes and acceptance proof:**
  - `test_the_committed_file_names_every_knob_and_both_loaders_read_it`:
    retain full loaded-value equality and raw-byte SHA-256 expectation.
    Its separate field-set assertion is redundant with that full equality.
    Removing a loaded field must still fail the retained comparison.
  - `test_the_judge_owns_the_three_execution_knobs_and_shared_stages_keep_the_rest`:
    compare the three named execution fields with the input file's values,
    not literals copied from today's file. Preserve namespace separation and
    digest inclusion. Replacing a loaded value with the wrong constant must fail.
  - `test_python_authored_config_and_config_only_vertical_extension`:
    compare loaded policy values with its input, or set independent valid
    values in the test, rather than pinning today's five numeric policy values.
    Keep the published workflow flag, known/unknown vertical acceptance and
    cross-language config binding. A reader discarding an authored policy or
    accepting an unknown vertical must still fail.
  - Rename `test_a_committed_day_reads_an_absent_ranking_field_as_unknown` to
    `test_a_day_written_before_the_ranking_fields_reads_them_as_unknown`, and
    `test_every_committed_day_revalidates_with_no_shortfall_counts` to
    `test_a_desk_written_before_the_shortfall_counts_reads_each_as_unknown`.
    Keep their bodies, populated-input conditions and migration assertions.
  - Clarify gate guidance: historical reader fixtures, known identity values,
    wire-format guarantees and config/consumer bindings are behavior evidence.
    Only checks of incidental stored content belong outside behavior tests.
- **Gates:** Shared changed-test selector and disposable wrong-reader checks.
  Renames preserve the exact collection cases under their corrected names.
- **Dependencies:** Row 1. No production or data change; serialize plan edits.
- **Proof record:** In isolated copies, returning default council settings while
  changing the copied file's `shards` value from 4 to 5 failed the full-value
  comparison. Pinning the similarity reader to 200/1/0 while the copied input
  named 201 pairs failed the input-value comparison. Replacing the feed
  reader's `min_words_article` with 180 failed against the test-owned value
  181. Each mutation failed at its intended assertion; none touched this
  worktree.
- **Gate record:** The shared selector selected the four changed test modules
  and two documentation-only paths. Its first run passed Ruff, mypy (831 source
  files), and all 75 tests in 24.92 seconds, but returned exit 1 because the
  frozen plan import changed its fingerprint during the run. A post-import run
  passed Ruff, mypy (831 source files), and all 75 tests in 10.18 seconds with
  exit 0.

## 9 - Row #8 - Workflow checks retain independent failure evidence

- **Scope:** Keep checks of executable workflow code and its safety boundaries.
  Add bounded evidence that two checkers can detect an invalid input, remove one
  comparison of harness constants, and derive publication dates from its input.
- **Files touched:** `backend/tests/workflows/test_inline_python_imports.py`,
  `test_workflow_inputs.py`, `test_publication_conflict.py`,
  `test_staged_paths.py` in the same directory.
- **Reference checks:** The group-4 supplemental review verified the four bodies
  and helper functions against the frozen baseline; the coordinator also read
  these current bodies. Its other nine rewrite/removal/rename proposals are
  rejected: they protect real trigger, staging, identity or timing behavior.
- **Changes and acceptance proof:**
  - Keep `test_every_inline_program_imports_the_modules_it_uses` and its named
    workflow sweep. Separately drive `_modules_used` and `_bound_names` with
    a bounded program that uses `hashlib` with and without an import. A checker
    that reports no modules or misses bound imports must fail.
  - Keep `test_every_input_an_expression_reads_is_declared_by_that_workflow`
    and its named workflow sweep. Add a constructed workflow that declares one
    input but reads that input and another undeclared input. Require exactly the
    undeclared input to be reported. Dropping references or reading declarations
    as references must fail the relevant constructed case.
  - `test_two_checkouts_keep_both_real_publication_updates`: compare dates with
    the two days registered by the test, in independently chosen newest-first
    order. Dropping either day or reversing order must still fail.
  - `test_the_plan_job_publishes_the_day_directory_it_decided`: retain the real
    workflow output and shell-expression checks; remove only the final equality
    between `SUBSTITUTED_DATE` and `SUBSTITUTED_DAY_DIR`, plus unused imports.
    `test_triggers.py::test_a_dispatched_date_becomes_the_day_it_names` already
    executes that date expansion. A wrong workflow day expression still fails.
- **Gates:** The shared `npm run test:changed` selector chose only the backend
  group and these four files. Whitespace and Ruff passed; mypy found no issues
  in 834 source files; all 15 tests passed. The real two-checkout publication
  test passed. Record:
  `backend/var/checks/5f792818acfe47502019e73501c37bf6d2b22656e984c8fc455c125efb59e731.json`.
- **Negative proofs:** Disposable checker variants that missed used modules,
  missed import bindings, dropped input references or scanned declarations as
  references each failed the new constructed test. Missing-day and reversed
  publication-date lists both failed the input-derived newest-first comparison.
- **Delivery:** Commit `bbea48bbd3e05f9075e360f225a1003dad1721f6` was delivered in
  [#1656](https://github.com/miztiik/yen-idhazh/pull/1656), merged at
  `43bdd37d671275af2f904590f7ca69498cc74a91` after exact-head required CI passed.
  The separate
  suite-wide review obligation in Row 3 remains open. No workflow, production,
  config, data, frontend or dependency changes.
- **Dependencies:** Row 1. Serialize edits to this shared plan.

## 10 - Row #9 - Remove the unused watchlist entry limit

- **Scope:** Remove `collect.watchlist_max_entities`, not enforce it at runtime.
  Owner ruling, kumarsnaveen, 2026-10-23: "A2: Remove the entry limit".
  This explicitly extends Table A row A5; the cap had only a test consumer.
- **Files touched:** `backend/idhazh/contracts/knobs/collect.py`,
  `config/idhazh.json`, `backend/tests/contracts/test_watchlist.py`,
  `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`,
  `tests/fixtures/gardener/pre-yearly-retention/config/idhazh.json`,
  and `docs/concepts/config.md`.
- **Changes and acceptance proof:** Remove the declaration and the key from
  named authored inputs. Replace the committed-list cap assertion with bounded
  generated lists above the old limit, through the real watchlist validator,
  alias-term reader and serialized readback. Refuse the removed key by name
  through both the collect block and aggregate config reader. Keep entity
  kinds, alias matching, retired-entry exclusion and identity validation.
  Preserve the historical fixture's retention and legacy tier-weight fields.
- **Gates:** Inspect the shared changed-test selector; run focused config,
  schema, historical acceptance, binding, matching and gardener coverage under
  the shared gate lock, plus Ruff and mypy. In disposable copies, confirm the
  removed-key proof fails against the base, and a reintroduced entry-count
  restriction fails the generated-list proof. No mocks or network tests.
- **Dependencies:** Row 1. No persisted-payload version or migration is needed
  for repository-authored config. Serialize edits to this shared plan.
- **Proof record:** Against base `ce1813d34104d11e66d9846d37bf5ce5a588601c`,
  `test_the_removed_entry_limit_is_refused_by_name` fails because the old
  setting is accepted. In a disposable copy, adding a 30-entry bound to
  `Watchlist.entities` fails both
  `test_authored_entries_are_not_limited_by_count[31]` and `[61]` at the real
  validator. The temporary copy was removed. The removed case is
  `test_the_watchlist_stays_inside_its_configured_cap`; the watchlist module
  moves from five collected cases to seven.
- **Gate record:** The shared selector selects full coverage for shared config
  inputs. Focused local checks passed Ruff, mypy (834 source files), 156
  app/appearance config cases, and 409 schema, historical acceptance, binding,
  tag, rank and named historical-gardener-consumer cases. The initial invocation
  named a nonexistent config test and ran no cases; a later overly broad
  gardener-directory run was stopped and replaced with its sole changed-fixture
  consumer. Neither is counted as a pass. Full-suite CI remains required before
  merge.

## 11 - Row #10 - Independent historical reader proofs

- **Scope:** Make historical test inputs independent of production migration
  tables, replace a self-derived month-window expectation, strengthen published
  alias output checks, and preserve historical values without pinning whitespace.
- **Files touched:** `backend/tests/contracts/test_two_call_ledgers.py`,
  `test_stamped_boundary.py`, `test_page_ceilings.py`, `test_run_manifest.py`,
  `test_source_classification_history.py`, `test_served_day.py` in the same
  directory; `docs/architecture/contracts/schemas.md`.
- **Changes and acceptance proof:**
  - Spell the fourteen historical call and machine column renames literally.
    Keep both call records, totals, absence of current headings, and full
    read-back equality. Deleting one production rename must fail this case.
  - Collect the three dropped-column cases from literal historical names:
    `runner_name`, `cgroup_peak_bytes`, `max_output_tokens`. Deleting a
    production dropped-column entry must fail its still-collected case.
  - Check inclusive 93-, 180- and 367-day windows against independently known
    maxima of 5, 7 and 14 calendar months. Retain `months_kept` for its independent
    index-ceiling caller; remove it only from the tautological assertion.
    With daily retention 45 and monthly retention forever, refuse year packing
    at 76 days by name and accept 77 days. Removing the extra wake margin must
    fail the refusal.
  - Retain raw historical manifest alias-key checks. Also require emitted
    records not to contain Python-only `items_decided` or `decision_ms` names.
  - Preserve every recorded historical taxonomy key and value and require
    next-write stability. Retain empty source-kind and source-tier assertions;
    do not rewrite the fixture. This applies Row 1 E1/E2, not a byte-output
    change. Dropping lenses or adding registry fields must fail.
  - Vary the historical authored institution weight to 0.5, with expected 0.5,
    while an empty weight record expects the original 1.0 default. Preserve
    trade-press 0.6 and community 0.3 defaults in both cases. A reader ignoring
    the authored institution weight must fail the non-default case.
  - Rename the served-day test to
    `test_a_day_without_the_ranking_fields_serves_a_valid_view_with_them_unknown`.
    Preserve its complete body and its populated-input condition.
- **Gates:** Shared changed-test selector over the six modules; disposable
  mutation proofs with exact case identifiers and counts recorded separately.
  No production, config, fixture, schema, acceptance or emitted-byte change.
- **Dependencies:** Row 1. Serialize edits to this shared plan; do not merge.
- **Gate record:** The selector chose exactly the six named modules and the
  documentation-only schema page. Whitespace and Ruff passed; mypy found no
  issues in 834 source files; all 65 pytest cases passed, zero skipped.
  Record:
  `backend/var/checks/13e3fe73f697df9d36eb1e2b3b0b7d5ad9e5d183f211acbc7e1b05c4bf43e317.json`.
  Baseline collection had 53 functions and 64 cases; final coverage has 54
  functions and 65 cases. One new boundary test, one name correction and two
  revised weight-case identifiers explain every difference; no case is removed.
- **Negative proofs:** Nine production faults in disposable copies caused
  eleven intended failed cases, with no collection errors. Removing one rename
  still collects its one case and fails readback; removing a dropped-column
  entry keeps all three cases and fails only `cgroup_peak_bytes`. Their old
  tests passed the same faults, with the old dropped-column test losing a case.
  Floor division by 30 fails all three calendar expectations. Dropping the extra
  wake accepts 76 and fails the refusal. Emitting each Python-only manifest key
  fails the new absence assertion. Losing lenses or adding registry fields
  fails taxonomy value equality. Ignoring authored institution 0.5 fails its
  expected value while the old default-valued cases pass. A whitespace-only
  taxonomy fixture change still passes. All disposable copies were removed.
- **Plan integration:** The coordinator released the serialized slot and named
  Row 9's frozen full successor as the input. All prior row text and the exact
  owner ruling in A5 remain; D3 remains open. Rows 5, 8 and 9 have their verified
  merge receipts above. Plan-only integration does not repeat unchanged gates.
- **Delivery:** Implementation commit `90c58a26c` was delivered in
  [#1659](https://github.com/miztiik/yen-idhazh/pull/1659), merged at
  `f0449de3db08c710e5b2292a03910da157bcb498`. The suite-wide Row 3 review
  remains open.

## 12 - Row #11 - Contract tests prove authored and constructed behavior

- **Scope:** Replace assertions tied to current committed values with bounded
  authored or constructed inputs in seven contract-test modules. Preserve the
  contract behavior, historical acceptance, path rules and reader bindings.
- **Files touched:**
  - `backend/tests/contracts/test_retention_knobs.py`
  - `backend/tests/contracts/test_model_registry.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_taxonomy_and_prompts.py`
  - `backend/tests/contracts/test_sources_and_marks.py`
  - `backend/tests/contracts/test_ledger_index.py`
  - `backend/tests/contracts/test_source_classification_binding.py`
- **Changes and acceptance proof:**
  - Compare the loaded rest threshold with the file value, keep the tuned
    threshold and real `after_failures` caller, and remove only the committed
    literal. Construct a finite published window one day beyond the authored
    first-sight window; require the loaded value and relation, not `730`.
    Keep named retired-key refusals and both the moved key and successor file
    in the prune refusal.
  - Hash the copied model-file bytes independently with SHA-256, then prove
    unchanged stability and changed-byte sensitivity. Remove the stale-teacher
    premise while retaining its named destination error. Keep
    `declared_for == sha256` for every file in the bounded `MODEL_FILES` list.
  - Construct a nonalphabetical mixed-consent registry with an independent
    expected order. Explicitly enable consent when proving paused and retired
    family behavior. Construct every grain's valid stem/suffix pair and both
    refused edits instead of scanning committed registry entries.
  - Require missing definitions to be refused for active verticals, lenses
    and events, and keep the prompt-block proof that all active definitions
    appear while draft and retired entries do not. Use the bounded
    `definitions-a` taxonomy to prove a published retired lens still reads
    while its tombstone stops new matching.
  - Require the compact-index decoded model to equal the object written, not
    only to serialize to stable text. Compare TypeScript field types with the
    live Python JSON Schema using the TypeScript compiler API, require an
    invalid property name in the refusal, and test omitted defaults beside
    separately authored source kind and entity tier values.
- **Gates:** Run the shared changed-test selector over the seven backend
  modules and the frontend type-binding logic test, with Ruff and mypy.
  In disposable archive copies, fault each preserved behavior and record its
  full failing pytest or frontend test identifier below. The frontend change
  adds only a contract test and selector inventory entry; no production,
  config, committed data, persisted shape, emitted-byte or acceptance change.
- **Dependencies:** Row 1. Serialize edits to this shared plan.
- **Proof record:** Disposable archive faults each failed the named case; no
  temporary fault changed this worktree.
  - Hard-coding the plan caller failed
    `backend/tests/contracts/test_retention_knobs.py::test_the_rest_rule_reads_the_knob_the_committed_config_spells`.
    Aliasing the published window to the first-sight field failed
    `backend/tests/contracts/test_retention_knobs.py::test_the_published_window_is_unbounded_or_outlives_the_first_sight_store`.
    Truncating the prune successor path failed both
    `backend/tests/contracts/test_retention_knobs.py::test_a_prune_number_left_in_finetune_is_sent_to_the_squash_declaration[prune_every_days]`
    and
    `backend/tests/contracts/test_retention_knobs.py::test_a_prune_number_left_in_finetune_is_sent_to_the_squash_declaration[prune_keep_days]`.
    Replacing the named retired-key refusal with a generic error failed all
    six cases of
    `backend/tests/contracts/test_retention_knobs.py::test_a_config_still_spelling_a_retired_knob_is_refused_by_name`:
    `[models-visual_planner]`,
    `backend/tests/contracts/test_retention_knobs.py::test_a_config_still_spelling_a_retired_knob_is_refused_by_name[models-route]`,
    `backend/tests/contracts/test_retention_knobs.py::test_a_config_still_spelling_a_retired_knob_is_refused_by_name[run-two_calls_per_item]`,
    `backend/tests/contracts/test_retention_knobs.py::test_a_config_still_spelling_a_retired_knob_is_refused_by_name[run-visual_planner_budget_minutes]`,
    `backend/tests/contracts/test_retention_knobs.py::test_a_config_still_spelling_a_retired_knob_is_refused_by_name[run-route_budget_minutes]`
    and
    `backend/tests/contracts/test_retention_knobs.py::test_a_config_still_spelling_a_retired_knob_is_refused_by_name[finetune-student]`.
  - Normalizing model-file bytes failed
    `backend/tests/contracts/test_model_registry.py::test_the_model_file_bytes_are_digested_with_the_rest_of_the_config`.
    A stale pairing in an inactive named model file failed
    `backend/tests/contracts/test_model_registry.py::test_every_model_file_loads_and_not_only_the_one_the_pointer_names`.
    Repointing the stale teacher to the wrong destination failed
    `backend/tests/contracts/test_model_registry.py::test_the_teacher_names_the_slot_the_model_file_declares`.
  - Reversing registry family order failed
    `backend/tests/contracts/test_ledger_registry.py::test_explorer_catalog_derives_eligible_names_from_registry_order`.
    Tying explicit consent to family status failed both
    `backend/tests/contracts/test_ledger_registry.py::test_explorer_consent_is_independent_of_family_lifecycle[paused]`
    and
    `backend/tests/contracts/test_ledger_registry.py::test_explorer_consent_is_independent_of_family_lifecycle[retired]`.
    Removing the flat stem failed
    `backend/tests/contracts/test_ledger_registry.py::test_a_grain_accepts_its_path_fields_and_refuses_the_other_shapes[flat-score-distribution-.json]`;
    requiring a tree suffix failed the same test's
    `[tree-None-None]` case.
  - Removing active-definition validation failed all three constructed cases
    `backend/tests/contracts/test_taxonomy_and_prompts.py::test_an_offered_entry_without_a_definition_is_refused[verticals]`,
    `backend/tests/contracts/test_taxonomy_and_prompts.py::test_an_offered_entry_without_a_definition_is_refused[lenses]`
    and
    `backend/tests/contracts/test_taxonomy_and_prompts.py::test_an_offered_entry_without_a_definition_is_refused[events]`.
    Omitting an active event and admitting a draft
    each failed
    `backend/tests/contracts/test_taxonomy_and_prompts.py::test_a_draft_or_retired_entry_reaches_no_prompt`.
    Making a retired lens matchable failed
    `backend/tests/contracts/test_sources_and_marks.py::test_a_published_item_carrying_a_retired_lens_still_reads`.
  -   Omitting compact-index state from a stable writer, with an empty entry in
  the disposable input, passed text idempotence but failed object equality in
  `backend/tests/contracts/test_ledger_index.py::test_a_compact_index_writes_one_entry_a_line_and_reads_back_what_it_wrote`.
  The TypeScript binding now parses the interface with the compiler API and
  compares it with the live Python JSON Schema; its post-change fault proof
  is pending. Accepting unknown properties failed
  `backend/tests/contracts/test_source_classification_binding.py::test_invalid_registry_refuses_loading_by_name[invalid-property-invented_rule]`.
  Overwriting the authored source kind and entity tier each failed
  `backend/tests/contracts/test_source_classification_binding.py::test_configured_defaults_apply_only_to_authored_config`.
- **Gate record:** Pending the final shared-selector run and post-change
  TypeScript binding fault proof. The earlier 226-case backend-only record
  predates this frontend test and does not certify the current change.
- **Plan integration:** The serialized slot is released. Row 5 and Row 9
  delivery receipts, Row 10's verified head and the exact owner ruling in A5
  are retained. D3 remains open; Row 10 is not a dependency.
- **Delivery:** Test and plan changes are committed in `62968e83a`; the
  current-main merge is `6a2179890`. The phase pull request is pending.

## 13 - Row #12 - Explicit controls and measurement behavior

- **Scope:** Nine test modules choose their own control inputs and check
  independent values. Preserve actual collection, ledger bytes, failure
  reporting, timing arithmetic, fresh-clone defaults and policy bounds.
- **Files:** `test_host_telemetry_control.py`, `test_job_machine.py`,
  `test_ledger_families.py`, `test_memory_profiling_control.py`,
  `test_memory_sampler.py`, `test_item_records.py`, `test_labels.py`,
  `test_measure_budgets.py`, `test_reference_dataset.py` under `backend/tests/`.
  Also `silicon.py` and `task_telemetry.py` under
  `backend/idhazh/telemetry/`, and `docs/reference/host-metrics.md`.
- **Explicit inputs:** Host and memory controls use copied test settings.
  Inherit/on/off resolves independently to false/true/false against a disabled
  copied memory default. The labelling sitting writes its own operator roster
  while preserving the committed-ledger byte check. Supplied registry entries
  each determine the expected name, lifecycle and UTC onboarding date.
- **Independent values:** Choose `Q5_K_S` and expect `q5_k_s`; calculate the
  rendered-prompt and extracted-text digests with hashlib. Count each supplied
  label bucket independently of the production selector. Identify the supplied
  short source row by URL. Parse real calendar stamps, allowing the documented
  minute/second same-day suffix. Require serialized measurement spread `0.0`
  and the actual imported `TokenizerMeasured` instance.
- **Actual refusal:** A copied model config changes both `sha256` and
  `declared_for`; the real stale-check command must exit 1. Preserve swapped
  digest/site evidence. A real unsupported urllib scheme reaches the transport
  error handler without a socket; require exit 2, stderr, empty stdout and no
  requested reading/page file.
- **Structural acquisition:** Coordinator consulted Fowler and authorized
  forwarding existing keyword-only `ask_placement=True` through
  `task_telemetry.record` and `silicon.file_machine_row` into `read_row`, never
  the elapsed-time writer. Production defaults are unchanged. Tests pass false,
  retain actual local collection and ledger writes, and restore a scoped
  `sys.setprofile` guard that refuses entry to the actual placement reader.
  Either missing forwarding hop fails before external metadata access.
- **Preserved evidence:** Keep count six, domain counts `[2, 4]`, labelling
  policy limits six and ten, attempt 2 against environment attempt 9, 60-second
  arithmetic, work-failure and instrumentation diagnostics. Remove only the
  truthy-digest loop, committed-roster nonemptiness, current-tree measurement
  freshness premise and source-text spelling of the imported record type.
  Named digest survivors are
  `test_a_successful_extraction_keeps_its_paragraph_break_and_its_provenance`
  and `test_the_saved_text_is_the_whole_article_and_keeps_its_paragraphs`.
- **Failure proofs:** 22 minimal disposable production faults each fail at the
  intended assertion, with unchanged and restored controls passing; original
  source hashes verified. Fourteen controlled cases also pass when copied
  committed host/fingerprint/memory defaults are disabled and the roster is
  empty. No mock, added skip, changed acceptance rule or configuration knob.
- **Bounded-input correction:** Replace both copied-tree config reads with the
  named-input `council._config.copy_config` helper. The memory-loader case also
  copies only `idhazh_gardener.json` and the declaration files named by its
  `task_names`. The two affected modules pass 42 cases; Ruff and mypy pass.
  Re-run disposable stale-exit, memory-inherit, memory-override and memory-YAML
  faults against the corrected tests; every intended failure and restored
  control passes. Hashes and logs are in the Row12 session evidence.
- **Collection:** Exact base `3d6d4b9f6a4ea4e7681576531963e27f11e64332` and
  final implementation each collect 7,218 cases. No function or parameter case
  is removed. Two renames: `test_the_committed_config_names_a_labeller` becomes
  `test_the_committed_labelling_knobs_hold_their_documented_values`, and
  `test_read_refuses_rather_than_guessing_when_no_server_answers` becomes
  `test_read_refuses_without_output_when_tokenizer_transport_fails`.
- **Gates:** Shared selector expands to full backend. Lint passes; mypy passes
  on 834 source files. Local pytest: 4 failed, 7,207 passed, 7 existing skips.
  Both sparse-publication Git-safety failures and the absent Windows hardware
  fingerprint reproduce on the exact unchanged base. The fourth failure still
  lacks a Bun local package after two frozen restore attempts fail with EPERM.
  No Git safety setting, manifest or lockfile changes. Final helper tests:
  15 passed and 2 existing POSIX skips; final helper type checks pass. Linux CI
  must establish complete-suite success on the merge candidate.
- **Separate finding:** Existing `date.today()` in `measure_budgets.py` is not
  changed. Keep both cold-start measurement tests: stored spread is zero, while
  one repeat makes comparison unavailable. Keep recorded loopback integration.
- **Plan integration:** Row 11 released the serialized slot at
  `26ac9f90cda08456c1f861c26285a2129924804c`. Its frozen plan is preserved
  exactly before this section is added, without importing its implementation.
  Current main, including Row 10 at `f0449de3db08c710e5b2292a03910da157bcb498`,
  was merged without rewriting history. Plan-only integration
  does not repeat unchanged application gates. D3 remains open.
- **Delivery:** Implementation `32c85d883` is delivered in open PR
  [#1661](https://github.com/miztiik/yen-idhazh/pull/1661), not merged by this
  worker. D12 remains IN-FLIGHT pending required Linux CI and merge.
- **Dependencies:** Row 1. Shared-plan editing remains serialized.

## See also

- [Plan execution](../docs/how-to/execute-a-plan.md).
- [Engineering contract](../CLAUDE.md#13-test-coverage-policy).
- [Contracts and serialization](../docs/architecture/contracts/schemas.md).
- [Local and CI checks](../docs/how-to/run-the-gates.md).
- [Publication validation](../docs/architecture/publishing/what-stops-a-broken-day-being-published.md).
