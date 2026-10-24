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
| A5 | Contract impact | No persisted shape, version stamp, migration, serializer, digest algorithm, production validation rule or dependency changes. Exception: Row 9 removes the unused `collect.watchlist_max_entities` configuration knob and its test-only entry cap, authorized by kumarsnaveen on 2026-10-23. Named config fixtures lose only that setting; historical retention and source-weight evidence stays intact. Session review reports are not a new application artifact. Exception: Row 16 replaces the whole-tree state CSV audit with a bounded supplied-commit-range gate, authorized by kumarsnaveen on 2026-10-23 UTC (option A1). Runs without a range explicitly provide no whole-tree integrity certification; invalid supplied ranges fail closed. Exception: Row 17 adds `observability.host_fingerprint_placement_enabled`, a default-on strict config control for Python placement metadata acquisition, authorized by kumarsnaveen on 2026-10-24 UTC (option A1). It leaves local machine measurements and ledger writes active and changes no persisted payload. Exception: Row 22 makes the existing council planning and collection total-job deadlines independently configurable through a standard-library-only prerequisite, covered by kumarsnaveen's structural-expansion authorization on 2026-10-24 UTC. Both defaults remain 30 minutes; the separate shard deadline, persisted payloads and package dependencies are unchanged. |
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
| D10 | 10 | Independent historical reader proofs | 1 | I | DONE | independent-historical-reader-proofs | [#1659](https://github.com/miztiik/yen-idhazh/pull/1659), merged 2026-10-24 UTC at `f0449de3db08c710e5b2292a03910da157bcb498` | - |
| D11 | 11 | Contract tests prove authored and constructed behavior | 1 | J | DONE | config-refusal-selection-proofs | [#1664](https://github.com/miztiik/yen-idhazh/pull/1664), merged at `90ea0e77cedaf7eeaff8e9690bacf144eebb44d3` | - |
| D12 | 12 | Explicit controls and measurement behavior | 1 | K | DONE | explicit-control-behavior-proofs | [#1661](https://github.com/miztiik/yen-idhazh/pull/1661), merged at `6a43c2b3c4747358a678587d8d877245b9b49134` | - |
| D13 | 13 | Extraction and metric behavior | 1 | L | IN-FLIGHT | row13-test-proofs | - | - |
| D14 | 14 | Grouping and dataset behavior | 1 | M | DONE | grouping-and-dataset-proofs | [#1665](https://github.com/miztiik/yen-idhazh/pull/1665), merged at `fe086c907f50f52c7c51a9c98c4425ce6f6e6357` | - |
| D15 | 15 | Encoder thread resolution uses production behavior | 1 | N | DONE | prove-encoder-thread-resolution | [#1667](https://github.com/miztiik/yen-idhazh/pull/1667), merged at `956fd7e27cdcbc927bd86ce54ecede4f993779ef` | - |
| D16 | 16 | Bounded state CSV integrity checks | 1 | O | DONE | bound-csv-integrity-checks | [#1668](https://github.com/miztiik/yen-idhazh/pull/1668), merged at `cff5cc58c8cc15c59b5b525fca84335e2e88c4ce` | - |
| D17 | 17 | Default-on host-placement acquisition control | 12 | P | IN-FLIGHT | host-fingerprint-placement | - | - |
| D18 | 18 | Workflow checks reject supported broken inputs | 1, 22 | Q | IN-FLIGHT | strengthen-workflow-proof-checks | - | - |
| D19 | 19 | Independent source-health publication proofs | 1 | R | DONE | prove-source-health-publication | [#1674](https://github.com/miztiik/yen-idhazh/pull/1674), merged at `e7f46b2317852ea5d3f212f83ea86ac51edc05ed` | - |
| D20 | 20 | Prove reader output behavior | 1 | S | IN-FLIGHT | prove-reader-output-behavior | - | - |
| D21 | 21 | Prove ledger dates and named-plan reads | 1 | T | DONE | prove-ledger-date-selection | [#1675](https://github.com/miztiik/yen-idhazh/pull/1675), merged at `31a689f073d602e75870f7fa48da72d3043f6c13` | - |
| D22 | 22 | Configured council planning and collection job deadlines | 1 | U | IN-FLIGHT | configure-council-job-deadlines | - | - |
| D23 | 23 | Independent qualification and planning controls | 1 | V | IN-FLIGHT | prove-planning-controls-independently | - | - |
| D24 | 24 | Independent council test controls | 17 | W | IN-FLIGHT | prove-council-controls-independently | - | - |
| D25 | 25 | Concrete remaining gardener and ledger safety proofs | 24 | X | IN-FLIGHT | strengthen-gardener-safety-proofs | - | - |
| D26 | 26 | Prove time boundaries without stand-ins | 21, 25 | Y | IN-FLIGHT | prove-time-boundaries-without-stand-ins | - | - |
| D27 | 27 | Explicit offline gardener collection controls | 17, 26 | Z | IN-FLIGHT | control-gardener-host-collection | - | - |
| D28 | 28 | Independent prefix normalization arithmetic | 1, 27 | AA | IN-FLIGHT | prove-vector-arithmetic | - | - |
| D29 | 29 | Populated registry values and mandatory real CSV reader | 1, 28 | AB | IN-FLIGHT | close-contract-proof-gaps | - | - |

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
  - `frontend/tests/source-classification-binding.spec.ts`
  - `frontend/scripts/test-groups.ts`
- **Changes and acceptance proof:**
  - Compare the loaded rest threshold with the file value, keep the tuned
    threshold and real `after_failures` caller, and remove only the committed
    literal. Construct a finite published window one day beyond the authored
    first-sight window; require the loaded value and relation, not `730`.
    Keep named retired-key refusals and both the moved key and successor file
    in the prune refusal; remove one duplicate read of the same config file.
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
    only to serialize to stable text. Compare required TypeScript field names
    and types with the live Python JSON Schema using the TypeScript compiler
    API; an optional marker is refused because serialized output emits the
    field. Require an invalid property name in the refusal, and test omitted
    defaults beside separately authored source kind and entity tier values.
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
  - Omitting compact-index state from a stable writer, with an empty entry in
    the disposable input, passed text idempotence but failed object equality in
  `backend/tests/contracts/test_ledger_index.py::test_a_compact_index_writes_one_entry_a_line_and_reads_back_what_it_wrote`.
    The TypeScript binding compares required interface AST fields with the
    live Python JSON Schema. Boolean-to-string and optional-field AST
    mutations fail
    `frontend/tests/source-classification-binding.spec.ts::the Python source-kind binding refuses an optional TypeScript field`
    and
    `frontend/tests/source-classification-binding.spec.ts::the Python type binding refuses a boolean field changed to string`.
    Accepting unknown properties failed
  `backend/tests/contracts/test_source_classification_binding.py::test_invalid_registry_refuses_loading_by_name[invalid-property-invented_rule]`.
    Overwriting the authored source kind and entity tier each failed
  `backend/tests/contracts/test_source_classification_binding.py::test_configured_defaults_apply_only_to_authored_config`.
- **Gate record:** The shared selector chose the seven backend modules and all
  frontend groups because the selector inventory changed. Whitespace, Ruff,
  mypy, Svelte checks, test-tooling checks and the canary build passed. Pytest
  passed 225 cases, logic passed 1,501, and browser checks passed 113; none
  failed or skipped. Record:
  `backend/var/checks/cdbdb0c4954ddedb8a33c187ae08431d04bd5d604d09f1b73cc8362d5b53fb60.json`.
  That run predates the optional-field proof and the duplicate-read cleanup.
  The final targeted results are 27 passing retention tests and 3 passing
  source-kind binding tests, including both bounded type faults; `npm run check`
  found zero errors and warnings. The merge itself did not repeat local
  application gates. PR checks `scope`, `gates`, `browser` and `site` passed at
  the prior Row 11 head; `robots` was skipped.
- **Plan integration:** The serialized slot is released. Row 5 and Row 9
  delivery receipts, Row 10's merged receipt and the exact owner ruling in A5
  are retained. D3 remains open; Row 10 is not a dependency.
- **Delivery:** Tests and the initial plan update are committed in `62968e83a`
  and `26ac9f90c`; current main, including Row 10's merge receipt, is merged
  into this branch without rewriting history. The AST binding proof is
  committed at `f0498735f`; [#1664](https://github.com/miztiik/yen-idhazh/pull/1664)
  merged at `90ea0e77cedaf7eeaff8e9690bacf144eebb44d3`. The current
  conflict-resolution candidate and targeted check results are recorded in
  the Row 11 execution report. This worker did not merge the phase PR.

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
  15 passed and 2 existing POSIX skips; final helper type checks pass. On
  pre-merge heads `cbb23a22ddcd711ebe3fa34a042e707050ba2a1b` and
  `95e2808d8942b0aeb8995c2fc919d772a9952acc`, required `scope`, `gates`,
  `robots` and `site` checks passed; `browser` skipped. The latest main
  integration at `57366d88ae2bc0209121c5c52e6f2eb9eee07893` also passed
  `scope`, `gates`, `robots` and `site`; `browser` skipped. Run:
  `https://github.com/miztiik/yen-idhazh/actions/runs/40080891074`.
- **Separate finding:** Existing `date.today()` in `measure_budgets.py` is not
  changed. Keep both cold-start measurement tests: stored spread is zero, while
  one repeat makes comparison unavailable. Keep recorded loopback integration.
- **Plan integration:** Row 11 released the serialized slot at
  `26ac9f90cda08456c1f861c26285a2129924804c`. Its frozen plan is preserved
  as the starting point before this section was added. The corrected Row 11
  section and merge receipt are preserved above; its implementation arrived
  through the normal main merge.
  Current main, including Row 10 at `f0449de3db08c710e5b2292a03910da157bcb498`,
  was merged without rewriting history. Main through
  `60b301d1c9edc188e2993252ebd5850d666bf8ec`, including the Row 11 merge, was
  then merged normally in a conflict-only integration. Latest main through
  `cff5cc58c8cc15c59b5b525fca84335e2e88c4ce`, including Row 16, was also
  merged normally. Plan conflicts were resolved by retaining the completed
  D11 merge receipt, Row 12's full section, and the complete Row 16 section;
  the complete Row 13-15 sections and the Row 16 A5 ruling are preserved.
  Exact-head CI passed. All 12 reviewed Row 12 test, production and
  documentation files remain byte-identical to
  `cbb23a22ddcd711ebe3fa34a042e707050ba2a1b`. D3 remains open.
- **Delivery:** Implementation `32c85d883` was delivered in
  [#1661](https://github.com/miztiik/yen-idhazh/pull/1661), merged at
  `6a43c2b3c4747358a678587d8d877245b9b49134`. The worker did not merge it.
- **Dependencies:** Row 1. Shared-plan editing remains serialized.

## 14 - Row #13 - Extraction and metric behavior

- **Scope:** Replace checks tied to current corpus, fixture or output counts
  with behavior proofs driven by independent test inputs. Add a validated
  config root to the shipped drift-report CLI so its configured behavior is
  tested through the actual command. Preserve production thresholds and
  acceptance rules.
- **Files touched:** `backend/tests/test_corpus.py`,
  `backend/tests/test_data_wrangler.py`, `backend/tests/test_derived_values.py`,
  `backend/tests/test_drift.py`, `backend/tests/test_elements.py`,
  `backend/tests/test_entity_gap.py`, `backend/tests/test_evals.py`,
  `backend/utilities/drift_report.py`, `docs/reference/github-actions.md` and
  this plan for its Row 13 evidence correction.
- **Changes and acceptance proof:**
  - Refuse a nonpositive pool multiple at the existing validation boundary;
    retain the committed-config loader proof. Give the data-wrangler row cap
    and floor tests their own valid settings, and derive printed counts,
    refusals and shortfalls from those settings.
  - Keep successful committed-plan resolution and add a missing-element
    refusal. Use a test-owned histogram bin count and require the real resolver
    to return that number of bins.
  - Review drift through the shipped CLI with a test-owned config root and
    populated ledger windows. Twenty rows pass the committed floor but fail
    the validated nondefault floor of 21. The CLI accepts `--config`, defaults
    to `DEFAULT_CONFIG_DIR` and passes that root to the real config loader.
    Check the reported shortfall, not source text or current defaults.
  - Replace fixed element totals with nonempty quantity and date conditions.
    Keep `ElementTable` overlap acceptance and prove the producer's real
    settlement keeps the date over a conflicting quantity. Remove the bounded
    span-drift sweep only after both named consumer and writer survivors fail
    the production fault; retain the independent SHA-256 oracle.
  - Derive entity-gap denominators from the supplied registry. Derive
    evaluation source lengths from `article.text.split()` for current and
    historical payloads, preserving unknown-source behavior for old cut
    payloads.
  - Choose a test-owned cap and bands so the original word count is above a
    higher band while the post-cut count falls below it. Preserve the
    independent 2,500-token history proof and safety bounds; do not change
    truncation policy.
- **Gates:** Against base
  `0ed955f54fc4b51e8a362574161a2e71df693514`, the initial bounded collection
  contained 244 cases across the seven modules; the final collection contains
  244. The final identifier disposition is five renames, one added missing-link
  case and one removed bounded span-drift sweep; no other identifier changed.
  Whitespace and Ruff passed, mypy passed over 834 source files, and all 244
  pytest cases passed. The stable post-merge selector on
  `f0449de3db08c710e5b2292a03910da157bcb498` passed Ruff, mypy over 834 source
  files and all 244 selected tests; record:
  `backend/var/checks/3b541520238458854a16e86dd8f2d82f5abbbd69ff4ace392779c5ef701d7073.json`.
  The focused CLI config-floor test and Ruff passed. Exact-head CI run
  `40082666626` passed all five jobs on `3de8c29dfbdb983b1034c0a12840ce76538148e7`.
  No broad local backend selector was repeated for the correction; exact-head
  CI supplies backend and type coverage.
  Record: `backend/var/checks/df85b2ab916049084e39bd0b3425b033fb75e127c6e5c9814a3097f144f70958.json`.
  The initial collection record used the original base above.
- **Negative proofs:** Reuse the 16 original non-drift fault proofs because
  their consumed source and test inputs are unchanged. The committed-config
  refusal proof set `qualification_pool_multiple` to zero; the named config
  validation test refused it. Two drift production faults failed the named
  CLI config-floor test: ignoring `--config`, and replacing the loaded report
  floor with its default. Both restored controls passed. For the CLI, the
  original and restored source SHA-256 is
  `5b27ed9409a021a6df171c7e6a5a7591ba35ac5e67e62ab320037089da8f35cc`;
  the faulted hash is
  `a51d1d87222ae6ea588fa9b3d65ef9ef411d2c4db79ff0960839f5f8632a53cf`.
  For the report, the original and restored source SHA-256 is
  `6d5367f97db07d87c1d0cf5f3d2e6869a5aa8c328bbbaf9b48bc9c1135f1bf60`;
  the faulted hash is
  `b6e89ae1b7daf389583d14841126262438e32322715272891f8718193839acbe`.
  Both disposable worktrees were removed.
- **Plan integration:** The coordinator released the slot and named frozen
  predecessor `fc2711237a90f4b009e1d3cabf1bad2b77b69582` as the source. Rows 11
  and 12 and all earlier plan text are preserved; D10 records its verified
  merge on 2026-10-24 UTC. Latest main through Row 19 was merged normally at
  `e7f46b2317852ea5d3f212f83ea86ac51edc05ed`; all main sections through Row 19
  remain. A5 is unchanged and D3 remains IN-FLIGHT. No Row 17 setting was
  imported.
- **Delivery:** Implementation and documentation correction are delivered in
  [#1670](https://github.com/miztiik/yen-idhazh/pull/1670), with source commit
  `3de8c29dfbdb983b1034c0a12840ce76538148e7`; the worker does not merge it.
  The suite-wide Row 3 review remains open.
- **Dependencies:** Row 1. Serialized plan editing is released for Row 14.

## 15 - Row #14 - Grouping and dataset behavior

- **Scope:** Make grouping, judge sampling, pair population and brief-band
  expectations independent of current config values. Preserve approved human
  labels, identity, grammar, safety and historical behavior.
- **Files touched:** `backend/tests/test_same_story.py`,
  `backend/tests/test_similarity_judge.py`,
  `backend/tests/test_story_dataset.py` and `backend/tests/test_summarize.py`.
- **Changes and acceptance proof:**
  - R1-R5 supply a valid test-owned similarity floor of 0.9 and independently
    prove the encoded vectors' cosine is below it. Keep exact-headline,
    one-word mismatch, rounded-price, different-figure and distinct-masthead
    grouping/count assertions and separate committed-policy safety proofs.
  - R6 supplies distinct valid judge and entry temperatures, 0.37 and 0.71,
    through copied test-owned configs before the real loopback request. Keep
    posted top-p and seed, grammar, entry and shared-weights identity checks.
  - R7 thinking flags remain branch preconditions and are unchanged. R8's
    supplied previous value of 0.94 and `test_similarity_fit.py` are unchanged.
  - R9/R10 preserve all independent B1-B10 human labels and B10's unchecked
    sources, unresolved boundary and catalog safety assertions. Existing
    catalog review and decision validation also accept those article
    decisions. No semantic pair-coverage algorithm is added or claimed.
  - R11 derives the full unordered-pair population from the input articles:
    n * (n - 1) / 2. Test-owned sampling produces a smaller frame while keeping
    representative/challenge overlap, missing-vector and deterministic-sample
    proofs. The expected population does not come from produced rows.
  - R12 supplies distinct valid 43-57 and 83-109 word bands. The brief article
    requests exactly the supplied brief band, not the longer-source band,
    without using the production band-selection helper as its oracle.
- **Gates:** The shared changed-file selector passed whitespace, Ruff and mypy
  over 834 source files; all 427 cases in the four selected modules passed,
  with no skips. Record:
  `backend/var/checks/431186ada16219c257a2e517e20b29f3997a039c5af0120fe577a2ac96e17588.json`.
  No test identifier was added, removed or renamed.
- **Negative proofs:** Ten disposable production faults, R1-R6 and R9-R12,
  failed their named tests. The ten-case clean control passed before and after
  injection. Each production-copy file was restored byte-for-byte, and the
  four test-file SHA-256 hashes remained unchanged. Faults covered headline
  equality, price agreement, masthead identity, posted temperature, typed
  parent acceptance, nullable source-check time, pair population and brief
  band selection. The original checkout's production files were never edited.
- **Plan integration:** Imported the complete frozen Row 13 predecessor with
  SHA-256 `e70837f6e5c8b8ae8bd035baf992bc378f366015b6873543b89957f3fa2107fc`.
  Only D14 and this section were added. All prior rows, including A5, D3,
  Rows 11-13 and the D10 merge receipt, remain unchanged.
- **Delivery:** Implementation was delivered in
  [#1665](https://github.com/miztiik/yen-idhazh/pull/1665), merged at
  `fe086c907f50f52c7c51a9c98c4425ce6f6e6357`. No production, config, contract,
  fixture, prompt, acceptance, frontend or dependency changes.
- **Dependencies:** Row 1. The frozen complete successor releases the
  serialized plan editor to Row 15 before PR delivery or CI completes.

## 16 - Row #15 - Encoder thread resolution uses production behavior

- **Scope:** Replace the test-owned thread-resolution formula with exact
  expectations against the resolver used by the real encoder scoring stage.
  Preserve configured-count precedence, automatic selection and the positive
  fallback when the processor count is absent or zero.
- **Files touched:** `backend/utilities/compare_summary_encoders.py`,
  `backend/tests/contracts/test_encoder_reading.py` and this plan.
- **Changes and acceptance proof:** Extract
  `resolve_encoder_thread_count(requested, available_processors)` without
  changing the resolution rule. The real scoring stage supplies the configured
  request and detected processor count, sets library threads, reads back the
  actual thread count and retains processor-availability recording. Five
  test-owned cases require independently specified exact results: explicit
  count wins over a different detected count; automatic uses the detected
  count; absent and zero processor counts fall back to one; an explicit count
  needs no processor reading. The authored-config nonnegative check remains.
- **Identifier disposition:** Replace
  `test_the_thread_setting_resolves_to_a_positive_count` with the five
  `test_encoder_thread_count_resolution` parameter cases and
  `test_configured_thread_count_is_nonnegative`. No reading-contract test is
  removed. Do not change `contracts/test_app_config.py`; its proposed
  similarity-inequality removals remain withdrawn.
- **Gates:** The shared selector classified the production utility as shared
  and selected the full backend and all frontend groups. That broad local
  test run was stopped without claiming a pass; full-suite validation remains
  with CI. Ruff passed for both changed files, and the selector's mypy check
  passed over 834 source files. All 16 cases in the changed module passed
  under the shared gate lock, including after merging main at
  `f0449de3db08c710e5b2292a03910da157bcb498`. The post-merge Ruff check passed.
- **Negative proofs:** Three disposable production faults each failed the
  intended exact-output case: ignore the explicit request, ignore the detected
  processor count, and return zero when the processor count is absent. Imports
  were verified to use the disposable production copy. The new test against
  the frozen base failed collection because that base has no extracted
  resolver; this is not counted as a behavioral fault proof. Generated copies
  were removed, and the working implementation was not fault-injected.
- **Plan integration:** Verified and imported the complete frozen Row 14
  predecessor, 81,195 bytes, with SHA-256
  `a7af64af9b7b3261997ffbb0bf61d3efb7aed6b6c0ca01f32ba06ec02f4e043a`.
  Only D15 and this section were added. All earlier text, A5, D3 IN-FLIGHT,
  Rows 11-14 and the D10 merge receipt remain unchanged.
- **Delivery:** Implementation was delivered in
  [#1667](https://github.com/miztiik/yen-idhazh/pull/1667), merged at
  `956fd7e27cdcbc927bd86ce54ecede4f993779ef`. No new config, persisted shape,
  dependency, model choice, default or safety rule. Runtime behavior is
  preserved; no canonical utility documentation required a change.
- **Dependencies:** Row 1. The complete frozen successor releases the
  serialized editor to Row 16 before checks, push or CI.

## 17 - Row #16 - Bounded state CSV integrity checks

- **Scope:** Replace only the growing tracked-tree CSV scan with a real
  commit-range gate. Keep the registry grain/suffix and no-union-merge tests.
- **Authority and accepted cost:** kumarsnaveen, 2026-10-23 UTC, selected A1:
  add the bounded commit-range check. It rejects additions, modifications and
  rename-ins of lowercase `state/...csv`, at any depth. Deletes and rename-outs
  pass; matching remains case-sensitive. It does not inspect unchanged files.
  A manual dispatch without a base, a branch-creation push with an all-zero
  base, or a local invocation without endpoints visibly reports that no range
  check ran and no whole-tree integrity certification was made. Supplied
  invalid endpoints, a supplied base without a head, and unrelated histories
  fail closed. The canonical guarantee and ruling are in
  `docs/how-to/run-the-gates.md`.
- **Files touched:** `frontend/scripts/state-csv-guard.ts`,
  `frontend/scripts/tests/state-csv-guard.test.mjs`, `frontend/package.json`,
  `.github/workflows/ci.yml`,
  `backend/tests/contracts/test_no_csv_ledger_is_left.py`,
  `backend/tests/workflows/test_ci_selection.py`,
  `docs/how-to/run-the-gates.md` and this plan.
- **Implementation:** The independent CLI resolves commits and their merge
  base, then uses `git diff --name-only --no-renames --diff-filter=d -z`
  over that one range. The existing `scope` job runs it before selection,
  without a condition, swallowed failure or new CI job. The selector's broad
  full-test fallback cannot turn an integrity error into success. Existing
  tooling scripts type-check the guard and run its tests. No new dependency,
  framework, persisted inventory, fixture rewrite, skip or mock.
- **Identifier disposition:** Remove only
  `backend/tests/contracts/test_no_csv_ledger_is_left.py::test_no_csv_file_is_committed_under_state`
  and its dead `subprocess` import and `STATE_CSV` constant after the real
  replacement proof passes. Retain
  `backend/tests/contracts/test_no_csv_ledger_is_left.py::test_no_ledger_in_the_registry_files_csv`
  and
  `backend/tests/contracts/test_no_csv_ledger_is_left.py::test_no_path_takes_a_union_merge`.
  Add
  `backend/tests/workflows/test_ci_selection.py::test_state_csv_integrity_runs_before_selection_without_a_skip_or_fallback`
  to check unconditional wiring, actual event bindings and full history.
- **CLI proof:** The new named module runs 27 real-process cases in generated
  temporary Git repositories. Rejection cases cover added, nested, modified,
  renamed-in and quoted/spaced CSV paths. Acceptance cases cover deletes,
  rename-outs, outside-state and unchanged files, uppercase directories and
  suffixes, and other prefixes. Divergent histories prove use of the merge
  base. Refusal cases cover invalid/missing refs, option-shaped refs, zero
  heads, invalid dispatch heads, invalid/missing branch-creation heads,
  all-zero PR bases and histories without an ancestor. Three no-range cases
  assert the notice and absence of a pass claim. All 27 passed without skips.
  Exact case names and command receipts remain in the session report.
- **Independent faults:** In disposable copies, ignoring the CSV predicate
  made the added-CSV exit assertion fail (zero instead of one); removing the
  deletion filter made the delete acceptance fail (one instead of zero);
  returning success after an invalid base made the refusal exit assertion
  fail (zero instead of one). These were assertion failures in executed CLI
  tests, not collection errors. Generated copies were removed.
- **Local gates:** The shared selector selected backend, all frontend groups
  and tooling for the CI/script changes. Exact local coverage was the
  registered tooling suite (strict TypeScript check and 103 tests passed),
  the two retained Python checks (both passed), and the new workflow wiring
  test (passed). All 15 existing CI-selection cases passed in the initial
  module run. Ruff and whitespace checks passed. Mypy and final CI receipts
  are recorded in the running session report; full Linux CI is authoritative.
  No published-site behavior changed, so no browser smoke is required.
- **Plan integration:** Imported the complete frozen Row 15 predecessor,
  84,555 bytes, SHA-256
  `245fec63e996bd281be2bd305d97459c8319797cf93c9f749cfe53a19ada2f75`.
  Added only D16, this section and the expressly approved A5 CSV exception.
  All prior evidence, A5 exceptions and D3 IN-FLIGHT remain unchanged.
- **Delivery:** Implementation was delivered in
  [#1668](https://github.com/miztiik/yen-idhazh/pull/1668), merged at
  `cff5cc58c8cc15c59b5b525fca84335e2e88c4ce`. The worker did not merge it.
- **Dependencies:** Row 1.

## 18 - Row #17 - Default-on host-placement acquisition control

- **Scope:** Add the owner-approved default-on config setting that can stop
  Python placement metadata acquisition without stopping local machine
  measurements or ledger writes. Keep the real reader and its safety boundary.
- **Authority:** kumarsnaveen selected A1 on 2026-10-24 UTC. This row does not
  take the other council rewrites. The config value and the caller's explicit
  `ask_placement=False` choice both prevent placement acquisition.
- **Files touched:** `backend/idhazh/contracts/knobs/observability.py`,
  `backend/idhazh/telemetry/silicon.py`, `config/idhazh.json`,
  `backend/tests/contracts/test_app_config.py`,
  `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`,
  `backend/tests/test_silicon.py`, `backend/tests/_host_placement.py`,
  `backend/tests/council/_config.py`,
  `backend/tests/council/test_session.py`,
  `backend/tests/council/test_publication.py`,
  `docs/reference/host-metrics.md` and this plan.
- **Implementation:** The observability contract declares a `StrictBool`
  setting with a default of true, and the committed config states true
  explicitly. `silicon.file_machine_row` passes the caller's choice AND the
  config value to the real placement reader. There is no new CLI switch,
  environment value, persisted payload, migration, transport stub,
  dependency, destination change or broader telemetry redesign.
- **Behavior proofs:** Config tests cover default true, explicit true/false
  and invalid types. Real local collection proves config false and caller
  false each skip the actual placement function while still writing a
  populated machine row with its local UTC clock. A scoped `sys.setprofile`
  guard verifies that the default-on recorder reaches the actual placement
  function, then stops before URL use or network access. The two named council
  proofs are `backend/tests/council/test_session.py::test_settle_records_one_machine_for_the_night_not_for_each_judged_date`
  and `backend/tests/council/test_publication.py::test_many_tenants_and_later_dates_survive_a_failure`.
  They use config false with real local collection and preserve machine-row
  counts, identities, clocks, publication receipts and failure/sibling
  guarantees.
- **Independent faults:** Three planned production faults must fail for the
  intended evidence: ignoring config false, ignoring caller false, and
  disabling local machine collection when placement is off. The bounded
  runner restores the source after each fault. These proofs had not run at
  plan freeze.
- **Local gates at plan freeze:** The six focused config, silicon and council
  tests passed before the final nullable-clock assertion was added. Ruff and
  whitespace checks passed. Mypy found the optional timestamp use; the test
  now asserts the timestamp exists before parsing it, and the type check must
  be rerun. The independent fault proofs and the refreshed shared selector
  remain pending. CI on the merge candidate is authoritative. No published
  site behavior changed.
- **Plan integration:** Verified and imported the complete frozen Row 16
  predecessor, 89,674 bytes, SHA-256
  `9b79f8297e884665f4a77f0f0b6faedc6de97bac39a9a860e18fcda4019563be`.
  Added only D17, this section and the owner-approved A5 placement-setting
  exception. All prior rows, evidence, rulings, D3 IN-FLIGHT and D12 IN-FLIGHT
  remain unchanged.
- **Delivery:** One phase PR for coordinator review and merge. The worker does
  not merge the PR. The frozen full successor releases the serialized editor
  to Row 18 independently of remaining checks, push or CI.
- **Dependencies:** Row 12's real `ask_placement` forwarding API.

## 19 - Row #18 - Workflow checks reject supported broken inputs

- **Scope:** Repair the existing checks that pass broken workflow inputs.
  Keep the actual committed YAML as the subject, all live policy, historical
  evidence and trust checks. The fingerprint enum-forwarding finding F4 is
  reserved for its separate phase after Row 17.
- **Files touched:** `backend/tests/workflows/test_llm_council_workflow.py`,
  `backend/tests/workflows/test_weights_and_model_refs.py`,
  `backend/tests/workflows/test_bench_targets.py`,
  `backend/tests/workflows/test_pipeline_tests_workflow.py`,
  `backend/tests/workflows/test_gardener_workflow.py`,
  `backend/tests/workflows/test_model_server_jobs.py`,
  `backend/tests/workflows/_harness.py` and this plan. No production, config
  or workflow edits belong to this row.
- **Implementation:** Inspect structured timeout keys instead of a regex over
  a dictionary's printed form. Read supported dotted and literal-bracket
  Actions references inside wrappers and multiple-reference expressions.
  Inspect ordered simple shell commands for package installation before
  utility or module use, direct Git commit/push commands and literal write
  destinations. Detect literal committed config reads at supported CLI,
  shell and inline Python call sites. Require the actual raw-download and
  dossier-emission steps before checking their conditions. Resolve each
  launcher's exact config-root argument through the step environment or
  action input and default. No generic shell interpreter, new framework,
  dependency, mock, skip or network access is added.
- **Preserved checks:** Timeout source/output propagation, published-key and
  allowed-context rules, actual named utility imports, candidate action
  inputs and ordering, raw-case conditions, default-token scope, shard
  permissions, and downloaded/derived model-path equality remain active.
  No existing test identifier is removed.
- **Local evidence at freeze:** The six modules collect 258 cases against
  196 baseline cases: all 196 exact identifiers remain, with 62 controlled
  parameter cases added. The initial run passed 254 and failed four.
  Three failures were a relative interpreter import path; all three pass
  with the absolute checkout path. The fourth is the genuine timeout
  defect below. Ruff passes. The initial scoped type check found reuse
  of a local variable with a different type; this is corrected and the
  repeat is pending. Full CI is authoritative on the merge candidate.
- **Independent faults:** The nine original assertions passed unchanged
  YAML and all 13 disposable workflow fault cases. Eight repaired
  non-timeout assertions pass unchanged YAML and fail all 12 corresponding
  cases with assertion failures, not collection errors or skips. Cases
  cover wrapped published output, installation moved after use, module
  use before installation, a committed config-root read, removed raw
  download, removed dossier emission, Git global-option commit, tee into
  docs, wrapped and bracket personal secrets, direct shard push and the
  wrong digest action config root. Every disposable workflow's restored
  SHA-256 is verified; exact identifiers and JUnit receipts are in the
  worker's session report.
- **Finding and dependency:** F1 exposes literal 30-minute deadlines in
  `llm-council.yml`'s planning and collection jobs. Fowler ruled that the
  shard-timeout claim was narrower, but these are still tunable-policy
  defects under Guardrail 6. The coordinator assigned prerequisite Row 22
  to add a direct-consumer planning/collection timeout config and a small
  predecessor job that uses the existing bound reader. Row 22 keeps the
  whole-job deadlines and failure-safe collection. Row 18 does not waive
  this finding, hide the two jobs or ship a red candidate; integration and
  merge wait for Row 22. This row does not guess or implement that design.
- **Plan integration:** Verified and imported the complete frozen Row 17
  predecessor, 93,831 bytes, SHA-256
  `bba347d9985ed1e242a2e654d8a8fdf13bbece766a4f1657dbe5d081fbbdcde0`.
  Added only D18 and this section. All prior rows, A5 exceptions, D3 status
  and evidence remain unchanged. The full frozen successor releases the
  serialized editor to Row 19 independently of gates and CI.
- **Delivery:** One coherent PR, reviewed and merged by the coordinator.
  The worker opens it and does not merge.
- **Dependencies:** Row 1; Row 22 for integration and merge.

## 20 - Row #19 - Independent source-health publication proofs

- **Scope:** Make the existing publication proofs detect lost source evidence
  independently of the producer they compare. Strengthen only concrete
  false branches and contradicted claims in
  `backend/tests/test_publish_source_health.py`; no production, config,
  contract, fixture or published-policy change.
- **Implementation:** Explicitly select a configured active feed for real
  publication. Seed its actual endpoint health and item records through the
  ledger door. The written source must be answering with permission
  unrecorded and exact item counts. The three selected recorded dates must
  independently report six opportunities, three publications and three
  source-owned failures, not only match a reference build's bytes.
  The privacy case reads the real published file and excludes exact supplied
  addresses and keys as well as the existing forbidden field words.
- **Other concrete repairs:** Reverse two distinct permission answers;
  clear an old failure after a newer success; prove the configured rest
  threshold's two sides; distinguish an unrelated retirement key; refuse
  both retirement/date mismatches; actually include a robots denial in
  the no-evidence case; separate a partial discount from the reliability
  floor; include a thin source in the headline denominator; prove strict
  alarm and inclusive decision boundaries; arrange worst-yield order
  opposite to alphabetical and input order; deliver duplicate publication
  attempts directly to the fold rather than deduplicating them in setup.
- **Preserved guarantees:** Public path, configured-source census, return/file
  and complete-reference byte equality, complete UTC date edges, bounded
  selected-file reads, calendar-window contrast, ranker-factor parity,
  source-owned failure attribution, unreadable history, empty states,
  retirement/rest exclusions and published privacy all remain.
- **Inventory:** The actual base has 33 functions, not the brief's 31.
  All 33 survive: 14 strengthened and 19 KEEP. Six parameter cases are
  added, so the final expected collection is 43 rather than 37.
  No function is deleted or skipped. The one rename is
  `test_a_thin_record_is_never_named_however_bad_it_looks` to
  `test_the_alarm_requires_enough_decisions_and_a_yield_strictly_below_its_bar`.
  Exact identifiers, category assignments and KEEP reasons are in the
  worker's session report.
- **KEEP correction:** PSH-7,
  `test_the_record_says_it_is_too_short_rather_than_printing_a_rate`,
  stays unchanged. Its long input is already clipped to the configured
  minimum before the readability assertion, so it already proves that
  exact edge. The initial proposed parameter cases are not retained.
- **Evidence at plan freeze:** The initial 44-case control passed before
  the PSH-7 correction; that is not the final 43-case receipt.
  Disposable real-source faults have already exposed the two publication
  holes and an endpoint-key leak at the intended assertions, with passing
  restored controls. The remaining fault runs and final selected gate are
  pending. The copy contains only 184 actually consumed named source/config
  files, retains `pyproject.toml`, and verifies its import provenance.
  No setup/collection failure is accepted as negative evidence. Linux CI
  remains authoritative on the merge candidate.
- **Plan integration:** Verified and imported the complete frozen Row 18
  predecessor, 98,435 bytes, SHA-256
  `a4fe543dbb4f46aba16c0511cbfc1a8da4c10a2ce35a2155735a3776ebc654f3`.
  Added only D19 and this section. PR #1674 merged at
  `e7f46b2317852ea5d3f212f83ea86ac51edc05ed`; D19 is DONE. All earlier
  evidence, A5 exceptions, D3 IN-FLIGHT and Row 18's pending Row 22
  prerequisite remain unchanged.
  The complete frozen successor releases the serialized editor to Row 20
  independently of remaining gates, push or CI.
- **Delivery:** One coherent phase PR for coordinator review and merge.
  Implementation commit `d05dc235941ab15332a1e34bf33286184793860e` was
  delivered in [#1674](https://github.com/miztiik/yen-idhazh/pull/1674),
  merged 2026-10-24 at `10:04:18 UTC` as
  `e7f46b2317852ea5d3f212f83ea86ac51edc05ed`. Exact-head `scope`, `gates` and
  `site` checks passed; `robots` and `browser` were skipped.
- **Dependencies:** Row 1.

## 21 - Row #20 - Prove reader output behavior

- **Scope:** Strengthen only `backend/tests/test_leading_stories.py` and
  `backend/tests/test_render.py`. No production, config, contract, fixture,
  dependency or frontend changes.
- **Leading-story behavior:** Prove the configured block and desk caps, the
  one-publication, one-subject and yesterday limits, item-id tie breaking,
  freshness multiplication, null corroboration, and the block's configured
  subject floor. Snapshot the caller's populated list and model values before
  selection. Keep score-versus-input ordering, public-day preservation,
  eligibility, provenance, true reasons and historical reads. Exercise the
  12/13 wording edge with valid test-owned counts.
- **Visual behavior:** Reverse both channels in a valid plan and derive the
  expected marks from that plan and its table. Compare complete alt-text
  number tokens to the source values. Keep published-data, provenance,
  portability, output-failure and identity checks. Require the named no-picture
  refusal, assert authored title and caption do not enter data, validate the
  reserved item names through `ItemId`, set the test directory as the real
  working directory, and prove a rejected write leaves no output tree.
- **Evidence at freeze:** Against `c10fd2f03e90cad07fdd400cc55a72ef9042d2d8`,
  the two modules collected 70 cases across 66 test functions. The new
  freshness and weighted-signal cases add two functions; the count boundary
  adds one case; one test name is corrected. No behavior test is removed.
  The exact collected ids and source hashes are in the worker report.
  `npm run test:changed -- --list` selected exactly these two backend modules.
  The selected gate is queued on the shared gate lock; its result and the
  disposable production-fault proofs are pending and are not represented as
  passes. Fault copies must use the copied code and fail at the intended
  assertions.
- **Plan integration:** Verified and imported the complete frozen Row 19
  predecessor, 102,543 bytes, SHA-256
  `094f4dce4c63088201bc1120bbe9f58d5b69a837938c074962ee3bebf77eeaa7`.
  Added only D20 and this section. Earlier rows, A5, D3, and Row 18's pending
  Row 22 dependency remain unchanged. The complete frozen successor releases
  the serialized editor to Row 21 independently of local gates and CI.
- **Delivery:** Open one phase PR after plan integration. The worker does not
  merge it.
- **Dependencies:** Row 1.

## 22 - Row #21 - Prove ledger dates and named-plan reads

- **Scope:** Strengthen only `backend/tests/test_ledger.py` and
  `backend/tests/test_plan_status.py`. No production, config, contract, fixture
  or dependency changes. Do not change date meanings, accepted historical
  payloads or publication policy.
- **Ledger proofs:** `test_the_unbounded_cover_reads_one_held_month_at_a_time`
  derives each expected month's days with `calendar.monthrange` and `date`,
  independently of the production calendar helper, while retaining the
  one-held-month-at-a-time read bound. The fitted-row test uses distinct valid
  dates (`2026-09-18` fitted, `2026-09-17` covered), requires filing under the
  fitted day, and reads back the row and writer identity. The newest-day test
  explicitly names the generated dates (`2026-09-30`, `2026-10-01`,
  `2026-10-02`), requires only `2026-10-01` and `2026-10-02` in the two-day
  cover, and checks reliability using only those selected rows.
- **Named-plan proofs:** The relative-root test requires the generated
  `TODO/alpha.md` plan to be read with eleven populated rows and independent
  first/last row values before comparing relative and absolute roots. Rename
  `test_a_detached_worktree_is_never_asked_about_a_pull_request` to
  `test_a_detached_worktree_note_omits_pull_request_wording`: the tested
  guarantee is only that the note omits that wording. Do not add a pretend
  GitHub client or claim that the test proves no request was made.
- **Preserved guarantees:** Keep the 730-day cover/window safety, independent
  116-part capture counts, read behavior, telemetry privacy, literal boundary
  dates and real Git evidence. Do not alter the existing `FixedClock`
  stand-in or timestamp semantics; its structural replacement is separate
  work.
- **Inventory:** Five baseline identifiers were collected. Four remain
  unchanged; the detached-worktree note test is the sole rename. No test
  functions are added or removed. Baseline SHA-1 object IDs were
  `7879f3be43eded3350fc6a6be5c6cad79969cd2b` for `test_ledger.py` and
  `43218ab4d92db65e963eb590f5f72dafc1cc2d7c` for `test_plan_status.py`;
  resulting object IDs are `2312aab2e7fc587c7dd9a3be9ccf21bdb0e994de` and
  `9be52e6a5d199d3f3451cea4017512d615505eb5`, respectively.
- **Verification:** The shared selector record
  `backend/var/checks/44fa0b73b9c905debcf25aa8af6aa523cb6e9f7dbbedd04961092167d15a0131.json`
  records whitespace, Ruff, mypy and all 91 selected tests passing. Its source
  modules match the unchanged Row 21 commit blobs
  `2312aab2e7fc587c7dd9a3be9ccf21bdb0e994de` and
  `9be52e6a5d199d3f3451cea4017512d615505eb5`; therefore this evidence is
  reused for Row 21 without a repeat solely for main integration. Seven
  disposable production faults failed at their intended assertions, five
  controls passed before and after, and restored source hashes were verified.
  No full-suite run is claimed.
- **Plan integration:** Merged current `origin/main`
  `e7f46b2317852ea5d3f212f83ea86ac51edc05ed` normally. Preserved the current
  Row 11 section and verified receipts for Rows 11, 12, 14, 15, 16 and 19,
  along with all other phase sections, A5 and D3. The two Row 21 test-module
  blobs remain unchanged. The frozen historical Row 21 successor remains
  108,564 bytes with SHA-256
  `85bb171daf2a4e00cd4689817825e295d10ddd6a0638381698f1299d682cbca3`.
- **Delivery:** Delivered in
  [#1675](https://github.com/miztiik/yen-idhazh/pull/1675), merged at
  `31a689f073d602e75870f7fa48da72d3043f6c13`. Source commit
  `7950bf6825560734a28d0dcd1d57a7634a378ac2` remains unchanged;
  `test_ledger.py` ownership remains released. The worker did not merge it.
- **Dependencies:** Row 1.

## 23 - Row #22 - Configured council planning and collection job deadlines

- **Scope:** Move only the planning and collection operational budgets out of
  workflow literals into independent validated Actions configuration. Preserve
  both 30-minute total-job defaults, including checkout and installation; a
  step-only deadline is not an equivalent replacement.
- **Authority:** This is the production prerequisite uncovered by Row 18's
  corrected timeout proof, covered by kumarsnaveen's structural-expansion
  authorization on 2026-10-24 UTC. Fowler supplied the construction; the owner,
  not the advisor, authorized the scope expansion.
- **Files touched:** `.github/workflows/llm-council.yml`;
  `config/llm_council_job_timeouts.json` (new);
  `backend/tests/workflows/test_council_job_timeouts.py` (new);
  `backend/tests/workflows/test_llm_council_workflow.py` (three released
  compatibility assertions only); `backend/utilities/shard_bound.py`
  (descriptive docstring only);
  `docs/architecture/publishing/llm-council.md`; this plan.
- **Construction:** The `job_bounds` prerequisite checks out the workflow
  revision and runs the existing strict positive-integer reader with stock
  runner `python3`. It publishes separate planning and collection outputs.
  Each consumer directly needs that job and uses its own output through
  `fromJSON` at whole-job scope. No backend installation, model or tenant
  loading is needed. Repository-authored Actions config has no persisted
  payload version or migration.
- **Preserved guarantees:** Judging keeps its existing shard output and
  deadline. Collection still runs after planning or judging fails or is
  cancelled, but only after budget validation succeeds. Failed validation
  leaves the run red and cannot start planned work with missing deadlines.
- **Runtime cost and rationale:** One runner startup and checkout is added
  before planning. The prerequisite has no custom deadline and inherits the
  Actions 6-hour ceiling, at which GitHub kills the job. There is no new CI
  job, package dependency, destination or persisted shape. The existing
  council page owns this policy; it stays whole because the addition explains
  the same workflow clock.
- **Oracle:** The real reader and actual CLI preserve distinct nondefault
  planning and collection values and prove independent substitution. Missing
  keys and bool/string/float/zero/negative values fail with the named key.
  Tests follow the producer step, job output, direct dependency and
  `fromJSON` job deadline. Missing dependencies, swapped keys, self-step
  references, step-only deadlines, broken outputs and lost failure/cancellation
  collection must fail.
- **Inventory:** No existing test functions or identifiers are removed or
  renamed. Six new functions add 18 parameter cases. Only the collector's
  dependency assertion, job-level condition assertion and expected permissions
  map change in the existing council module, after Row 18's explicit source
  release. Row 18's checker and shared harness are not imported.
- **Evidence at freeze:** Source commit
  `55ab017f198b94f396553c348e9caf6f9768d261`; clean implementation tree before
  importing the plan. New module: 18 passed. Existing council module:
  43 passed. Collection: 61 cases, not a full-suite claim. Repository ruff
  and targeted mypy passed. The shared selector expands unknown workflow,
  config and utility inputs to all groups; only targeted gates run locally.
  Two generic producer/artifact controls remain queued under `gate_lock`.
- **Negative proof:** In a disposable base checkout with its own
  `pyproject.toml` and verified reader import, the new wiring cases fail for
  the absent direct dependency. Eight real YAML/config/reader faults fail at
  their intended assertions/refusals: missing dependency, swapped producer
  key, self-step timeout, absent whole-job timeout, wrong output, success-only
  collection, zero config budget and reader acceptance of zero. All 18
  unchanged controls pass before and after; source hashes restore exactly.
  Separately moving the timeout onto the actual planning step fails only
  the planning case; the collection case still passes. Both unchanged
  two-case controls pass before and after that edit.
- **Evidence identity:** Restored workflow SHA-256
  `bc8fd1e1d41bf9f68ca69846e37e8bb8e5afb1e0c9ea8a72a6bb0040ee2f7fc7`;
  new test
  `3fb5c7c718907300b4323a45eef43311c91f0325efaf2e0595ea808336a8e3a2`;
  config
  `76d0cf38d409fd360126612e54d0dcb9c5b59b999e5f075f798b514eba424ea0`;
  reader
  `6a6b72898f8830ce22e664e9396007856a6e027ad15b114c83a672bec319fc87`;
  three-assertion compatibility source
  `a4dc627dd45fb9da720f88c8482173ff6fc31672b75bf969ce8bc8b52b2c4f39`.
  Exact selected identifiers, changed-input hashes and fault logs are in the
  worker's session report; these are evidence, not new application artifacts.
- **Plan integration:** Verified and imported the exact full Row 21
  predecessor, 108,564 bytes, SHA-256
  `85bb171daf2a4e00cd4689817825e295d10ddd6a0638381698f1299d682cbca3`.
  Added only D22, this complete section and the approved A5 scope note.
  All earlier rows, earlier A5 exceptions and D3 remain intact. This complete
  successor releases the serialized editor independently of gates and CI.
- **Delivery:** Open an independently green phase PR after plan integration;
  the worker does not merge. Row 18 depends on this production fix, then
  integrates the new main wiring into its own checker work and reruns its
  changed-input proofs.
- **Dependencies:** Row 1.

## 21 - Row #20 - Prove reader output behavior

- **Scope:** Strengthen only `backend/tests/test_leading_stories.py` and
  `backend/tests/test_render.py`. No production, config, contract, fixture,
  dependency or frontend changes.
- **Leading-story behavior:** Prove the configured block and desk caps, the
  one-publication, one-subject and yesterday limits, item-id tie breaking,
  freshness multiplication, null corroboration, and the block's configured
  subject floor. Snapshot the caller's populated list and model values before
  selection. Keep score-versus-input ordering, public-day preservation,
  eligibility, provenance, true reasons and historical reads. Exercise the
  12/13 wording edge with valid test-owned counts.
- **Visual behavior:** Reverse both channels in a valid plan and derive the
  expected marks from that plan and its table. Compare complete alt-text
  number tokens to the source values. Keep published-data, provenance,
  portability, output-failure and identity checks. Require the named no-picture
  refusal, assert authored title and caption do not enter data, validate the
  reserved item names through `ItemId`, set the test directory as the real
  working directory, and prove a rejected write leaves no output tree.
- **Evidence at freeze:** Against `c10fd2f03e90cad07fdd400cc55a72ef9042d2d8`,
  the two modules collected 70 cases across 66 test functions. The new
  freshness and weighted-signal cases add two functions; the count boundary
  adds one case; one test name is corrected. No behavior test is removed.
  The exact collected ids and source hashes are in the worker report.
  `npm run test:changed -- --list` selected exactly these two backend modules.
  The selected gate is queued on the shared gate lock; its result and the
  disposable production-fault proofs are pending and are not represented as
  passes. Fault copies must use the copied code and fail at the intended
  assertions.
- **Plan integration:** Verified and imported the complete frozen Row 19
  predecessor, 102,543 bytes, SHA-256
  `094f4dce4c63088201bc1120bbe9f58d5b69a837938c074962ee3bebf77eeaa7`.
  Added only D20 and this section. Earlier rows, A5, D3, and Row 18's pending
  Row 22 dependency remain unchanged. The complete frozen successor releases
  the serialized editor to Row 21 independently of local gates and CI.
- **Delivery:** Open one phase PR after plan integration. The worker does not
  merge it.
- **Dependencies:** Row 1.

## 22 - Row #21 - Prove ledger dates and named-plan reads

- **Scope:** Strengthen only `backend/tests/test_ledger.py` and
  `backend/tests/test_plan_status.py`. No production, config, contract, fixture
  or dependency changes. Do not change date meanings, accepted historical
  payloads or publication policy.
- **Ledger proofs:** `test_the_unbounded_cover_reads_one_held_month_at_a_time`
  derives each expected month's days with `calendar.monthrange` and `date`,
  independently of the production calendar helper, while retaining the
  one-held-month-at-a-time read bound. The fitted-row test uses distinct valid
  dates (`2026-09-18` fitted, `2026-09-17` covered), requires filing under the
  fitted day, and reads back the row and writer identity. The newest-day test
  explicitly names the generated dates (`2026-09-30`, `2026-10-01`,
  `2026-10-02`), requires only `2026-10-01` and `2026-10-02` in the two-day
  cover, and checks reliability using only those selected rows.
- **Named-plan proofs:** The relative-root test requires the generated
  `TODO/alpha.md` plan to be read with eleven populated rows and independent
  first/last row values before comparing relative and absolute roots. Rename
  `test_a_detached_worktree_is_never_asked_about_a_pull_request` to
  `test_a_detached_worktree_note_omits_pull_request_wording`: the tested
  guarantee is only that the note omits that wording. Do not add a pretend
  GitHub client or claim that the test proves no request was made.
- **Preserved guarantees:** Keep the 730-day cover/window safety, independent
  116-part capture counts, read behavior, telemetry privacy, literal boundary
  dates and real Git evidence. Do not alter the existing `FixedClock`
  stand-in or timestamp semantics; its structural replacement is separate
  work.
- **Inventory:** Five baseline identifiers were collected. Four remain
  unchanged; the detached-worktree note test is the sole rename. No test
  functions are added or removed. Baseline SHA-1 object IDs were
  `7879f3be43eded3350fc6a6be5c6cad79969cd2b` for `test_ledger.py` and
  `43218ab4d92db65e963eb590f5f72dafc1cc2d7c` for `test_plan_status.py`;
  resulting object IDs are `2312aab2e7fc587c7dd9a3be9ccf21bdb0e994de` and
  `9be52e6a5d199d3f3451cea4017512d615505eb5`, respectively.
- **Verification:** The shared selector record
  `backend/var/checks/44fa0b73b9c905debcf25aa8af6aa523cb6e9f7dbbedd04961092167d15a0131.json`
  records whitespace, Ruff, mypy and all 91 selected tests passing. Its source
  modules match the unchanged Row 21 commit blobs
  `2312aab2e7fc587c7dd9a3be9ccf21bdb0e994de` and
  `9be52e6a5d199d3f3451cea4017512d615505eb5`; therefore this evidence is
  reused for Row 21 without a repeat solely for main integration. Seven
  disposable production faults failed at their intended assertions, five
  controls passed before and after, and restored source hashes were verified.
  No full-suite run is claimed.
- **Plan integration:** Merged current `origin/main`
  `e7f46b2317852ea5d3f212f83ea86ac51edc05ed` normally. Preserved the current
  Row 11 section and verified receipts for Rows 11, 12, 14, 15, 16 and 19,
  along with all other phase sections, A5 and D3. The two Row 21 test-module
  blobs remain unchanged. The frozen historical Row 21 successor remains
  108,564 bytes with SHA-256
  `85bb171daf2a4e00cd4689817825e295d10ddd6a0638381698f1299d682cbca3`.
- **Delivery:** Delivered in
  [#1675](https://github.com/miztiik/yen-idhazh/pull/1675), merged at
  `31a689f073d602e75870f7fa48da72d3043f6c13`. Source commit
  `7950bf6825560734a28d0dcd1d57a7634a378ac2` remains unchanged;
  `test_ledger.py` ownership remains released. The worker did not merge it.
- **Dependencies:** Row 1.

## 23 - Row #22 - Configured council planning and collection job deadlines

- **Scope:** Move only the planning and collection operational budgets out of
  workflow literals into independent validated Actions configuration. Preserve
  both 30-minute total-job defaults, including checkout and installation; a
  step-only deadline is not an equivalent replacement.
- **Authority:** This is the production prerequisite uncovered by Row 18's
  corrected timeout proof, covered by kumarsnaveen's structural-expansion
  authorization on 2026-10-24 UTC. Fowler supplied the construction; the owner,
  not the advisor, authorized the scope expansion.
- **Files touched:** `.github/workflows/llm-council.yml`;
  `config/llm_council_job_timeouts.json` (new);
  `backend/tests/workflows/test_council_job_timeouts.py` (new);
  `backend/tests/workflows/test_llm_council_workflow.py` (three released
  compatibility assertions only); `backend/utilities/shard_bound.py`
  (descriptive docstring only);
  `docs/architecture/publishing/llm-council.md`; this plan.
- **Construction:** The `job_bounds` prerequisite checks out the workflow
  revision and runs the existing strict positive-integer reader with stock
  runner `python3`. It publishes separate planning and collection outputs.
  Each consumer directly needs that job and uses its own output through
  `fromJSON` at whole-job scope. No backend installation, model or tenant
  loading is needed. Repository-authored Actions config has no persisted
  payload version or migration.
- **Preserved guarantees:** Judging keeps its existing shard output and
  deadline. Collection still runs after planning or judging fails or is
  cancelled, but only after budget validation succeeds. Failed validation
  leaves the run red and cannot start planned work with missing deadlines.
- **Runtime cost and rationale:** One runner startup and checkout is added
  before planning. The prerequisite has no custom deadline and inherits the
  Actions 6-hour ceiling, at which GitHub kills the job. There is no new CI
  job, package dependency, destination or persisted shape. The existing
  council page owns this policy; it stays whole because the addition explains
  the same workflow clock.
- **Oracle:** The real reader and actual CLI preserve distinct nondefault
  planning and collection values and prove independent substitution. Missing
  keys and bool/string/float/zero/negative values fail with the named key.
  Tests follow the producer step, job output, direct dependency and
  `fromJSON` job deadline. Missing dependencies, swapped keys, self-step
  references, step-only deadlines, broken outputs and lost failure/cancellation
  collection must fail.
- **Inventory:** No existing test functions or identifiers are removed or
  renamed. Six new functions add 18 parameter cases. Only the collector's
  dependency assertion, job-level condition assertion and expected permissions
  map change in the existing council module, after Row 18's explicit source
  release. Row 18's checker and shared harness are not imported.
- **Evidence at freeze:** Source commit
  `55ab017f198b94f396553c348e9caf6f9768d261`; clean implementation tree before
  importing the plan. New module: 18 passed. Existing council module:
  43 passed. Collection: 61 cases, not a full-suite claim. Repository ruff
  and targeted mypy passed. The shared selector expands unknown workflow,
  config and utility inputs to all groups; only targeted gates run locally.
  Two generic producer/artifact controls remain queued under `gate_lock`.
- **Negative proof:** In a disposable base checkout with its own
  `pyproject.toml` and verified reader import, the new wiring cases fail for
  the absent direct dependency. Eight real YAML/config/reader faults fail at
  their intended assertions/refusals: missing dependency, swapped producer
  key, self-step timeout, absent whole-job timeout, wrong output, success-only
  collection, zero config budget and reader acceptance of zero. All 18
  unchanged controls pass before and after; source hashes restore exactly.
  Separately moving the timeout onto the actual planning step fails only
  the planning case; the collection case still passes. Both unchanged
  two-case controls pass before and after that edit.
- **Evidence identity:** Restored workflow SHA-256
  `bc8fd1e1d41bf9f68ca69846e37e8bb8e5afb1e0c9ea8a72a6bb0040ee2f7fc7`;
  new test
  `3fb5c7c718907300b4323a45eef43311c91f0325efaf2e0595ea808336a8e3a2`;
  config
  `76d0cf38d409fd360126612e54d0dcb9c5b59b999e5f075f798b514eba424ea0`;
  reader
  `6a6b72898f8830ce22e664e9396007856a6e027ad15b114c83a672bec319fc87`;
  three-assertion compatibility source
  `a4dc627dd45fb9da720f88c8482173ff6fc31672b75bf969ce8bc8b52b2c4f39`.
  Exact selected identifiers, changed-input hashes and fault logs are in the
  worker's session report; these are evidence, not new application artifacts.
- **Plan integration:** Verified and imported the exact full Row 21
  predecessor, 108,564 bytes, SHA-256
  `85bb171daf2a4e00cd4689817825e295d10ddd6a0638381698f1299d682cbca3`.
  Added only D22, this complete section and the approved A5 scope note.
  All earlier rows, earlier A5 exceptions and D3 remain intact. This complete
  successor releases the serialized editor independently of gates and CI.
- **Delivery:** Open an independently green phase PR after plan integration;
  the worker does not merge. Row 18 depends on this production fix, then
  integrates the new main wiring into its own checker work and reruns its
  changed-input proofs.
- **Dependencies:** Row 1.

## 24 - Row #23 - Independent qualification and planning controls

- **Scope:** Strengthen only `backend/tests/test_qualify.py`, `test_plan.py`,
  `test_rank.py` and `test_discover.py`. No production, configuration, contract
  or fixture change; no test deletion or new dependency.
- **Qualification:** Count independently authored score, nonbrief and successful
  timed-decode populations for the actual diagnostic names. Rename the context
  size comparison accurately. Keep meaningful provenance assertions without
  adding incidental author, date or wording requirements.
- **Planning:** Distinguish final item count from the larger unbounded supply
  when deriving workers. Preserve the separate operator override. Assert exact
  authored supply, strongest cross-desk ceiling winners, ID tie handling and
  survivor order. The real article-limit integration uses no production ceiling
  helper as its expected answer. Keep future-date replacement and strengthen the
  existing source-quota safety test rather than duplicating it.
- **Quota finding:** A real quota-disabled production fault survives the
  original safety test: the live 24-hour age limit excludes its third lab story.
  The correction retains that safety identifier, proves at least three lab
  stories are eligible before the quota, and must reject the quota-disabled
  fault. The correction and its final source hashes remain pending at this
  plan freeze; no production defect is claimed.
- **Other controls:** Keep complete fresh-state repeatability under an accurate
  name; prove exact health-detail clipping and response-body exclusion at the
  plan record boundary. Require real round-robin input and complete alternating
  slices. Keep the real local encoder and refuse actual audited Python network
  attempts before I/O, including attempts whose refusal the encoder catches.
  Bind deliberately nondefault validated tier weights while retaining the
  original default ranking assertion.
- **No-loss mapping:** The temperature-named qualification case becomes
  `test_the_context_size_does_not_change_which_gates_are_asked`. The no-crowding
  planning case becomes `test_fresh_state_roots_produce_the_same_plan_items`.
  All other identifiers remain. Original inventory: 261 functions and 311
  collected cases. Row 4's removed fixture-only test remains absent.
- **Evidence at freeze:** Implementation commit
  `6cf996e54438d230e454fafdb47db8887cc45430` precedes the quota correction.
  The four-module run passed 311 cases without skips or errors. Its final
  six-attempt diagnostic refinement passed the 15-case copied-tree control,
  whose source hashes match that commit. Ruff and the four-file type check
  passed; an exact-final qualification type check remains queued. Sixteen
  copied-production faults failed their intended assertions without collection
  errors or skips and restored their hashes. Remaining faults, final controls
  and corrected-source gates are pending. Full-suite CI is not claimed.
- **Evidence files:** The worker session report `row23-report.md` and frozen
  `row23-original.json`, `row23-original-ids.json`,
  `row23-source-reconciliation.json` and `row23-proof-results-initial.json`
  record original IDs, hashes, decisions and partial proof outcomes. These are
  session evidence, not new application payloads.
- **Plan integration:** Imported the exact full Row 22 predecessor, 114,623
  bytes, SHA-256
  `83e5d49bc3dd2aa6c885b129971c2d713ee6cda2aaf046754df2d6b67586752c`.
  Added only D23 and this section. A5, D3, every earlier row and the single
  latest Row 11 correction receipt remain unchanged. Release the full successor
  to Row 24 immediately; remaining gates do not hold the serialized editor.
- **Delivery:** Open the phase PR after the final source and evidence are
  ready. The worker does not merge it.
- **Dependencies:** Row 1.

## 25 - Row #24 - Independent council test controls

- **Scope:** Strengthen the remaining council behavior tests in
  `backend/tests/council/`: `test_council_matrix.py`,
  `test_council_runs_without_a_judge.py`, `test_lifecycle.py`,
  `test_night_plan.py`, `test_selection.py` and `test_session.py`. The shared
  test helper `_config.py` explicitly preserves the real host collection
  controls. No production, config, contract, fixture or dependency change; no
  test is deleted, added or renamed. Existing committed tenant slug resolution,
  lifecycle records, workflow bindings, clocks and safety defaults remain real
  executable inputs.
- **Finding map:** Row 17 already repaired findings 7 and 9. Keep both test
  bodies unchanged; their source hashes are identical to the Row 17 base.
  Rewrite the other nine findings in place. The source hashes below cover each
  complete function including decorators. The exact Row 17 function bytes and
  hashes are retained in `row24-baseline-functions.json` in the session report.

Table E - Finding identity and exact source hashes

| ID | Finding and disposition | Original -> survivor pytest identifier | Row 17 base SHA-256 | Row 24 SHA-256 |
| --- | --- | --- | --- | --- |
| E1 | 1 - REWRITE | `test_council_matrix.py::test_a_cell_carries_the_tenant_the_date_the_shard_and_that_tenants_width` -> same | `e2925cdd746c1c09306054c2c66186bfd6b76f6e97f24ce9c24d9525546103a1` | `6c45bb1652ac6575c41ccb7e52f6e9aa65680cb05d5b5559712bc4054ac450e2` |
| E2 | 2 - REWRITE | `test_council_matrix.py::test_a_second_date_adds_cells_rather_than_a_third_axis` -> same | `15b32ee166f9501765fb0f3afc165e9ab437e1d8c1cce226e32e94e38b5d3dd8` | `9f89f49b7f5c0b38c475e1ff25c0106fb4ce75172e1b49b7cc220f80e945ca15` |
| E3 | 3 - REWRITE | `test_council_runs_without_a_judge.py::test_two_tenants_union_their_nights_and_keep_their_own_width` -> same | `9e93b890484348302bcb80d57b4d8fbb734ef0e79f7986aaecddc463c2a95463` | `8cc1a6e082f5700ae42ea53588440ae921ebf50ac11a3bbde86ca65f28ba0394` |
| E4 | 4 - REWRITE | `test_council_runs_without_a_judge.py::test_the_venue_runs_a_shard_under_its_own_clock_and_files_the_row` -> same | `0bc2e3bc43bfddc72b15e6449df99b90ff375bfb228e105af53b684edbd7a70b` | `6ad60f4800effc63725a4555c47d7389fe36d2cd3d6f14b015e50e236183ae7f` |
| E5 | 5 - REWRITE | `test_lifecycle.py::test_only_active_judges_get_cells_work_and_publication_paths[True]`, `[False]` -> same two cases | `55e17740b7fe032fae17fed94b432a184f193785b25c0196bc5effc18dd1b7f3` | `a6ebfed157f8188b17f26dff986de119a324c46e9cee343c9b07fbe546f089fa` |
| E6 | 6 - REWRITE | `test_night_plan.py::test_the_plan_is_the_union_of_what_the_tenants_owe_newest_first` -> same | `f0ee98baec42c9c6346a9affaa4efebf8c88d1f88a26820a82d7bab78dd519c1` | `530af08ae2439b89cac2d1b4a247312e9f23dfb51a0ee96420cf593e54f81902` |
| E7 | 7 - KEEP (Row 17) | `test_publication.py::test_many_tenants_and_later_dates_survive_a_failure` -> same | `13888090c72039c187755aee5d43ab58c8939db80f3c107487cc7df5204b9c5f` | `13888090c72039c187755aee5d43ab58c8939db80f3c107487cc7df5204b9c5f` |
| E8 | 8 - REWRITE | `test_selection.py::test_each_judge_has_its_own_repair_cap` -> same | `1106e4d1f43db96e3768cfd8d7e19516be82550d72f840efb07d3f2cf704e11a` | `da4843af090a852665040627ea2e6c7f9baf37ee04718992ba2f8af214953f54` |
| E9 | 9 - KEEP (Row 17) | `test_session.py::test_settle_records_one_machine_for_the_night_not_for_each_judged_date` -> same | `c6394e5cc24d348800578beaea53b4a8279791b94cce6081bf256d8af0f8cdf3` | `c6394e5cc24d348800578beaea53b4a8279791b94cce6081bf256d8af0f8cdf3` |
| E10 | 10 - REWRITE | `test_session.py::test_a_unit_that_raised_files_one_failed_row_beside_its_completed_siblings` -> same | `8921b00fa4e8f6f298fce1d13bf8d1bd126d0f2f1ec3cb58a3eea522373dab2a` | `bb3bfb4440b89cfb360d5fa8b1dee37626aa8375003d9465ea5b67ff9ecb92b3` |
| E11 | 11 - REWRITE | `test_session.py::test_the_saving_job_files_one_date_and_a_rerun_replaces_its_rows` -> same | `90959eb84db4bb78d59bafd5cb1a0f13954dc4c896b84a02d643c034376b2dd7` | `41146c8a2fad6ae5051ffebb4674754c2baffa4ef773ff18d79a53fc83d12990` |

- **Independent controls and expected results:** These are authored in each
  copied config and read through the real council loader, except where the
  named committed tenant ledger or workflow input is the behavior under test.

Table F - Controls, expected behavior and rejected faults

| ID | Input -> expected behavior; fault the test must reject |
| --- | --- |
| F1 | Council shard ceiling 3; tenant width 2; date `2026-09-20` -> exactly shards 0 and 1, each carrying `shards: 2`, `runs_model: false`, the tenant and date; committed paths include the tenant's path. Reject using the council ceiling as tenant width. |
| F2 | Ceiling 3; tenant width 2; dates `2026-09-20`, `2026-09-19` -> the exact four flat cells (two per date), preserving tenant width. Reject a ceiling-driven width or a third Cartesian axis. |
| F3 | Council first night `2026-09-24`, repair window 6 nights, repair cap 3, ceiling 5; tenants owe `2026-09-25` (width 2) and `2026-09-25`, `2026-09-24`, `2026-09-23` (width 3); tonight `2026-09-26` -> newest-first union: first tenant `26,25`; second `26,25,24`; widths 2 and 3. Reject shipped-default dependence, loss of union/order, or a shared width. |
| F4 | Ceiling 3; tenant width 2; actual council clock and real venue rows -> two shards each receive a deadline later than the recorded start; settlement records selection, two work parts and combination. Reject a substituted fixed clock, a ceiling-used-as-width, or missing real rows. |
| F5 | Room ceiling 3; active tenant width 2; paused and retired tenants retained in copied lifecycle config -> only the active tenant gets two cells, is loaded, prepared, run and settled, and writes its four expected rows and committed path. Reject inactive execution or ceiling-used-as-width; preserve the real status and workflow inputs. |
| F6 | First night `2026-09-24`, window 6, repair cap 3; one tenant owes `25`, another owes `25,24,23`; tonight `26` -> `[26,25,24]`, newest first, with `23` excluded by first night. Reject dependence on shipped dates or failure to form the union. |
| F7 | Preserve Row 17's real machine collection: telemetry and fingerprint enabled, bandwidth jobs empty, placement acquisition disabled only in this copied config. Three tenants, dates `2026-10-08` and `2026-10-09`, one tenant raises -> all six output files complete, six rows with exactly one raised failure, later-date rows survive, and one local machine row remains with zero memory probe. Reject lost later-date output, lost failure isolation, or disabling machine collection to avoid host metadata. |
| F8 | First night `2026-10-01`, window 6, per-tenant repair cap 2; tonight `2026-10-10`; first tenant owes `09,08`, second owes `07,06` -> first gets `10,09`, second gets `10,07`; model flags remain `false,false,true,true`. Reject a cap shared across tenants or dependence on the shipped cap/window. |
| F9 | Preserve Row 17's real machine collection and disable only placement acquisition in the copied config; settle the same run for `2026-09-20` and `2026-09-19` -> one machine row for the run night, job unset, task `save_council_results`, memory probe zero, and measured instant present. Reject one machine row per judged date or disabling local collection. |
| F10 | Council ceiling 5; tenant width 4; work part 2 raises -> four work rows plus selection and combination; exactly part 2 is failed with `fault: raised` and null model/token costs, while its three siblings complete. Reject ceiling-used-as-width or invented cost on failure. |
| F11 | Council ceiling 3; tenant width 2; same date saved at attempts 1 and 2 -> two physical attempts retained, current settlement contains only attempt 2 and exactly selection, two work parts and combination. Reject appending the first attempt as current output or changing row identity fields. |

- **Evidence at freeze:** The Row 17 source base is
  `9cf4b204a311a9333cc2b84b067a36b90922f3f1`. Ruff passed on the seven
  council test modules. The seven-module selector remains queued behind the
  shared `gate_lock`; it has not started. Full `python -m mypy` remains in
  progress. No fault demonstration or passing test result is claimed here.
  Keep the queued selector and type check; do not bypass the gate or repeat an
  unchanged selector. Row 17's publication and settle proofs remain its
  responsibility unless their consumed hashes and results are supplied.
- **Plan integration:** Imported the exact released Row 23 predecessor,
  118,619 bytes, SHA-256
  `78f4022d614719552f6bb0f4f5e0033bebf4a20bc2219324f0a85938b45d52d5`.
  Added only D24 and this section. A5, D3, all earlier row sections and all
  complete Row 19-23 sections remain intact. This full successor is frozen and
  released independently of gates and delivery.
- **Delivery:** Row 17 is the source dependency and has not yet merged. After
  its merge, verify the GitHub merge receipt and equivalent source changes,
  merge current `main` normally into this branch, then open the Row 24 phase
  PR. Do not merge the Row 24 PR.
- **Dependencies:** Row 17; Row 23 is the required exact plan predecessor, not
  a gate dependency.

## 26 - Row #25 - Concrete remaining gardener and ledger safety proofs

- **Scope:** Strengthen only the nine approved test files:
  `backend/tests/gardener/test_schedule.py`, `test_report.py`,
  `test_error_cause.py`, `test_github_trees.py`,
  `backend/tests/ledger/test_day_removal.py`, `test_lifecycle.py`,
  `test_arrow_schema.py`, and `backend/tests/retention/test_visual_pruning.py`,
  `test_prune_range.py`. No production, config, contract, policy, fixture or
  dependency change. No test is deleted. Preserve every historical removal,
  window and destructive-default pin.
- **Disposition rule:** Keep the existing safety behavior. Rewrite weak
  assertions with independent inputs and observable outcomes; rename only where
  the old name claimed behavior the function does not provide. Do not add
  source-text proxies, call spies, fake sinks, skips or success-shaped fallbacks.

Table G - Finding identity and exact source hashes

| ID | Finding and disposition | Original -> survivor pytest identifier | Original function SHA-256 | Row 25 function SHA-256 |
| --- | --- | --- | --- | --- |
| G1 | S1 - REWRITE | new -> `test_schedule.py::test_non_utc_instants_use_the_utc_day_at_the_eligibility_boundary`; new -> `test_non_utc_instants_use_the_utc_month_at_the_eligibility_boundary` | - | `bc88b797bea0f4db18cb83c4ad2069973a6c6c7b25be853705e38bd11818fa77`; `95284130e40736c6bada5cef581c0230c9cb97296ac8449eaaba17f3e5956869` |
| G2 | R1 - REWRITE and rename | `test_report.py::test_no_sentence_a_task_can_be_told_says_a_member_is_gone` -> `test_guidance_and_recovery_notes_make_no_completed_removal_claim` | `fd4fb35a48e0be1b3633de93d93f9724c798f81f7dd69cf3a7cbd274d49b234d` | `f1e289edbf8b62ec47d77aecafd899db030890ae29b6f1613b37695bc38954a8` |
| G3 | R2 - REWRITE | `test_report.py::test_every_word_a_record_or_a_line_can_hold_has_a_sentence_a_person_reads` -> same | `20b6214c71d3f3a5327c1f801a8b9f5fd58c41dfabc033f4880c80b7ff450c2b` | `fd2d01317fae7563ce906dcf6b8860d7cdfa6b099caa6d85916d1fbbd5e97723` |
| G4 | E1 - REWRITE | `test_error_cause.py::test_a_403_is_unavailable_only_when_headers_prove_exhaustion` -> same | `c3f7cddd2aacc57df8c30ee02f5f1f67bbea24090c16affd229b9e69ea7e30d9` | `39e2d1823404341389686db489e89142f642db49c20f0471354fcf6c327ac6f6` |
| G5 | D1 - REWRITE | `test_day_removal.py::test_a_day_that_is_not_a_utc_day_is_refused_before_a_file_is_read` -> same | `8f9a1a30a261b507aa38caaa4c501802cf084dfba660a9e310a7a4527d078de1` | `37f6693439929bcac816a4a14a073149898ede5aa70833170e6d9124eb9bd04c` |
| G6 | L1 - REWRITE | `test_lifecycle.py::test_every_checked_route_writes_into_an_active_family`; `test_every_checked_route_writes_nothing_into_a_paused_family_and_says_so_once` -> same | `61c790f03b837784082345dbffb9910825a3bce1be5c3eb925d75388a9777d3f`; `0d62f054f49cc2a410150c6b11639ba02bfa27006afaabf82d4701045a5deb2f` | `9ca489ae10fa4d60fae0d0560f2c58e9ec089b4f7185742d4a6f2c1cc9c3037f`; `5b61bc4aac178b6a64e2f12ecbeae5494630f4bcc442855de9ccb737f5d52e8b` |
| G7 | A1 - REWRITE and rename | `test_arrow_schema.py::test_ledger_engines_and_door_have_no_run_plan_special_case` -> `test_run_plan_values_round_trip_through_each_generic_ledger_engine` | `27164426e4b9a151e7e15dff6e070965c6afdcfb7acfa8b7b8d33cf5f7fb05b2` | `6628fffcffd7cf9de9c4fe8c151f7da63d4e9ddf2330d78bfd2fae30d96736dd` |
| G8 | V2 - RENAME | `test_visual_pruning.py::test_a_name_inside_the_dated_tree_that_is_not_a_date_is_a_fault` -> `test_a_year_level_sibling_does_not_change_a_named_day_visual_list` | `e358047a842a553a08ee5055bdeeaa4424511a65c8bf24912a612813c17cb025` | `fcc5524760dab22eed04a702b14503446ea3385e628ad4886148e765d9e05416` |
| G9 | G1 - REWRITE and rename | `test_github_trees.py::test_many_named_period_paths_are_split_before_git_is_called` -> `test_named_members_survive_pathspec_batches_larger_than_the_process_limit` | `b961aface02b91d61bf4011fd6cba81d12c4ca8a16190d16ff86027696adb1fd` | `bff597f8e7d0ea478353d567ed8de6bdb8650048f9229365be9eae76a828c939` |
| G10 | PRUNE-REAL-FAILURE - REWRITE | `test_prune_range.py::test_a_pass_on_the_door_that_fails_part_way_names_what_changed_and_is_run_again` -> same | `d6caf6d9dc7f21ec74106234e4bc46c955e8828f90acb8e97a7a6b827fc1fa7d` | `62bd414e60facd82c842801b66397ce85e735f471916415222a35eae38abf7b5` |
| G11 | PRUNE-BEFORE-READ - REWRITE docstrings only | `test_prune_range.py::test_the_eval_ledger_is_refused_with_the_sentence_its_declaration_gives`; `test_a_live_pass_on_the_door_is_refused_without_a_writer_it_can_name` -> same | `dddcf421d92ee167bfb70c641e8b3cf11e3f617a7d345320c9539ff37cf4c623`; `a497040e365d43d0b9d2da5beae78cb5bb5c089277a0fb9e3f247a693bbe3599` | `9c19cf306892be83cb6ba5df33eab241bfad77621fddeff1da2d818eb293b907`; `f1ea5e99a18275585c19fcada787ef203117a922d3db1f44e2a28b9e6e742771` |

Table H - Independent controls and expected behavior

| ID | Finding | Control and independent oracle |
| --- | --- | --- |
| H1 | S1 | Supply `+05:30` instants at 2026-09-26 05:29:59 and 05:30, where local date is unchanged and UTC date crosses midnight. Expect the newest eligible day to change from 2026-09-23 to 2026-09-24. Supply 2026-10-16 05:29:59 and 05:30 at 45 days; expect newest month to change from 2026-07 to 2026-08. Expected UTC dates are literals, not production calendar helpers. Existing midnight and year-rollover proofs remain. |
| H2 | R1 | Check guidance and recovery notes separately with a narrow completed-removal-claim pattern. A dry, failed or deferred outcome cannot state that a member, file, day or period has already been removed. Neutral next-step guidance remains allowed. |
| H3 | R2 | Retain exact key-set coverage for every `TaskOutcome`, `GardenerFault` and `RecoveryNote`; require every associated sentence value to be a nonblank string. |
| H4 | E1 | Build real standard-library `HTTPError` responses with canonical, lowercase and mixed-case 403 headers. Assert exact `ErrorCause`; do not parse header values or use a successful fake HTTP client. |
| H5 | D1 | Use a regular file as the state root with invalid UTC-day strings. The invalid-day `ValueError` must win; attempting the state-directory read first produces a distinct filesystem error. Keep valid-day missing-index refusals. |
| H6 | L1 | Redirect the actual trace sink root to test-owned state, explicitly enable tracing, open a real deterministic span, and assert the persisted JSON record. The paused-family case still expects its one warning and no file. Other lifecycle routes and their paused controls remain. |
| H7 | A1 | Read the named `RunPlan` contract fixture, pass nested values through the generic parquet and JSON-lines render/read engines, and validate the recovered rows against the same contract. Do not claim that the ledger door accepts `RunPlan`. |
| H8 | V2 | Add a non-date file beside, not inside, the named year/day tree. The exact visual list for the named day remains unchanged. Keep malformed selected-path refusals; do not assert that an unselected sibling must fault. |
| H9 | G1 | Put two real named members in a disposable Git origin, then supply pathspecs whose ASCII byte total exceeds the host's argument limit. Assert the exact member names and byte sizes returned by Git. No call spy, empty-origin success or invented Linux threshold. |
| H10 | PRUNE-REAL-FAILURE | Select March 3-5, assert the dry-run plan has exactly two raw deletes followed by a compact rewrite, then make the real target write fail: Windows denies delete sharing on the selected file; POSIX limits file size to zero with `SIGXFSZ` ignored. Require the real `OSError` cause, exactly the planned deletes in `so_far.taken`, no completed writes, `failed`/`raised`, `resume_from` at March 3, no additional changes, and restart equality with an uninterrupted run. |
| H11 | PRUNE-BEFORE-READ | Narrow only two test docstrings from unsupported no-read claims to the verified unchanged-tree result. Keep their before/after fingerprints and all refusal and dry-run assertions; do not weaken any separately established read-boundary contract. |

- **Evidence at freeze:** The original selected identifiers and nine original
  file hashes are recorded in
  `row25-baseline-test-identifiers.txt` and the session report. The source
  changes are complete and limited to the approved test files. The shared
  changed-test selector is queued for its backend, Ruff, mypy and selected
  pytest checks. No gate result or disposable production-fault result is
  claimed at this freeze.
- **Plan integration:** Imported the exact released Row 24 predecessor,
  127,951 bytes, SHA-256
  `68009a5cd5e05c3867abc8340802bd13f180510b36f72edf8ece6fb2ec3ca73c`.
  Added only D25 and this section. A5, D3 and every earlier row section remain
  intact. This full Row 25 successor is frozen and released independently of
  gates and delivery.
- **Delivery:** Open one coherent phase PR when the source and evidence are
  ready. Do not merge it. Row 26 consumes this exact frozen successor.
- **Dependencies:** Row 24 is the required exact plan predecessor and row
  dependency; it is not a gate dependency.


## 27 - Row #26 - Prove time boundaries without stand-ins

- **Scope:** Replace only the existing `FixedClock` case and its dead imports
  in `backend/tests/test_ledger.py`; correct only the measurement-date default
  in `backend/utilities/measure_budgets.py`; add the focused
  `backend/tests/test_measurement_date.py`; document the default and override
  in `docs/reference/pipeline-cost.md`. No persisted shape, identifier
  algorithm, model, destination, config or runner-policy change.
- **Source prerequisite:** Started at Row 21's released source
  `7950bf6825560734a28d0dcd1d57a7634a378ac2` and verified it is an ancestor.
  Row 21 released `backend/tests/test_ledger.py`; its other controls remain
  unchanged. Do not amend or push its branch.
- **Original controlled identifier:**
  `backend/tests/test_ledger.py::test_a_second_attempt_replaces_its_first_and_another_run_is_kept`
  retains its name and exact run identities. The original module SHA-256 is
  `21b3a486416c6d59bb652ef5905e4e248fa453607034592bb271e6a44dfc4fc8`.
  The original measurement utility SHA-256 is
  `a2582d4b7ea095feaef6501001e35d2a35efef67ab71d1fbe6e57ec3fba7c2cb`.

Table I - Independent controls and expected faults

| ID | Control | Independent expected behavior | Disposable production fault |
| --- | --- | --- | --- |
| I1 | Three typed raw files rendered by the native ledger renderer, with valid row identities and one explicit `written_at_ms` | Run `2026-09-07-1` keeps attempt 2 with 200 bytes before cleanup; run `2026-09-07-2` remains with 300 bytes. All three files share one millisecond. Existing real producer-write cases remain separate. | Keep the lower rather than highest attempt in the copied production reader; the original named test must fail its value assertion. |
| I2 | Actual aware instants `2027-01-01T00:30:00+02:00` and `2026-12-31T23:30:00-02:00` | Default measurement dates are respectively `2026-12-31` and `2027-01-01`, independent of the machine timezone. A parsed `--taken-on 2026-06-15` stays that date. A naive instant is refused. | Drop UTC conversion or ignore the operator date in the copied utility; the corresponding date assertion must fail. |
| I3 | Real `main`/`read` execution observed with `sys.setprofile`, stopped at actual `Tokenizer.__init__` entry before its body | The resolver runs once with an actual aware UTC clock reading bounded by the test's real readings. The real stamp uses its returned date, including the parsed operator override. No token response, clock or successful measurement is replaced. | Remove the resolver call, supply a naive clock or request a local clock at the real callsite; binding assertions must fail before tokenizer I/O. |

- **Evidence at freeze:** Byte-identical copies of the two original named
  modules collected 61 cases under the default five-seat gate lock. The final
  named collection must retain all 61 and add the six focused date cases.
  Source commit `a27974fd914dc6c6456789a8f57b17f25a2ee805` is pushed;
  the real-callsite binding correction is being committed separately.
  Ruff passed after the clock removal and after the binding correction.
  Mypy reported no issues in the three initially changed Python files.
  Final controls, binding type checks and copied production fault proofs
  remain pending. No passing test or fault result is claimed by this freeze.
- **Plan integration:** Imported the exact released Row 25 predecessor,
  137,147 bytes, SHA-256
  `01b4131df8482f86ec00f350a98ad157691dbee642fee71ad1c013a2a825c7d7`.
  Add only D26 and this section; verify removing those additions restores
  every predecessor byte. Preserve A5, D3 IN-FLIGHT, one D11 row, every
  earlier complete section and receipt. Freeze and release the full
  successor for Row 27 independently of gates.
- **Delivery:** After Row 21 is merged, verify its merge and source
  equivalence, merge current `main` normally, retain newer complete
  canonical sections and receipts, and open one coherent phase PR.
  Do not merge the Row 26 PR.
- **Dependencies:** Row 21 owns the source prerequisite; Row 25 is the
  exact full-plan predecessor. Neither plan freeze waits for gates.

## 28 - Row #27 - Explicit offline gardener collection controls

- **Scope:** Change only `backend/tests/gardener/_garden.py` and
  `backend/tests/gardener/test_runner.py`. The copied test config explicitly
  enables master host telemetry and local fingerprint collection, selects an
  empty bandwidth job list, and disables external placement through Row 17's
  approved setting. The real `config.load_gardener` validates these controls.
  No production default, persisted payload, collection implementation, task
  declaration, lifecycle, retention rule or policy changes.
- **Source prerequisite:** Verified Row 17 commit
  `9cf4b204a311a9333cc2b84b067a36b90922f3f1` is the starting HEAD and ancestor.
  Preserve all its production, schema, test and documentation changes without
  modifying its branch. Row 17's living rule already states that placement-off
  retains local collection in `docs/reference/host-metrics.md`; reuse that
  rule rather than restating it in a second canonical page.
- **Original controlled identifiers:** Retain
  `backend/tests/gardener/test_runner.py::test_a_shard_records_the_machine_it_drew_and_names_it_among_its_writes[local]`,
  the same identifier with `[pushed]`, and
  `backend/tests/gardener/test_runner.py::test_a_shard_uses_its_loaded_fingerprint_switch`.
  Original SHA-256 values are
  `a4db5015b22da1ee211cf75788d22849c3fdba41caa30bd95d315376b5a5637a`
  for `_garden.py` and
  `348e6bd7dbbfb49f2c3e8fe903758776ceab9a72bfa310d14656eb82a86cd78a`
  for `test_runner.py`. The session preserves the original files and function
  identifiers. No test is deleted or renamed.
- **Behavior evidence:** All three focused cases passed with real collection.
  Each positive case wrote two actual Parquet files, 12,487 and 12,584 bytes,
  and one settled host row. The row retains `job=None`, pipeline `gardener`,
  task `run-tasks`, run `2026-09-27-18012345678`, attempt 1, zero bandwidth
  buffer, absent bandwidth rate, absent placement and `job_seconds=0` from the
  unchanged scripted clock. The local measurement timestamp is populated.
  The exact raw-file set equals the declared host write set; pushed bytes are
  read back from the real bare origin and match the checkout. The local-only
  case publishes none. The loaded fingerprint-off case produces no host files
  or rows. Actual Linux-only CPU fields stay unavailable on this Windows
  machine; no readings are invented and no Linux collection claim is made.
- **Independent fault:** In a disposable copy of the actual production code,
  remove both checks of the loaded `host_fingerprint` control from the machine
  and elapsed-time writers. The original negative-control identifier fails
  its host write-set assertion, with one intended failure and no collection
  errors. The runner verifies the imported `silicon.py` belongs to the copy.
  Restore production code: all three focused cases pass. Set the copied
  shipped defaults to master-off, fingerprint-off and bandwidth selected for
  `run-tasks`: all three still pass because the test-owned config chooses its
  own controls. The disposable runner restores both code and config. No
  collector spy, fake OS probe, replacement placement reader, network request
  or substituted production implementation is used.
- **Local gates at freeze:** Ruff passed over the repository. Mypy passed over
  835 source files. Whitespace checks passed. The shared selector against the
  fixed Row 17 base selects full backend and frontend coverage because the
  fixture helper is shared. Per the gate guide, a bounded named run of the
  gardener runner, publisher, sparse shard, registry, shard planner, download
  ceiling, shared publisher, corpus history, CLI, summary, trees, collection,
  names-only and yearly-expiry modules is still running. No result is claimed
  for that run or for CI. The full merge-candidate suite remains authoritative
  in CI; no published-site behavior changed.
- **Frozen source:** `_garden.py` SHA-256
  `33e79d590f4afd18116993c98264b56b65e49ae1962a1389241647e9c4022ca5`;
  `test_runner.py` SHA-256
  `ddf22cc620c300434686a0a81f2154801d5e89dd33122de6f961f324bb88375b`.
  The source-writing slot is released independently of gates and plan handoff.
- **Plan integration:** Imported the exact released Row 26 full predecessor,
  141,434 bytes, SHA-256
  `d969aaf615469d8b84e3298d861332428346aa9f5d706bea0a96d83acb54c833`.
  Add only D27 and this section. Removing those additions must reconstruct
  every predecessor byte, including A5, D3 IN-FLIGHT, the single D11 row and
  every earlier complete section and receipt. Freeze and release the full
  successor to Row 28 immediately, independently of remaining gates and CI.
- **Delivery:** After Row 17 is merged, integrate current `main` normally,
  preserve newer complete plan sections and receipts, then open one coherent
  phase PR. Do not merge it, rewrite published history, alter sibling source
  files, or create a later CI-receipt-only commit. Keep worktree, branch and
  evidence artifacts.
- **Dependencies:** Row 17 supplies the actual collection control; Row 26 is
  the exact full-plan predecessor. Neither dependency authorizes touching
  Row 25's nine source files.

## 29 - Row #28 - Independent prefix normalization arithmetic

- **Scope:** Change only
  `backend/tests/test_story_vector_derivation.py`. Replace the two expectations
  that call the same `normalize_prefix` helper as `derive_gemma` with authored
  numeric results. Do not change production, config, contracts, committed
  fixtures, model selection, identity rules or historical acceptance.
- **Original identifiers:** Retain
  `test_derived_prefix_l2_lineage_preserves_native_bytes[128]`, the same
  identifier with `[256]` and `[512]`, and
  `test_native_extension_coverage_derives_same_representation_and_refuses_conflict`.
  All identifiers have prefix
  `backend/tests/test_story_vector_derivation.py::`. Preserve the seven
  `test_native_validation_refuses_invalid_derivation` cases and
  `test_dimensions_selected_in_development_and_identical_for_both_roles`
  unchanged. Original collection contains 12 cases; no identifier is removed,
  renamed or added. The original source SHA-256 is
  `def13e315e77f84fa4fe2aaba8e562742cd1822c6e60adee70108c3713f77589`.
- **Arithmetic:** Generate a native float32 matrix with 768 columns. The first
  row has 3, 4, 12 and 84 at columns 0, 127, 128 and 256; column 767 holds
  1000 and must be excluded. The 128-, 256- and 512-column prefixes have
  lengths 5, 13 and 85. A distinct second row has 5, 12, 84 and 132 at those
  positions, lengths 13, 85 and 157, and an excluded tail of -2000. Expected
  arrays explicitly place the corresponding fractions and zero every other
  column. These rows distinguish prefix boundaries, column order, full-vector
  scaling and per-row scaling without calling the production normalizer.
  Comparison uses float32 epsilon as relative tolerance and zero absolute
  tolerance, so excluded positions must stay exactly zero.
- **Extension composition:** Keep the shared seeded native fixture unchanged.
  Within this one extension case, author distinct prefix positions with signed
  3-4-5 and 5-12-13 rows. Expected rows are keyed by the original article IDs,
  not derived from the production combined matrix. Assert the exact base-then-
  extension input order, the independently assembled native rows, the known
  normalized fractions, complete coverage and the original conflict refusal.
  Native file hashes reflect the actual generated arrays.
- **Preserved guarantees:** Keep native array equality, unchanged snapshot
  bytes, float32 shape, unit row norms, base file hashes, derivation lineage,
  no-inference identity, repeat stability, model pin refusal, development
  selection, confirmation freeze and extension settings/revision refusal.
  The native fixture, seven invalid-input cases and confirmation test retain
  their original function bodies. Do not edit
  `backend/tests/test_story_encoder_candidates.py`; its seven reviewed
  identity, refusal and resume tests remain outside this row.
- **Local evidence at freeze:** The shared selector selects only the changed
  backend test module and no build. Ruff and whitespace checks pass. Mypy
  identified two NumPy tolerance argument types; the corrected source converts
  epsilon to Python float without changing arithmetic. Its rerun is pending.
  Original collection independently confirms all 12 cases in a disposable
  copy. The first fault harness stopped only while formatting a Windows
  short-path receipt, before executing a fault test; it is not fault evidence.
  The corrected harness verifies actual imported file identity with
  `Path.samefile`, source markers and hashes. Its queued proof must show the
  old four arithmetic cases admit a last-columns fault, the new four fail
  their numeric assertions, and the restored full 12-case control passes.
  No passing fault, restored-control or CI result is claimed by this freeze.
- **Frozen source:** SHA-256
  `f0487b6cc6109af59142dc25602d6764ae3cb1bc456f2c8d5664badd68b7299c`.
  The two changed functions and original unchanged-function hashes are
  recorded in the session. The source-writing slot is released.
- **Plan integration:** Imported the exact released Row 27 full predecessor,
  146,771 bytes, SHA-256
  `e0025be9f706d8d8c5d9046535d42cac2065b3ba1359cb72ea7cf1163549cc77`.
  Add only D28 and this section. Removing them must reconstruct every
  predecessor byte, including A5, D3 IN-FLIGHT, the single D11 row and every
  complete earlier section and receipt. Freeze and release the full successor
  immediately for Row 29, independently of remaining gates and CI.
- **Delivery:** Open one coherent phase PR after the affected evidence passes
  and the changes are review-ready. Preserve the complete shared plan and
  report exact source, fault, restored-control and PR-head hashes in the
  session handoff. Do not merge the PR or rewrite published history.
- **Dependencies:** Row 1 supplies the behavior-focused test policy; Row 27 is
  the exact full-plan predecessor, not a production dependency.

## 30 - Row #29 - Populated registry values and mandatory real CSV reader

- **Scope:** Change only
  `backend/tests/contracts/test_curated_registries.py` and
  `backend/tests/contracts/test_cell_shapes.py`, three named test-owned JSON
  examples under `tests/fixtures/curated-registries/`, and the owning schema
  and gate documentation. No production, frontend, configuration, contract,
  persisted format, default, dependency or publication change.
- **Corrected disposition:** The initial replacement direction overlooked
  the canonical explicit-field guarantee in
  `docs/architecture/contracts/schemas.md`. The coordinator withdrew that
  direction after reading the requirement. KEEP the original three committed
  registry checks and the original canonical sentence unchanged: a curator
  must see every effective field, including a default. Add three DISTINCT
  controlled reader/writer proofs instead. Native default handling in these
  test-owned inputs does not authorize omitting fields from repository
  configuration. This is a correction to the assignment, not an owner-policy
  change or a guardrail exception.
- **Original identifiers and reconciliation:** With prefix
  `backend/tests/contracts/test_curated_registries.py::`, retain
  `test_a_curated_registry_survives_a_read_and_a_rewrite[sources.json]`,
  the same identifier with `[taxonomy.json]` and `[watchlist.json]`.
  Add `test_a_controlled_registry_survives_a_read_and_a_rewrite` with those
  same three parameter suffixes. The curated module grows from one function
  and three collected cases to two functions and six cases. The cell module
  retains all 18 functions and 63 cases, including
  `backend/tests/contracts/test_cell_shapes.py::test_both_parsers_read_a_folded_shard_to_the_same_cells`.
  Total: 19 functions and 66 cases before; 20 functions and 69 cases after.
  No identifier is removed or renamed. Archived-base and final collection
  receipts list every identifier. Every original test body except the
  deliberately corrected parser guard is byte-identical.
- **Independent registry oracle:** The three named JSON examples supply
  known keys and values independently of the native model dump and current
  production records. They contain multiple deliberately unsorted records,
  populated nested feeds, aliases, keyword order, active/draft/retired entries,
  retirement dates, nondefault weights, source classifications, configured
  taxonomy defaults and an enabled EDGAR policy with a chosen request rate.
  A case copies its expected example, omits the version and one known default
  (feed weight, vertical floor or organisation kind), then calls the actual
  `Sources`, `Taxonomy` or `Watchlist` JSON reader and custom serializer.
  Parsed output and the next real read must equal the authored expected keys
  and values without sorting lists or comparing incidental JSON whitespace.
  Only the current contract stamp comes from production metadata. These
  proofs remain meaningful when current registries contain no records.
  Primary category C2; secondary C5, C6 and C13. The retained committed-file
  explicit-field checks remain C5 behavior, not a deletion candidate.
- **Mandatory real parser:** Existing full and contract gates already require
  Node, with the declared runtime requirement at the start of
  `docs/how-to/run-the-gates.md`; no new arbitrary version is introduced.
  Replace both skips with named actionable failures: unavailable Node on PATH,
  or missing `frontend/src/lib/charts/series.ts`. Check that the reader is a
  file. Keep the same real Node driver and shipped TypeScript parser, all ten
  hostile-character inputs, the folded physical-row bound, Python CSV
  comparison, subprocess timeout/return-code/stderr reporting and exact
  browser cell comparison. Primary category C13; secondary C4 and C6.
  No Python parser copy, source-text substitute, npm package, mock or
  platform-specific skip is added.
- **Preserved separate guarantees:** `test_app_config.py::test_config_file_validates`
  still validates all three committed registries. The focused serializer-byte
  tests in `test_json_serialization.py` and writer-selection/record-layout
  tests in `test_record_layouts.py` are unchanged. Do not recreate the
  redundant generic one-record-a-line test removed earlier. KEEP the exact
  persisted `content-similarity-judge/metrics` path identity and the council
  recorded-configuration digest proof; neither nearby file is edited.
- **Real fault evidence:** In a disposable copy importing its own actual
  production contracts, remove feed weight from the Sources writer, configured
  default source kind from the Taxonomy writer, or EDGAR request rate from the
  Watchlist writer. Each same collected controlled identifier fails its
  independently known expected-value assertion. Separately change Sources'
  default weight from 1.0 to 0.99, and reverse the first taxonomy lens's keyword
  list in the actual writer. Both fail that assertion, proving default
  handling and meaningful list order rather than fixture self-validation.
  Restore all actual production bytes: all six curated cases pass.
  For parser guards, import setup first in isolated child processes, then
  actually empty PATH or rename the actual named parser in the disposable
  copy. Both invoke the real test body and raise the intended named pytest
  failure, not an import, Git-fixture or unrelated runtime error. Restore the
  parser and run the same collected case with Node 24.22.1: it passes against
  the real CSV driver. The disposable copy is removed after recording all
  receipts. No production-path mutation occurs in the working checkout.
- **Restoration receipts:** Production source hashes after each restore are
  Sources `ee6c3be2d3457502a09907b211abb7a1daf16adc6ca79c9aba26d1fc872140b9`,
  Taxonomy `8d05f1209ba6a2fb5faffb005ea9ae8e9930c43e9813bdd79a2aad253c9a093a`,
  Watchlist `779ce5db81be641449a8e2059a50cfc6fae250f8b0fabe8f296f1d340fd9bddd`,
  and the real TypeScript parser
  `a02694173b9d384f8fe877f676f4d1d4fadba99e6305d88146a1ad2faca59eca`.
  The retained original curated function body is
  `b116f1f553c8e3193707888c1d5bf5d942c87a0f661adb9eb123397ff1e020ec`.
  Its original file was 1,706 bytes with hash
  `e7910cfc0034e05a2197b9c8b977273179ce4927570e0084622aa0b08e4771cf`.
  The original cell file was 23,659 bytes with hash
  `be41641ab07e6a7764dac3ea5501f14c84a5c857f63e490d17d8bc9e27176560`;
  original parser-test body hash
  `cea046fc6a85c21c09f6a5af3ad722118adb99e198106fcb638fb49b6027901a`.
- **Local gates at freeze:** The shared selector reports broad backend and
  frontend coverage because the new fixture directory is an unknown shared
  input. For this test-only change, use the gate guide's bounded named run:
  both changed modules, `test_json_serialization.py`, `test_record_layouts.py`,
  and the three named committed-registry validation cases. All 95 pass.
  Separate restored controls pass six curated cases and the one real Node
  parser case. Ruff over the changed Python files and whitespace checks pass.
  Mypy over the two changed files is still running, unwrapped per the gate
  header; no result is claimed for it. A further disposable empty-current-
  registry fault/control proof is queued; no result is claimed for it at
  freeze. Full merge-candidate CI remains authoritative and has not run yet.
  No published-site behavior changes, so no new local browser matrix.
- **Frozen source:** Curated test file, 2,866 bytes, SHA-256
  `02283d5a8d1ace2aac8b128eede597a49d74badb20f253d7ce974603905e7f06`;
  cell test file, 23,913 bytes, SHA-256
  `6bf30e61a15a8e21719e64de306f946dbc9f618c60186d5249dbfc32e4a6ad43`.
  The three named fixture hashes are Sources
  `f8ba9416b66259bdcff3c7506eb677aa408e455cc67e7d40f3585f401397c44d`,
  Taxonomy `e7d4420c5ec50518ebd0be635e9cbd0297991010551cb5228c9ae5469a6cd9b8`,
  and Watchlist
  `cac7f52ff46c31b437fb7324c0798984dc69faa89c7134a5d7a828837f286061`.
  The source-writing slot was released independently of gates, plan and CI.
- **Plan integration:** Imported the exact released Row 28 full predecessor,
  151,815 bytes, SHA-256
  `3fb198ea7eac6bcdc142e305c9b4ee22ad91a6c1e7d12ea577800146550e6bac`.
  Add only D29 and this section. Removing them must reconstruct every
  predecessor byte, including A5, D3 IN-FLIGHT, the single D11 row and every
  complete earlier section and receipt. Freeze and release the full successor
  immediately, independently of remaining gates and CI.
- **Delivery:** After affected evidence passes, integrate current main
  normally, preserving newer complete canonical rows without duplicating D11.
  Open one meaningful phase PR; do not merge. Record final gate, source,
  fault/control and exact PR-head receipts outside the commit. No later
  CI-receipt-only commit. Keep worktree, branch and evidence artifacts.
- **Dependencies:** Row 1 supplies semantic test policy; Row 28 is the exact
  full-plan predecessor, not a production dependency.

## See also

- [Plan execution](../docs/how-to/execute-a-plan.md).
- [Engineering contract](../CLAUDE.md#13-test-coverage-policy).
- [Contracts and serialization](../docs/architecture/contracts/schemas.md).
- [Local and CI checks](../docs/how-to/run-the-gates.md).
- [Publication validation](../docs/architecture/publishing/what-stops-a-broken-day-being-published.md).
