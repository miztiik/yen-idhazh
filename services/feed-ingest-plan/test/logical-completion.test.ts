/** Does attempt proof survive native packing while refusing changed record membership? */
import { expect, test } from "bun:test";
import { mkdir, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { createHash } from "node:crypto";
import { CONTRACT_VERSION, CandidateRejectionContract, EditorialSelectionContract,
  PLANNER_EXCLUSIONS_VERSION, PLANNING_OBSERVATIONS_VERSION, EXTRACTION_QUALITY_VERSION,
  PUBLISHER_IDENTITY_VERSION, SOURCE_RELIABILITY_VERSION,
  PreviousHarvestDiagnosticsSchema } from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence } from "@idhazh/common-contracts";
import { describeObjectSchema, digestRows, persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRowContract, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { main } from "../src/index";
import { readPlanningHistory } from "../src/metrics/planning-populations";
import { ArticleAssessmentContract, DiversityMetricContract, DispatchContract, SourceRunContract } from "../src/metrics/audit-contracts";
import { commitLogicalRecords, PLANNING_RECORD_KEYS } from "../src/read-ledger-history/logical-records";
import { encodeHistoricalRecord } from "../src/read-ledger-history/encode-historical-record";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import type { AttemptHistory } from "../src/read-ledger-history/complete-attempt";
import { recordedPlan, namedPlanningFiles } from "./plan-recordings";
import { source } from "./harvest-recordings";

const contracts: Record<keyof AttemptHistory["ledgers"] | "source-runs", LedgerRowContract<object>> = {
  "article-assessments": ArticleAssessmentContract, diversity: DiversityMetricContract,
  "editorial-selections": EditorialSelectionContract,
  dispatches: DispatchContract, rejections: CandidateRejectionContract,
  "source-runs": SourceRunContract,
};
test("logical proof survives native daily, monthly and yearly files with no original raw files", async () => {
  for (const previous of [false, true]) for (const zero of [false, true]) {
    const fixture = await recordedPlan(zero ? [source({ url: "https://news.example/empty.xml" })]
      : previous ? [source({ url: "https://news.example/article-failures.xml" })] : undefined);
    try {
      const summary = await main(["--cli"], { inputs: fixture.inputs, runtime: fixture.runtime, output: () => {} });
      if (!("files" in summary) || summary.metrics === undefined) throw new Error("Missing actual summary");
      let history = await readPlanningHistory(namedPlanningFiles(summary, fixture.inputs.outputRoot));
      if (previous) {
        const attempt = selectCompleteAttempt(history).selected!;
        const proofs = new Map<string, NonNullable<LedgerCompletionEvidence["logical"]>>();
        for (const ledger of ["article-assessments", "rejections"] as const) {
          const contract = ledger === "article-assessments" ? ArticleAssessmentContract : CandidateRejectionContract;
          const legacy = contract.legacyVersions[PLANNER_EXCLUSIONS_VERSION];
          const fields = describeObjectSchema(legacy.schema).fields;
          const oldRows = history.ledgers[ledger].rows.map(held => {
            const current = contract.schema.parse(held.row);
            const diagnostics = "details" in current ? current.details.diagnostics : current.diagnostics;
            const originalDiagnostics = diagnostics === null ? null : PreviousHarvestDiagnosticsSchema.parse(
              Object.fromEntries(Object.entries(diagnostics).filter(([key]) => key !== "quality")));
            const score = "score_evidence" in current ? current.score_evidence : null;
            const originalScore = score === null ? null : Object.fromEntries(
              Object.entries(score).filter(([key]) => key !== "source_reliability"));
            if ("details" in current) return { ...held, row: legacy.schema.parse({
              ...current, version: PLANNER_EXCLUSIONS_VERSION,
              details: { ...current.details, diagnostics: originalDiagnostics },
            }) };
            expect(current.source.publisher_id).toBeNull();
            const { publisher_id: _publisherId, ...source } = current.source;
            return { ...held, row: legacy.schema.parse({
              ...current, source, version: PLANNER_EXCLUSIONS_VERSION,
              diagnostics: originalDiagnostics, score_evidence: originalScore,
            }) };
          });
          if (!zero) expect(oldRows.some(held => {
            const row = held.row;
            return ("details" in row ? row.details.diagnostics : row.diagnostics) !== null;
          })).toBe(true);
          // Compute the previous writer's commitment directly from its original shape,
          // independently of the migration encoder whose behavior this case protects.
          const pairs = oldRows.map(held => ({
            key: JSON.stringify(PLANNING_RECORD_KEYS[ledger].map(key => Reflect.get(held.row, key))),
            digest: digestRows([held.row], fields),
          })).sort((left, right) => left.key < right.key ? -1 : left.key > right.key ? 1 : 0);
          const hash = createHash("sha256").update(`${JSON.stringify([
            "2026-10-22", ledger, PLANNER_EXCLUSIONS_VERSION, attempt.date, attempt.run_id,
            attempt.attempt, attempt.correlation_id,
          ])}\n`);
          for (const pair of pairs) hash.update(`${JSON.stringify([pair.key, pair.digest])}\n`);
          const proof = {
            version: "2026-10-22" as const, row_schema_version: PLANNER_EXCLUSIONS_VERSION,
            row_count: pairs.length, content_sha256: hash.digest("hex"),
          };
          proofs.set(ledger, proof);
          const rows = oldRows.map(held => ({ ...held, row: legacy.migrate(held.row) }));
          expect(commitLogicalRecords(ledger, rows, attempt, PLANNER_EXCLUSIONS_VERSION).commitment).toEqual(proof);
          history = { ...history, ledgers: { ...history.ledgers, [ledger]: { ...history.ledgers[ledger], rows } } };
        }
        history = { ...history, sources: { ...history.sources, rows: history.sources.rows.map(held => ({
          ...held, row: { ...held.row, completion_evidence: held.row.completion_evidence!.map(evidence => ({
            ...evidence, logical: proofs.get(evidence.ledger) ?? evidence.logical,
          })) },
        })) } };
      }
      const original = selectCompleteAttempt(history).selected!;
      expect(original).not.toBeNull();
      for (const period of ["daily", "monthly", "yearly"] as const) {
        const named = (ledger: keyof typeof contracts) => ({
          day: summary.date, indexes: { [period]: join(fixture.inputs.outputRoot, "compact", "feed-ingest-plan", ledger, "index", `${period}.json`) },
        });
        for (const ledger of Object.keys(contracts) as (keyof typeof contracts)[]) {
          const day = ledger === "source-runs" ? history.sources : history.ledgers[ledger];
          const covers = summary.date.slice(0, period === "daily" ? 10 : period === "monthly" ? 7 : 4);
          // This tests the native format, not execution of the production gardener.
          const written = await persistLedger({
            ledger, rowContract: contracts[ledger], rows: [...day.rows].reverse(),
            outputRoot: fixture.inputs.outputRoot,
            registryEntry: { name: ledger, family: "feed-ingest-plan", grain: "raw-and-compact",
              lifecycle_status: "active", prefix: ["feed-ingest-plan", ledger] },
            ledgerSettings: fixture.inputs.ledgerSettings,
            writerContext: { ...history.sources.files[0]!.envelope.identity, attempt: 9, producer: "tests.native-packing" },
            period: { tier: "compact", period, covers, builtFrom: day.files.length },
          });
          const file = written.files[0];
          const index = named(ledger).indexes[period]!;
          await mkdir(dirname(index), { recursive: true });
          await writeFile(index, JSON.stringify({
            version: "2026-10-07", ledger, period,
            entries: [{ covers, rows: day.rows.length, bytes: file === undefined ? 0 : (await stat(join(fixture.inputs.outputRoot, file.path))).size,
              state: file === undefined ? "empty" : "packed" }],
          }));
          for (const old of day.files) {
            // Only generated files in this test's named day are removed.
            if (old.envelope.tier === "raw") {
              const raw = namedPlanningFiles(summary, fixture.inputs.outputRoot);
              const paths = ledger === "source-runs" ? raw.sources.rawFiles : raw.ledgers[ledger].rawFiles;
              for (const path of paths ?? []) await rm(path, { force: true });
            }
          }
        }
        history = await readPlanningHistory({
          sources: named("source-runs"), ledgers: {
            "article-assessments": named("article-assessments"), diversity: named("diversity"),
            "editorial-selections": named("editorial-selections"), dispatches: named("dispatches"), rejections: named("rejections"),
          },
        });
        const packed = selectCompleteAttempt(history);
        expect(packed.findings).toEqual([]);
        expect(packed.selected).toEqual(original);
      }
    } finally { await fixture.close(); }
  }
}, 30000);

test("canonical membership dedupes identical records and refuses missing, extra, conflicting or cross-attempt evidence", async () => {
  const fixture = await recordedPlan();
  try {
    const summary = await main(["--cli"], { inputs: fixture.inputs, runtime: fixture.runtime, output: () => {} });
    if (!("files" in summary)) throw new Error("Missing summary");
    const history = await readPlanningHistory(namedPlanningFiles(summary, fixture.inputs.outputRoot));
    const selected = selectCompleteAttempt(history).selected!;
    const ledger = "article-assessments";
    const day = history.ledgers[ledger];
    const held = day.rows[0]!;
    const commitment = commitLogicalRecords(ledger, day.rows, selected).commitment;
    expect(commitLogicalRecords(ledger, [...day.rows].reverse().concat(held), selected).commitment).toEqual(commitment);
    const changed = (rows: readonly StoredLedgerRow<object>[]) => selectCompleteAttempt({
      ...history, ledgers: { ...history.ledgers, [ledger]: { ...day, rows } },
    });
    expect(changed([...day.rows, held]).selected).toEqual(selected);
    expect(changed(day.rows.slice(1)).selected).toBeNull();
    const row = ArticleAssessmentContract.schema.parse(held.row);
    const tampered = { ...held, row: { ...row, observed_at: "2026-10-21T12:00:00Z" } };
    expect(changed([tampered, ...day.rows.slice(1)]).selected).toBeNull();
    expect(changed([...day.rows, tampered]).findings[0]!.reason).toContain("conflicting duplicate");
    const extra = { ...held, row: { ...row, candidate_id: "0".repeat(64) } };
    expect(changed([...day.rows, extra]).selected).toBeNull();
    expect(() => commitLogicalRecords(ledger, [{ ...held, identity: { ...held.identity, attempt: 2 } }], selected))
      .toThrow("another attempt");
    expect(changed([{ ...held, row: { ...row, correlation_id: "other" } }, ...day.rows.slice(1)]).selected).toBeNull();
    expect(selectCompleteAttempt({ ...history, ledgers: { ...history.ledgers, [ledger]: { ...day, status: "missing", rows: [] } } }).selected).toBeNull();
  } finally { await fixture.close(); }
}, 30000);

test("recorded rejection commitments retain their original schema stamp after migration", async () => {
  const fixture = await recordedPlan();
  try {
    const summary = await main(["--cli"], { inputs: fixture.inputs, runtime: fixture.runtime, output: () => {} });
    if (!("files" in summary)) throw new Error("Missing summary");
    const history = await readPlanningHistory(namedPlanningFiles(summary, fixture.inputs.outputRoot));
    const selected = selectCompleteAttempt(history).selected!;
    const rows = history.ledgers.rejections.rows;
    expect(rows.length).toBeGreaterThan(0);
    const original = rows.map(held => {
      const current = CandidateRejectionContract.schema.parse(held.row);
      const {
        diagnostics: _diagnostics, published_on: _publishedOn, failure_code: _failureCode,
        matched_url_marker: _matchedUrlMarker, ...details
      } = current.details;
      return { ...held, row: { ...current, details, version: CONTRACT_VERSION } };
    });
    const migrated = original.map(held => ({
      ...held, row: CandidateRejectionContract.legacyVersions[CONTRACT_VERSION].migrate(held.row),
    }));
    const oldProof = commitLogicalRecords("rejections", migrated, selected, CONTRACT_VERSION).commitment;
    const sources = history.sources.rows.map(held => {
      if (held.row.completion_evidence === null) throw new Error("Missing recorded completion");
      return {
        ...held, row: { ...held.row, completion_evidence: held.row.completion_evidence.map(evidence =>
          evidence.ledger === "rejections" ? { ...evidence, logical: oldProof } : evidence) },
      };
    });
    const oldHistory = { ...history, sources: { ...history.sources, rows: sources } };
    expect(selectCompleteAttempt(oldHistory).selected?.run_id).toBe(selected.run_id);
    expect(commitLogicalRecords("rejections", [...migrated].reverse(), selected, CONTRACT_VERSION).commitment).toEqual(oldProof);
    expect(oldProof).not.toEqual(commitLogicalRecords("rejections", migrated, selected).commitment);
    expect(() => commitLogicalRecords("rejections", migrated, selected, "2026-10-19")).toThrow("unsupported");
    expect(commitLogicalRecords("rejections", migrated, selected, "2026-10-22").commitment.row_schema_version).toBe("2026-10-22");
    const assessments = history.ledgers["article-assessments"].rows;
    const assessment = ArticleAssessmentContract.schema.parse(assessments[0]!.row);
    const assignedAssessment = ArticleAssessmentContract.schema.parse({
      ...assessment, source: { ...assessment.source, publisher_id: "fixture-publisher" },
    });
    expect(ArticleAssessmentContract.schema.parse(encodeHistoricalRecord(
      "article-assessments", assignedAssessment, PUBLISHER_IDENTITY_VERSION,
    )).source.publisher_id).toBe("fixture-publisher");
    const previousAssessment = encodeHistoricalRecord(
      "article-assessments", assessment, SOURCE_RELIABILITY_VERSION,
    );
    expect(ArticleAssessmentContract.legacyVersions[SOURCE_RELIABILITY_VERSION].schema.parse(previousAssessment)
      .source).not.toHaveProperty("publisher_id");
    expect(() => encodeHistoricalRecord(
      "article-assessments", assignedAssessment, SOURCE_RELIABILITY_VERSION,
    )).toThrow("cannot omit curated publisher identity");
    expect(() => commitLogicalRecords("article-assessments", assessments, selected, "2026-10-22"))
      .toThrow("cannot omit measured diagnostics");
    const historicalAssessments = assessments.map(held => {
      const row = ArticleAssessmentContract.schema.parse(held.row);
      return { ...held, row: { ...row, diagnostics: null,
        score_evidence: row.score_evidence === null ? null : { ...row.score_evidence, source_reliability: null },
      } };
    });
    expect(commitLogicalRecords("article-assessments", historicalAssessments, selected, "2026-10-22")
      .commitment.row_schema_version).toBe("2026-10-22");
    for (const version of [CONTRACT_VERSION, "2026-10-22", PLANNING_OBSERVATIONS_VERSION]) {
      const legacy = DispatchContract.legacyVersions![version]!;
      const dispatches = history.ledgers.dispatches.rows.map(held => {
        const current = DispatchContract.schema.parse(held.row);
        const { planning_observations: _observations, ...content } = current.content;
        const { source_reliability: _reliability, ...ratings } = current.selection.ratings;
        expect(current.content.source.publisher_id).toBeNull();
        expect(current.selection.source.publisher_id).toBeNull();
        const { publisher_id: _contentPublisherId, ...contentSource } = current.content.source;
        const { publisher_id: _selectionPublisherId, ...selectionSource } = current.selection.source;
        const original = legacy.schema.parse({
          ...current, version,
          content: version === PLANNING_OBSERVATIONS_VERSION ? {
            ...current.content, source: contentSource, version: PLANNING_OBSERVATIONS_VERSION,
          } : { ...content, source: contentSource, version: CONTRACT_VERSION },
          selection: { ...current.selection, source: selectionSource, version: CONTRACT_VERSION, ratings },
        });
        return { ...held, row: original };
      });
      const migratedDispatches = dispatches.map(held => ({ ...held, row: legacy.migrate(held.row) }));
      const proof = commitLogicalRecords("dispatches", migratedDispatches, selected, version).commitment;
      const fields = describeObjectSchema(legacy.schema).fields;
      const records = dispatches.map(held => {
        const row = held.row as { content: { date: string; candidate_id: string } };
        return [
          JSON.stringify([row.content.date, row.content.candidate_id]),
          digestRows([held.row as Record<string, unknown>], fields),
        ];
      }).sort(([a], [b]) => a! < b! ? -1 : a! > b! ? 1 : 0);
      const expected = createHash("sha256").update(`${JSON.stringify([
        "2026-10-22", "dispatches", version, selected.date, selected.run_id, selected.attempt, selected.correlation_id,
      ])}\n`);
      for (const record of records) expected.update(`${JSON.stringify(record)}\n`);
      expect(proof.content_sha256).toBe(expected.digest("hex"));
      expect(proof.row_schema_version).toBe(version);
      if (version === PLANNING_OBSERVATIONS_VERSION) {
        expect(migratedDispatches.map(held => DispatchContract.schema.parse(held.row).content))
          .toEqual(history.ledgers.dispatches.rows.map(held => DispatchContract.schema.parse(held.row).content));
      }
      expect(() => commitLogicalRecords("dispatches", history.ledgers.dispatches.rows, selected, version))
        .toThrow(version === PLANNING_OBSERVATIONS_VERSION
          ? "cannot omit source reliability evidence" : "cannot omit planning observations");
    }
    expect(() => commitLogicalRecords("article-assessments", assessments, selected, PLANNER_EXCLUSIONS_VERSION))
      .toThrow("cannot omit measured extraction quality");
    expect(() => commitLogicalRecords("article-assessments", assessments, selected, EXTRACTION_QUALITY_VERSION))
      .toThrow("cannot omit source reliability evidence");
    expect(() => commitLogicalRecords("editorial-selections", history.ledgers["editorial-selections"].rows, selected, CONTRACT_VERSION))
      .toThrow("cannot omit source reliability evidence");
    for (const ledger of ["editorial-selections", "article-assessments"] as const) {
      const contract = ledger === "editorial-selections" ? EditorialSelectionContract : ArticleAssessmentContract;
      const version = ledger === "editorial-selections" ? CONTRACT_VERSION : EXTRACTION_QUALITY_VERSION;
      const legacy = ledger === "editorial-selections"
        ? EditorialSelectionContract.legacyVersions[CONTRACT_VERSION]
        : ArticleAssessmentContract.legacyVersions[EXTRACTION_QUALITY_VERSION];
      const original = history.ledgers[ledger].rows.map(held => {
        const row = contract.schema.parse(held.row);
        expect(row.source.publisher_id).toBeNull();
        const { publisher_id: _publisherId, ...source } = row.source;
        const scores = "ratings" in row ? row.ratings : row.score_evidence;
        const oldScores = scores === null ? null : Object.fromEntries(
          Object.entries(scores).filter(([key]) => key !== "source_reliability"));
        return { ...held, row: legacy.schema.parse({
          ...row, source, version, ...("ratings" in row ? { ratings: oldScores } : { score_evidence: oldScores }),
        }) };
      });
      const fields = describeObjectSchema(legacy.schema).fields;
      const records = original.map(held => [
        JSON.stringify(PLANNING_RECORD_KEYS[ledger].map(key => Reflect.get(held.row, key))),
        digestRows([held.row as Record<string, unknown>], fields),
      ]).sort(([a], [b]) => a! < b! ? -1 : a! > b! ? 1 : 0);
      const expected = createHash("sha256").update(`${JSON.stringify([
        "2026-10-22", ledger, version, selected.date, selected.run_id, selected.attempt, selected.correlation_id,
      ])}\n`);
      for (const record of records) expected.update(`${JSON.stringify(record)}\n`);
      const migrated = original.map(held => ({ ...held, row: legacy.migrate(held.row) }));
      expect(commitLogicalRecords(ledger, migrated, selected, version).commitment.content_sha256)
        .toBe(expected.digest("hex"));
      expect(commitLogicalRecords(ledger, [...migrated].reverse(), selected, version).commitment.content_sha256)
        .toBe(commitLogicalRecords(ledger, migrated, selected, version).commitment.content_sha256);
    }
  } finally { await fixture.close(); }
});
