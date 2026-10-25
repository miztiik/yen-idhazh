/** Does named native history retain original identities and distinguish proof from missing evidence? */
import { beforeAll, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import {
  ArticleAssessmentRecordSchema, CandidateRejectionContract, CONTRACT_VERSION,
  DocumentObservationRecordSchema, EditorialSelectionContract, EditorialSelectionRowSchema, SourceRunRecordSchema,
  DOCUMENT_OBSERVATION_VERSION,
  PLANNER_EXCLUSIONS_VERSION, EXTRACTION_QUALITY_VERSION, PreviousHarvestDiagnosticsSchema,
} from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence } from "@idhazh/common-contracts";
import {
  appendIdentityColumns, createUuidV5, describeObjectSchema, digestRows, persistLedger,
} from "@idhazh/ledger-file-writer";
import type { LedgerRowContract, PersistLedgerResult, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { Int64, tableFromIPC, vectorFromArray } from "apache-arrow";
import initializeParquet, { Table as WasmTable, WriterPropertiesBuilder, readMetadata, readParquet, writeParquet } from "parquet-wasm/esm";
import { tableToIPC } from "apache-arrow";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { readPublisherPublication } from "../src/read-ledger-history/read-publisher-publication";
import { readIngestEvidence, closedObservationDays } from "../src/read-ledger-history/read-ingest-evidence";
import { estimateOperationalFeedback } from "../src/estimate-operational-feedback";
import { settleIngestObservations } from "../src/settle-ingest-observations";
import { rollupIngestOutcomes } from "../src/rollup-ingest-outcomes";
import { classifyPublicationHistoryError } from "../src/read-ledger-history/classify-publication-history-error";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";
import { ItemHealthPublicationSchema, PublishedRowSchema, PUBLISHED_ROW_SCHEMA_VERSION } from "../src/metrics/publication-evidence";
import { ITEM_HEALTH_ROW_SCHEMA_VERSION } from "../src/read-ledger-history/item-health-version";
import { resolveHealthInventory } from "../src/read-ledger-history/read-health-inventory";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import type { AttemptHistory } from "../src/read-ledger-history/complete-attempt";
import { readHistoricalSelections } from "../src/partition-article-shards/read-editorial-selection";
import { partitionArticles, persistDispatches } from "../src/partition-article-shards/shard-packer";
import { fixtureInput, readWritten, registration, settings, writer, writeRows } from "./partition-fixtures";
import {
  ArticleAssessmentContract, DiversityMetricContract, DispatchContract, DocumentObservationContract,
  SourceRunContract, legacyAuditSchemas,
} from "../src/metrics/audit-contracts";

const selectionContract = EditorialSelectionContract;
beforeAll(async () => { await initializeParquet(); });
function evidence(ledger: LedgerCompletionEvidence["ledger"], written: PersistLedgerResult): LedgerCompletionEvidence {
  if (written.status === "skipped") throw new Error("Fixture completion ledger was skipped");
  return {
    ledger, row_count: written.files.reduce((count, file) => count + file.row_count, 0),
    files: written.files.map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })),
    logical: null,
  };
}
async function completeHistory(root: string, observedAt?: string) {
  const input = await fixtureInput(root, { count: 1 });
  const packed = partitionArticles({
    selections: input.curation.rows, candidates: input.candidates,
    context: input.context, settings: input.planning.config.partition,
  });
  const dispatch = await persistDispatches(packed, {
    outputRoot: root, writerContext: writer(input.fixture.run_id), ledgerSettings: settings,
    registration: registration("dispatches"), date: input.fixture.date,
    correlation_id: input.fixture.correlation_id,
  });
  const assessments = await writeRows(root, "article-assessments", input.fixture.date,
    ArticleAssessmentRecordSchema, input.curation.assessments, writer(input.fixture.run_id),
    ArticleAssessmentContract.schemaVersion);
  const empty: PersistLedgerResult = { status: "empty", files: [] };
  const completion = [
    evidence("editorial-selections", input.persisted.selections), evidence("dispatches", dispatch),
    evidence("article-assessments", assessments), evidence("rejections", empty), evidence("diversity", empty),
  ];
  const source = (attempt = 1, zero = false) => SourceRunRecordSchema.parse({
    date: input.fixture.date, correlation_id: input.fixture.correlation_id, run_id: input.fixture.run_id,
    attempt, source_id: input.candidates[0]!.source_id, source: input.candidates[0]!.source, status: "active",
    fetch_status: "success", parse_status: "success", parsed_count: 1, harvested_count: 1,
    fresh_count: 1, duplicate_count: 0, eligible_count: 1, normalized_count: 1, selected_count: zero ? 0 : 1,
    published_count: null, lead_count: null, drop_reasons: [], fetch_duration_ms: 1, parse_duration_ms: 1,
    last_failure_at: null, last_failure_reason: null, history_success_fraction: null,
    history_success_attempts: null, history_window_days: null, observation_phase: "plan_complete",
    observed_at: observedAt ?? input.fixture.observed_at, expected_source_count: 1,
    completion_evidence: zero ? completion.map(item => ({ ...item, row_count: 0, files: [] })) : completion,
  });
  const sourceWritten = await writeRows(root, "source-runs", input.fixture.date,
    SourceRunRecordSchema, [source()], writer(input.fixture.run_id), SourceRunContract.schemaVersion);
  const sources = await readWritten(root, "source-runs", input.fixture.date,
    SourceRunContract, sourceWritten);
  const ledgers: AttemptHistory["ledgers"] = {
    "editorial-selections": await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections),
    dispatches: await readWritten(root, "dispatches", input.fixture.date, DispatchContract, dispatch),
    "article-assessments": await readWritten(root, "article-assessments", input.fixture.date, ArticleAssessmentContract, assessments),
    rejections: await readWritten(root, "rejections", input.fixture.date, CandidateRejectionContract, empty),
    diversity: await readWritten(root, "diversity", input.fixture.date, DiversityMetricContract, empty),
  };
  return { input, source, sourceWritten, history: { sources, ledgers }, packed };
}
async function compactSelections(
  root: string, input: Awaited<ReturnType<typeof fixtureInput>>, rows: readonly StoredLedgerRow<ReturnType<typeof EditorialSelectionRowSchema.parse>>[],
  period: "daily" | "monthly" | "yearly",
) {
  const covers = period === "daily" ? input.fixture.date : period === "monthly" ? input.fixture.date.slice(0, 7) : input.fixture.date.slice(0, 4);
  const written = await persistLedger({
    ledger: "editorial-selections", registryEntry: registration("editorial-selections"), outputRoot: root,
    writerContext: { ...writer(input.fixture.run_id, 9, 6), producer: "tests.compactor" },
    ledgerSettings: settings, rowContract: selectionContract,
    period: { tier: "compact", period, covers, builtFrom: 1 }, rows,
  });
  const file = written.files[0]!;
  const path = join(root, file.path);
  const indexPath = join(root, "compact", "feed-ingest-plan", "editorial-selections", "index", `${period}.json`);
  await mkdir(dirname(indexPath), { recursive: true });
  const index = {
    version: "2026-10-07", ledger: "editorial-selections", period,
    entries: [{ covers, rows: file.row_count, bytes: (await stat(path)).size, state: "packed" }],
  };
  await writeFile(indexPath, JSON.stringify(index));
  return { path, indexPath, index };
}

async function migrateAuditFixture<TLegacy extends object, TCurrent extends object>(
  root: string, day: string, run: string, ledger: Parameters<typeof readLedgerDay>[0]["ledger"], path: string,
  legacySchema: LedgerRowContract<TLegacy>["schema"], currentContract: LedgerRowContract<TCurrent>,
): Promise<TCurrent> {
  const input: unknown = await Bun.file(new URL(path, import.meta.url)).json();
  const row = legacySchema.parse(input);
  const written = await writeRows(root, ledger, day, legacySchema, [row], writer(run), "2026-10-20");
  const pathBefore = join(root, written.files[0]!.path);
  const originalBytes = await readFile(pathBefore);
  const loaded = await readWritten(root, ledger, day, currentContract, written);
  expect(await readFile(pathBefore)).toEqual(originalBytes);
  expect(loaded.rows).toHaveLength(1);
  expect(loaded.rows[0]!.row).toMatchObject({ version: currentContract.schemaVersion });
  return loaded.rows[0]!.row;
}

test("native raw and daily reads preserve original writer identity instead of the compactor identity", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-periods-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const raw = await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections);
    expect(raw.tier).toBe("raw");
    expect(raw.rows).toHaveLength(1);
    const original = raw.rows[0]!;
    const compact = await compactSelections(root, input, raw.rows, "daily");
    const current = await readLedgerDay({
      ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: compact.indexPath }, rawFiles: input.persisted.selections.files.map(file => join(root, file.path)),
    });

    expect(current.tier).toBe("daily");
    expect(current.rows).toEqual([original]);
    expect(current.files[0]!.envelope.identity.attempt).toBe(9);
    expect(current.rows[0]!.identity.attempt).toBe(1);
    expect(current.rows[0]!.identity.shard).toBe(0);
    expect(current.rows[0]!.identity.unit_id).toBe(original.identity.unit_id);

    const observation = DocumentObservationRecordSchema.parse(await Bun.file(new URL(
      "../../../tests/fixtures/contracts/feed-ingest-document-observation/refused-fetch.json", import.meta.url,
    )).json());
    const attemptObservation = {
      ...observation, event_id: createUuidV5(observation.event_id, "attempt:1"),
      operation: "attempt" as const, request_phase: "target" as const,
      request_sequence: 0, retry: 0, request_coverage: "complete" as const, dispatched_request_count: 0,
    };
    expect(DocumentObservationRecordSchema.parse(attemptObservation).dispatched_request_count).toBe(0);
    expect(DocumentObservationRecordSchema.parse({
      ...attemptObservation, request_coverage: "unknown", dispatched_request_count: null,
    }).dispatched_request_count).toBeNull();
    expect(() => DocumentObservationRecordSchema.parse({
      ...attemptObservation, request_coverage: "unknown", dispatched_request_count: 0,
    })).toThrow("unknown request coverage");
    const feedObservation = { ...observation, document_kind: "feed" as const };
    const partialFeedAttempt = DocumentObservationRecordSchema.parse({
      ...attemptObservation, document_kind: "feed", request_phase: "robots", request_coverage: "partial",
      dispatched_request_count: 1,
    });
    expect(partialFeedAttempt).toMatchObject({
      document_kind: "feed", outcome: "failed", request_phase: "robots",
      request_coverage: "partial", dispatched_request_count: 1,
    });
    expect(() => DocumentObservationRecordSchema.parse({
      ...feedObservation, candidate_id: "a".repeat(64),
    })).toThrow("article opportunity requires its article kind");
    expect(() => DocumentObservationRecordSchema.parse({
      ...observation, candidate_id: "a".repeat(64), observed_run_id: null,
    })).toThrow("article opportunity requires its article kind");
    const correctedObservation = DocumentObservationRecordSchema.parse({
      ...observation, event_id: createUuidV5(observation.event_id, "correction:1"),
      corrects_event_id: observation.event_id, correction_revision: 1,
      occurred_at: "2026-10-21T12:01:00Z",
    });
    expect(correctedObservation).toMatchObject({
      corrects_event_id: observation.event_id, correction_revision: 1,
    });
    expect(() => DocumentObservationRecordSchema.parse({
      ...observation, corrects_event_id: observation.event_id, correction_revision: 1,
    })).toThrow("cannot correct itself");
    expect(() => DocumentObservationRecordSchema.parse({
      ...correctedObservation, correction_revision: null,
    })).toThrow("both its target event and positive revision");
    const observationWriter = writer(observation.observed_run_id!);
    const observationRawWritten = await writeRows(
      root, "document-observations", input.fixture.date, DocumentObservationRecordSchema,
      [observation, correctedObservation], observationWriter, DOCUMENT_OBSERVATION_VERSION,
    );
    const observationRaw = await readWritten(
      root, "document-observations", input.fixture.date, DocumentObservationContract, observationRawWritten,
    );
    expect(observationRaw.tier).toBe("raw");
    expect(observationRaw.rows).toHaveLength(2);
    expect(observationRaw.rows.map(held => held.row.event_id).sort()).toEqual(
      [observation.event_id, correctedObservation.event_id].sort(),
    );
    const rawCorrection = observationRaw.rows.find(held => held.row.event_id === correctedObservation.event_id);
    expect(rawCorrection?.row).toMatchObject({
      occurred_at: "2026-10-21T12:01:00Z",
      corrects_event_id: observation.event_id, correction_revision: 1,
    });
    const observationCompact = await persistLedger({
      ledger: "document-observations", registryEntry: registration("document-observations"),
      outputRoot: root, writerContext: { ...writer(observation.observed_run_id!, 9, 6), producer: "tests.compactor" },
      ledgerSettings: settings, rowContract: DocumentObservationContract,
      period: { tier: "compact", period: "daily", covers: input.fixture.date, builtFrom: 1 },
      rows: observationRaw.rows,
    });
    const observationFile = observationCompact.files[0]!;
    const observationPath = join(root, observationFile.path);
    const observationIndexPath = join(root, "compact", "feed-ingest-plan", "document-observations", "index", "daily.json");
    await mkdir(dirname(observationIndexPath), { recursive: true });
    await writeFile(observationIndexPath, JSON.stringify({
      version: "2026-10-07", ledger: "document-observations", period: "daily",
      entries: [{
        covers: input.fixture.date, rows: observationFile.row_count,
        bytes: (await stat(observationPath)).size, state: "packed",
      }],
    }));
    const observationDaily = await readLedgerDay({
      ledger: "document-observations", day: input.fixture.date, contract: DocumentObservationContract,
      indexes: { daily: observationIndexPath },
    });
    expect(observationDaily.tier).toBe("daily");
    expect(observationDaily.rows.map(held => held.row)).toEqual(observationRaw.rows.map(held => held.row));
    const compactCorrection = observationDaily.rows.find(held => held.row.event_id === correctedObservation.event_id);
    expect(compactCorrection?.row).toMatchObject({
      occurred_at: "2026-10-21T12:01:00Z",
      corrects_event_id: observation.event_id, correction_revision: 1,
    });
    expect(observationDaily.rows[0]!.identity.unit_id).toBe(observationRaw.rows[0]!.identity.unit_id);

    const event = (name: string, patch: Partial<typeof observation> = {}) => DocumentObservationRecordSchema.parse({
      ...observation, event_id: createUuidV5(observation.event_id, name),
      candidate_id: "a".repeat(64), publisher_id: "recorded-publisher",
      ...patch,
    });
    const failedFetch = event("failed-fetch", { attribution: "source", failure_code: "http", http_status: 403 });
    const target = (name: string, sequence: number, phase: "validation" | "robots" | "target", count: number) => event(name, {
      operation: "attempt", caused_by_event_id: failedFetch.event_id,
      request_phase: phase, request_sequence: sequence, retry: Math.max(0, sequence - 2),
      dispatched_request_count: count, request_coverage: "complete",
      outcome: "success", attribution: null, failure_code: null,
    });
    const requestFacts = [
      failedFetch, target("validation", 0, "validation", 0), target("robots", 1, "robots", 1),
      target("target-first", 2, "target", 1), target("target-retry", 3, "target", 1),
      target("target-redirect", 4, "target", 1),
    ];
    const successfulFetch = event("successful-fetch", {
      candidate_id: "b".repeat(64), outcome: "success", attribution: null, failure_code: null,
    });
    requestFacts.push(successfulFetch, event("successful-target", {
      candidate_id: successfulFetch.candidate_id, operation: "attempt", caused_by_event_id: successfulFetch.event_id,
      request_phase: "target", request_sequence: 0, retry: 0, dispatched_request_count: 1,
      request_coverage: "complete", outcome: "success", attribution: null, failure_code: null,
    }), event("successful-extraction", {
      candidate_id: successfulFetch.candidate_id, operation: "parse", caused_by_event_id: successfulFetch.event_id,
      outcome: "success", attribution: null, failure_code: null,
    }), event("feed-poll", {
      candidate_id: null, document_kind: "feed", operation: "attempt",
      request_phase: "target", request_sequence: 0, retry: 0, dispatched_request_count: 10,
      request_coverage: "complete", outcome: "success", attribution: null, failure_code: null,
    }));
    const settled = settleIngestObservations([...requestFacts, ...requestFacts], input.fixture.date, input.fixture.date);
    expect(settled.rows).toHaveLength(requestFacts.length);
    expect(rollupIngestOutcomes(settled.rows, true).sources[0]).toMatchObject({
      observed_attempted_opportunities: 2, observed_measured_opportunities: 2, request_coverage: 1,
      total_target_requests: 4, source_wasted_requests: 3, waste_ratio: 0.75,
      extracted_opportunities: 1, source_failed_opportunities: 1, cpu: null, private_memory: null,
    });
    const extractionFailure = event("successful-extraction", {
      candidate_id: successfulFetch.candidate_id, operation: "parse", caused_by_event_id: successfulFetch.event_id,
      outcome: "failed", attribution: "source", failure_code: "empty-content",
    });
    const replaceExtraction = (attribution: "source" | "pipeline" | "unresolved") => requestFacts.map(row =>
      row.event_id === extractionFailure.event_id ? { ...extractionFailure, attribution } : row);
    expect(rollupIngestOutcomes(replaceExtraction("source"), true).sources[0])
      .toMatchObject({ total_target_requests: 4, source_wasted_requests: 4 });
    expect(rollupIngestOutcomes(replaceExtraction("pipeline"), true).sources[0])
      .toMatchObject({ total_target_requests: 4, source_wasted_requests: 3, pipeline_failed_opportunities: 1 });
    expect(rollupIngestOutcomes(replaceExtraction("unresolved"), true).sources[0])
      .toMatchObject({
        total_target_requests: 4, source_wasted_requests: null, unresolved_opportunities: 1,
        observed_request_census_opportunities: 2, observed_measured_opportunities: 1,
        measured_coverage: 0.5, measured_target_requests: 3, measured_source_wasted_requests: 3, waste_ratio: 1,
      });
    expect(rollupIngestOutcomes(settled.rows, false).sources[0])
      .toMatchObject({
        request_coverage: null, measured_coverage: null, total_target_requests: null, source_wasted_requests: null,
        measured_target_requests: 4, measured_source_wasted_requests: 3,
      });
    expect(rollupIngestOutcomes(requestFacts.filter(row => row.event_id !== extractionFailure.event_id), true).sources[0])
      .toMatchObject({
        observed_request_census_opportunities: 2, observed_resolved_outcome_opportunities: 1,
        request_coverage: 1, measured_coverage: 0.5, measured_target_requests: 3, unresolved_opportunities: 1,
      });
    const correction = event("request-correction", {
      ...requestFacts[3]!, event_id: createUuidV5(observation.event_id, "request-correction"),
      corrects_event_id: requestFacts[3]!.event_id, correction_revision: 1,
      dispatched_request_count: 2, occurred_at: "2026-10-21T23:00:00Z",
    });
    expect(rollupIngestOutcomes(settleIngestObservations(
      [...requestFacts, correction], input.fixture.date, input.fixture.date,
    ).rows, true).sources[0]).toMatchObject({ total_target_requests: 5, source_wasted_requests: 4, waste_ratio: 0.8 });
    expect(() => settleIngestObservations([...requestFacts, correction, {
      ...correction, event_id: createUuidV5(observation.event_id, "tied-correction"),
    }], input.fixture.date, input.fixture.date)).toThrow("Tied document correction");
    expect(settleIngestObservations([{
      ...failedFetch, occurred_at: "2026-10-20T12:00:00Z",
    }, { ...correction, corrects_event_id: failedFetch.event_id }],
    input.fixture.date, input.fixture.date)).toMatchObject({
      rows: [], notices: [{ reason: "correction_outside_window" }],
    });
    expect(settleIngestObservations([correction], input.fixture.date, input.fixture.date)).toMatchObject({
      rows: [], notices: [{ reason: "correction_target_unavailable" }],
    });
    const partial = event("partial-fetch", { candidate_id: "c".repeat(64) });
    const partialFacts = [...requestFacts, partial, event("partial-target", {
      candidate_id: partial.candidate_id, operation: "attempt", caused_by_event_id: partial.event_id,
      request_phase: "target", request_sequence: 0, retry: 0, dispatched_request_count: null,
      request_coverage: "unknown",
    }), event("standalone-target", {
      observed_run_id: null, candidate_id: null, operation: "attempt",
      request_phase: "target", request_sequence: 0, retry: 0, dispatched_request_count: 2,
      request_coverage: "complete",
    })];
    expect(rollupIngestOutcomes(partialFacts, true)).toMatchObject({
      sources: [{
        observed_attempted_opportunities: 3, observed_measured_opportunities: 2, request_coverage: 2 / 3,
        observed_target_requests: 4, observed_source_wasted_requests: 3,
        total_target_requests: null, source_wasted_requests: null, waste_ratio: 0.75,
        measured_target_requests: 4, measured_source_wasted_requests: 3,
        unresolved_opportunities: 1,
      }],
      unallocated: { observation_count: 2, observed_dispatched_requests: 12 },
    });
    expect(rollupIngestOutcomes([], true).sources).toEqual([]);
    expect(rollupIngestOutcomes([event("unidentified", { candidate_id: null })], true).sources[0])
      .toMatchObject({ observed_attempted_opportunities: 0, request_coverage: null, total_target_requests: null });
    const zeroFetch = { ...failedFetch, failure_code: "robots-denied" as const };
    const zero = rollupIngestOutcomes([zeroFetch, target("zero-validation", 0, "validation", 0)], true);
    expect(zero.sources[0]).toMatchObject({
      observed_attempted_opportunities: 1, observed_measured_opportunities: 1, total_target_requests: 0,
      source_wasted_requests: 0, waste_ratio: null,
    });
    const recoveredFacts = requestFacts.map(row => row.candidate_id === successfulFetch.candidate_id
      ? { ...row, candidate_id: failedFetch.candidate_id } : row);
    expect(rollupIngestOutcomes(recoveredFacts, true).sources[0]).toMatchObject({
      observed_attempted_opportunities: 1, observed_measured_opportunities: 1,
      extracted_opportunities: 1, source_failed_opportunities: 0,
      measured_target_requests: 4, measured_source_wasted_requests: 3, waste_ratio: 0.75,
    });
    const cohortFacts = Array.from({ length: 25 }, (_, index) => {
      const candidate_id = (index + 1).toString(16).padStart(64, "0");
      const fetch = event(`cohort-fetch-${index}`, {
        candidate_id, outcome: index < 10 ? "failed" : "success",
        attribution: index < 10 ? "source" : null, failure_code: index < 10 ? "http" : null,
        http_status: index < 10 ? 403 : 200,
      });
      const attempt = event(`cohort-target-${index}`, {
        candidate_id, operation: "attempt", caused_by_event_id: fetch.event_id,
        request_phase: "target", request_sequence: 0, retry: 0,
        dispatched_request_count: index >= 20 && index < 23 ? null : 1,
        request_coverage: index >= 20 && index < 23 ? "unknown" : "complete",
        outcome: "success", attribution: null, failure_code: null,
      });
      const parse = event(`cohort-parse-${index}`, {
        candidate_id, operation: "parse", caused_by_event_id: fetch.event_id,
        outcome: index >= 23 ? "failed" : "success",
        attribution: index >= 23 ? "unresolved" : null, failure_code: null,
      });
      return index < 10 ? [fetch, attempt] : [fetch, attempt, parse];
    }).flat();
    const cohortWritten = await writeRows(join(root, "cohort"), "document-observations", input.fixture.date,
      DocumentObservationRecordSchema, cohortFacts, observationWriter, DOCUMENT_OBSERVATION_VERSION);
    const cohortRead = await readIngestEvidence({
      root: join(root, "cohort"), now: "2026-10-22T00:00:00Z", window_days: 1,
      registration: registration("document-observations"),
      days: [{ day: input.fixture.date, raw_files: cohortWritten.files.map(file => file.path) }],
    });
    const cohort = cohortRead.sources[0]!;
    expect(cohort).toMatchObject({
      observed_attempted_opportunities: 25, observed_measured_opportunities: 20,
      observed_request_census_opportunities: 22, observed_resolved_outcome_opportunities: 23,
      request_coverage: 22 / 25, measured_coverage: 0.8,
      measured_target_requests: 20, measured_source_wasted_requests: 10, waste_ratio: 0.5,
      observed_target_requests: 22, total_target_requests: null, source_wasted_requests: null,
      unresolved_opportunities: 2, availability: "partial",
    });
    const lessMeasured = cohortFacts.map(row => row.event_id === createUuidV5(observation.event_id, "cohort-target-19")
      ? { ...row, request_coverage: "unknown" as const, dispatched_request_count: null } : row);
    expect(rollupIngestOutcomes(lessMeasured, true).sources[0]).toMatchObject({
      observed_attempted_opportunities: 25, observed_measured_opportunities: 19, measured_coverage: 19 / 25,
      measured_target_requests: 19, measured_source_wasted_requests: 10, waste_ratio: 10 / 19,
    });
    const feedbackPolicy = input.planning.config.feedback;
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [cohort] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "qualified", measured_coverage: 0.8,
      request_waste_ratio: 0.5, request_component_weight: 1 / 3,
      request_component_penalty: 1 / 6,
    });
    const belowSupport = rollupIngestOutcomes(lessMeasured, true).sources[0]!;
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [belowSupport] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "insufficient_support", request_waste_ratio: null,
      request_component_penalty: null,
    });
    const fullyWastedFacts = cohortFacts.filter(row => row.operation !== "parse").map(row =>
      row.operation === "fetch" ? {
        ...row, outcome: "failed" as const, attribution: "source" as const,
        failure_code: "http" as const, http_status: 403,
      } : row);
    const fullyWasted = rollupIngestOutcomes(fullyWastedFacts, true).sources[0]!;
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [fullyWasted] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "qualified", request_waste_ratio: 1,
      request_component_penalty: 1 / 3,
    });
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [zero.sources[0]!] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "insufficient_support", measured_target_requests: 0,
      request_waste_ratio: null, request_component_penalty: null,
    });
    const zeroRequestsWithQualifiedSupport = {
      ...cohort, measured_target_requests: 0, measured_source_wasted_requests: 0,
    };
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [zeroRequestsWithQualifiedSupport] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "insufficient_support", observed_measured_opportunities: 20,
      measured_coverage: 0.8, request_waste_ratio: null, request_component_penalty: null,
    });
    const unknownFacts = cohortFacts.filter(row => row.operation !== "parse").map(row =>
      row.operation === "attempt" ? {
        ...row, request_coverage: "unknown" as const, dispatched_request_count: null,
      } : row);
    const unknownRequests = rollupIngestOutcomes(unknownFacts, true).sources[0]!;
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [unknownRequests] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "unavailable", measured_target_requests: null,
      request_waste_ratio: null, request_component_penalty: null,
    });
    const missingCoverage = rollupIngestOutcomes(cohortFacts, false).sources[0]!;
    expect(estimateOperationalFeedback(
      { ...cohortRead, sources: [missingCoverage] }, feedbackPolicy,
    ).sources[0]).toMatchObject({
      qualification_status: "unavailable", measured_coverage: null,
      request_component_penalty: null,
    });

    const evidenceRoot = join(root, "request-evidence");
    const nativeFacts = await writeRows(evidenceRoot, "document-observations", input.fixture.date,
      DocumentObservationRecordSchema, requestFacts, observationWriter, DOCUMENT_OBSERVATION_VERSION);
    const replayFacts = await writeRows(evidenceRoot, "document-observations", input.fixture.date,
      DocumentObservationRecordSchema, requestFacts, { ...observationWriter, attempt: 2 }, DOCUMENT_OBSERVATION_VERSION);
    const evidenceInput = {
      root: evidenceRoot, now: "2026-10-22T00:00:00Z", window_days: 1,
      registration: registration("document-observations"),
      days: [{ day: input.fixture.date, raw_files: [...nativeFacts.files, ...replayFacts.files].map(file => file.path) }],
    };
    const rawEvidence = await readIngestEvidence(evidenceInput);
    expect(rawEvidence).toMatchObject({
      availability: "available", sources: [{ total_target_requests: 4, source_wasted_requests: 3 }],
      publishers: [{ publisher_id: "recorded-publisher", observed_attempted_opportunities: 2 }],
    });
    expect(rawEvidence.history.days[0]!.files).toHaveLength(2);
    const nativeDay = await readWritten(evidenceRoot, "document-observations", input.fixture.date, DocumentObservationContract, nativeFacts);
    const packedFacts = await persistLedger({
      ledger: "document-observations", registryEntry: registration("document-observations"),
      outputRoot: evidenceRoot, writerContext: { ...observationWriter, attempt: 9, producer: "tests.compactor" },
      ledgerSettings: settings, rowContract: DocumentObservationContract,
      period: { tier: "compact", period: "daily", covers: input.fixture.date, builtFrom: 1 },
      rows: nativeDay.rows,
    });
    const packedFile = packedFacts.files[0]!;
    const packedIndex = join("compact", "feed-ingest-plan", "document-observations", "index", "daily.json");
    await mkdir(dirname(join(evidenceRoot, packedIndex)), { recursive: true });
    await writeFile(join(evidenceRoot, packedIndex), JSON.stringify({
      version: "2026-10-07", ledger: "document-observations", period: "daily",
      entries: [{ covers: input.fixture.date, rows: packedFile.row_count,
        bytes: (await stat(join(evidenceRoot, packedFile.path))).size, state: "packed" }],
    }));
    const compactEvidence = await readIngestEvidence({
      ...evidenceInput, days: [{ ...evidenceInput.days[0]!, indexes: { daily: packedIndex.replaceAll("\\", "/") } }],
    });
    expect(compactEvidence.sources).toEqual(rawEvidence.sources);
    expect(compactEvidence.history.days[0]!.files).toHaveLength(1);
    const missingEvidence = await readIngestEvidence({ ...evidenceInput, days: [] });
    expect(missingEvidence).toMatchObject({ availability: "unavailable", sources: [] });
    expect(closedObservationDays("2026-11-01T00:00:00Z", 2)).toEqual(["2026-10-30", "2026-10-31"]);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("plan completion observed after midnight stays in its original run-day partition", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-late-plan-observation-"));
  try {
    const { input, history } = await completeHistory(root, "2026-10-22T00:00:00Z");
    expect(history.sources.rows).toHaveLength(1);
    expect(history.sources.rows[0]!.identity.covers).toBe(input.fixture.date);
    expect(history.sources.rows[0]!.row).toMatchObject({
      date: input.fixture.date, run_id: input.fixture.run_id, observed_at: "2026-10-22T00:00:00Z",
      observation_phase: "plan_complete",
    });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("recorded audit rows migrate through native Parquet without invented evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-legacy-contracts-"));
  const day = "2026-10-20";
  const run = `${day}-1`;
  try {
    const migrated = new Map<string, object>();
    migrated.set("article-assessments", await migrateAuditFixture(
      root, day, run, "article-assessments",
      "../../../tests/fixtures/contracts/feed-ingest-article-assessment/one-observation.json",
      legacyAuditSchemas.ArticleAssessment, ArticleAssessmentContract));
    migrated.set("diversity", await migrateAuditFixture(
      root, day, run, "diversity",
      "../../../tests/fixtures/contracts/feed-ingest-diversity/one-observation.json",
      legacyAuditSchemas.DiversityMetric, DiversityMetricContract));
    migrated.set("source-runs", await migrateAuditFixture(
      root, day, run, "source-runs",
      "../../../tests/fixtures/contracts/feed-ingest-source-run/one-observation.json",
      legacyAuditSchemas.SourceRun, SourceRunContract));
    migrated.set("dispatches", await migrateAuditFixture(
      root, day, run, "dispatches",
      "../../../tests/fixtures/contracts/feed-ingest-dispatch/one-article.json",
      legacyAuditSchemas.Dispatch, DispatchContract));
    migrated.set("editorial-selections", await migrateAuditFixture(
      root, day, run, "editorial-selections",
      "../../../tests/fixtures/contracts/feed-ingest-editorial-selection/one-article.json",
      EditorialSelectionContract.legacyVersions[CONTRACT_VERSION].schema, EditorialSelectionContract));
    migrated.set("rejections", await migrateAuditFixture(
      root, day, run, "rejections",
      "../../../tests/fixtures/contracts/feed-ingest-rejection/empty-feed.json",
      CandidateRejectionContract.legacyVersions[CONTRACT_VERSION].schema, CandidateRejectionContract));
    expect(migrated.get("article-assessments")).toMatchObject({
      timing_basis: "unavailable", timing_at: null, age_hours: null, max_age_hours: null, diagnostics: null,
    });
    expect(migrated.get("diversity")).toMatchObject({ top_k: null });
    expect(migrated.get("editorial-selections")).toMatchObject({
      version: EditorialSelectionContract.schemaVersion, ratings: { source_reliability: null },
    });
    expect(migrated.get("source-runs")).toMatchObject({ date: day, run_id: run });
    const sourceRun = SourceRunRecordSchema.parse(migrated.get("source-runs"));
    const previousSourceRun = SourceRunContract.legacyVersions![PLANNER_EXCLUSIONS_VERSION]!;
    const { publisher_id: _publisherId, ...legacySnapshot } = sourceRun.source;
    const previousRun = previousSourceRun.schema.parse({
      ...sourceRun, version: PLANNER_EXCLUSIONS_VERSION, source: legacySnapshot,
    });
    expect(previousSourceRun.migrate(previousRun).source.publisher_id).toBeNull();
    expect(previousSourceRun.schema.safeParse({
      ...sourceRun, version: PLANNER_EXCLUSIONS_VERSION,
    }).success).toBe(false);
    const originalSource = await Bun.file(new URL(
      "../../../tests/fixtures/contracts/feed-ingest-source-run/one-observation.json", import.meta.url,
    )).json();
    for (const version of ["2026-10-22", "2026-10-22T10:05"]) {
      const previousSource = SourceRunContract.legacyVersions![version]!;
      const previousRow = previousSource.schema.parse({ ...originalSource, version });
      const previousFile = await writeRows(root, "source-runs", day, previousSource.schema,
        [previousRow], writer(run), version);
      const sourceHistory = await readWritten(root, "source-runs", day, SourceRunContract, previousFile);
      expect(sourceHistory.rows[0]!.row).toMatchObject({ version: SourceRunContract.schemaVersion });
      expect(sourceHistory.rows[0]!.row.completion_evidence?.every(entry => entry.logical === null)).toBe(true);
    }
    const { diagnostics: _diagnostics, ...currentAssessment } = ArticleAssessmentRecordSchema.parse(migrated.get("article-assessments"));
    expect(currentAssessment.source.publisher_id).toBeNull();
    const { publisher_id: _previousPublisherId, ...previousSource } = currentAssessment.source;
    const previousAssessment = { ...currentAssessment, source: previousSource };
    const assessmentSchema = ArticleAssessmentContract.legacyVersions["2026-10-22"].schema;
    const assessmentFile = await writeRows(root, "article-assessments", day, assessmentSchema,
      [assessmentSchema.parse({ ...previousAssessment, version: "2026-10-22" })], writer(run), "2026-10-22");
    const assessmentHistory = await readWritten(root, "article-assessments", day, ArticleAssessmentContract, assessmentFile);
    expect(assessmentHistory.rows[0]!.row.diagnostics).toBeNull();
    const previousRejection = CandidateRejectionContract.schema.parse(migrated.get("rejections"));
    if (previousRejection.drop_reason === "EXTRACT_FAILED" || previousRejection.drop_reason === "EXTRACT_EMPTY"
      || previousRejection.drop_reason === "ALREADY_PUBLISHED" || previousRejection.drop_reason === "SETTLED_FAILURE"
      || previousRejection.drop_reason === "BLOCKED_URL_MARKER") {
      throw new Error("Legacy rejection fixture has a current-only reason");
    }
    const {
      diagnostics: _rejectionDiagnostics, published_on: _publishedOn, failure_code: _failureCode,
      matched_url_marker: _matchedUrlMarker, ...details
    } = previousRejection.details;
    const rejectionSchema = CandidateRejectionContract.legacyVersions["2026-10-22"].schema;
    const rejectionFile = await writeRows(root, "rejections", day, rejectionSchema,
      [{ ...previousRejection, details, version: "2026-10-22" }], writer(run), "2026-10-22");
    const rejectionHistory = await readWritten(root, "rejections", day, CandidateRejectionContract, rejectionFile);
    expect(rejectionHistory.rows[0]!.row.details.diagnostics).toBeNull();
    const priorDiagnostics = PreviousHarvestDiagnosticsSchema.parse({ extract_ms: 2 });
    const priorAssessment = ArticleAssessmentContract.legacyVersions[PLANNER_EXCLUSIONS_VERSION];
    const priorAssessmentRow = { ...previousAssessment, version: PLANNER_EXCLUSIONS_VERSION, diagnostics: priorDiagnostics };
    const priorAssessmentFile = await writeRows(root, "article-assessments", day, priorAssessment.schema,
      [priorAssessmentRow], writer(run), PLANNER_EXCLUSIONS_VERSION);
    const readAssessment = await readWritten(root, "article-assessments", day, ArticleAssessmentContract, priorAssessmentFile);
    expect(readAssessment.rows[0]!.row).toMatchObject({
      version: ArticleAssessmentContract.schemaVersion, diagnostics: { extract_ms: 2, quality: null },
    });
    expect(priorAssessment.schema.safeParse({
      ...priorAssessmentRow, diagnostics: { ...priorDiagnostics, quality: null },
    }).success).toBe(false);
    const priorRejection = CandidateRejectionContract.legacyVersions[PLANNER_EXCLUSIONS_VERSION];
    const priorRejectionFile = await writeRows(root, "rejections", day, priorRejection.schema,
      [{ ...previousRejection, version: PLANNER_EXCLUSIONS_VERSION,
        details: { ...previousRejection.details, diagnostics: priorDiagnostics } }], writer(run), PLANNER_EXCLUSIONS_VERSION);
    const readRejection = await readWritten(root, "rejections", day, CandidateRejectionContract, priorRejectionFile);
    expect(readRejection.rows[0]!.row).toMatchObject({
      version: EXTRACTION_QUALITY_VERSION, details: { diagnostics: { extract_ms: 2, quality: null } },
    });
    expect(migrated.get("dispatches")).toHaveProperty("content");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("native monthly and yearly precedence reads only the requested day's original rows", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-coarse-periods-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const raw = await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections);
    const original = raw.rows[0]!;
    const otherDay = "2026-10-20";
    const neighbor = await writeRows(root, "editorial-selections", otherDay, EditorialSelectionRowSchema,
      [{ ...original.row, date: otherDay }], writer(input.fixture.run_id), selectionContract.schemaVersion);
    const neighborRows = await readWritten(root, "editorial-selections", otherDay, selectionContract, neighbor);
    const indexes: Partial<Record<"daily" | "monthly" | "yearly", string>> = {};
    const daily = await compactSelections(root, input, raw.rows, "daily");
    indexes.daily = daily.indexPath;
    for (const period of ["monthly", "yearly"] as const) {
      const compact = await compactSelections(root, input, [...raw.rows, ...neighborRows.rows], period);
      indexes[period] = compact.indexPath;
      const current = await readLedgerDay({
        ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract, indexes,
        rawFiles: input.persisted.selections.files.map(file => join(root, file.path)),
      });
      expect(current.tier).toBe(period);
      expect(current.rows).toEqual([original]);
      expect(current.files[0]!.envelope.identity.attempt).toBe(9);
      expect(current.rows[0]!.identity.attempt).toBe(1);
      expect(current.rows[0]!.identity.shard).toBe(0);
      expect(current.rows[0]!.identity.unit_id).toBe(original.identity.unit_id);
      expect(current.files[0]!.rows).toHaveLength(2);
      expect(current.notices.some(notice => notice.startsWith("overlapping-periods"))).toBe(true);
    }
    const rawName = basename(input.persisted.selections.files[0]!.path);
    const stale = `raw/feed-health/2025/01/01/${rawName}`;
    const recent = `raw/feed-health/2026/02/12/${rawName}`;
    const discovery = resolveHealthInventory({
      ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31,
      inventory: { version: "2026-10-03T13:33", entries: [stale, recent].map(path => ({
        root: "state", path, bytes: 1, items: 0,
      })) },
      compact: {
        yearly: { version: "2026-10-07", ledger: "feed-health", period: "yearly",
          entries: [{ covers: "2025", rows: 1, bytes: 1 }] },
        monthly: { version: "2026-10-07", ledger: "feed-health", period: "monthly",
          entries: [{ covers: "2026-01", rows: 1, bytes: 1 }] },
        daily: { version: "2026-10-07", ledger: "feed-health", period: "daily",
          entries: [{ covers: "2026-02-01", rows: 1, bytes: 1 }] },
      },
    });
    expect(discovery.inputs.map(day => day.day)).toEqual([
      ...Array.from({ length: 29 }, (_, index) => `2026-01-${String(index + 3).padStart(2, "0")}`),
      "2026-02-01", "2026-02-12",
    ]);
    expect(discovery.files).toContain("state/compact/feed-health/monthly/2026/01.parquet");
    expect(discovery.files).toContain(`state/${recent}`);
    expect(discovery.files).not.toContain(`state/${stale}`);
    expect(discovery.inventory_complete).toBe(false);
    for (const inventory of [
      { version: "2099-01-01", entries: [] },
      { version: "2026-10-03T13:33", entries: [{ root: "state", path: "../escaped.parquet", bytes: 1, items: 0 }] },
      { version: "2026-10-03T13:33", entries: [{ root: "state", path: "raw/feed-health/2026/02/12/not-a-uuid.parquet", bytes: 1, items: 0 }] },
    ]) expect(() => resolveHealthInventory({
      ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31, inventory, compact: {},
    })).toThrow();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("named empty, lost, expired and missing periods never fall through to leftover raw files", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-states-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const indexPath = join(root, "compact", "feed-ingest-plan", "editorial-selections", "index", "daily.json");
    await mkdir(dirname(indexPath), { recursive: true });
    const read = () => readLedgerDay({
      ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: indexPath }, rawFiles: input.persisted.selections.files.map(file => join(root, file.path)),
    });
    const base = { version: "2026-10-07", ledger: "editorial-selections", period: "daily" };
    for (const state of ["empty", "lost"] as const) {
      await writeFile(indexPath, JSON.stringify({ ...base, entries: [{ covers: input.fixture.date, rows: 0, bytes: 0, state }] }));
      const held = await read();
      expect(held.status).toBe(state);
      expect(held.files).toEqual([]);
    }
    await writeFile(indexPath, JSON.stringify({ ...base, entries: [{ covers: input.fixture.date, rows: 1, bytes: 100, state: "packed" }] }));
    expect((await read()).status).toBe("missing");
    await rm(indexPath);
    expect((await read()).notices).toContain("index-missing:daily");
    expect((await read()).status).toBe("rows");
    expect((await readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract })).status).toBe("missing");
    const expired = join(dirname(indexPath), "yearly.json");
    await writeFile(expired, JSON.stringify({ ...base, period: "yearly", expired_through: "2026", entries: [] }));
    expect((await readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { yearly: expired }, rawFiles: input.persisted.selections.files.map(file => join(root, file.path)) })).status).toBe("missing");
    const nativeRaw = `raw/feed-health/${input.fixture.date.replaceAll("-", "/")}/${basename(input.persisted.selections.files[0]!.path)}`;
    for (const state of ["empty", "lost"] as const) {
      const discovery = resolveHealthInventory({
        ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31,
        inventory: { version: "2026-10-03T13:33",
          entries: [{ root: "state", path: nativeRaw, bytes: 1, items: 0 }] },
        compact: { daily: { version: "2026-10-07", ledger: "feed-health", period: "daily",
          entries: [{ covers: input.fixture.date, rows: 0, bytes: 0, state }] } },
      });
      expect(discovery.inputs).toEqual([]);
      expect(discovery.files).not.toContain(`state/${nativeRaw}`);
      expect(discovery.notices).toContain(`feed-inventory:covered-raw-day-unconfirmed:feed-health:${input.fixture.date}`);
    }
    const absent = resolveHealthInventory({
      ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31, inventory: undefined, compact: {},
    });
    expect(absent.inputs).toEqual([]);
    expect(absent.inventory_complete).toBe(false);
    expect(absent.notices).toContain("feed-inventory:publication-inventory-missing:feed-health");
    expect(absent.notices).toContain("feed-inventory:raw-census-unproven:feed-health");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("one named raw listing verifies its ordered filename digest, sizes and missing-file evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-raw-index-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const path = join(root, input.persisted.selections.files[0]!.path);
    const indexPath = join(dirname(path), "index.json");
    const names = [basename(path)];
    const index = {
      version: "2026-10-03", ledger: "editorial-selections", date: input.fixture.date,
      files: names, content_sha256: createHash("sha256").update(names.join("\n")).digest("hex"),
      bytes: [(await stat(path)).size], listed_at: input.fixture.observed_at,
    };
    const read = () => readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract, rawIndex: indexPath });
    await writeFile(indexPath, JSON.stringify(index));
    expect((await read()).rows).toHaveLength(1);
    await writeFile(indexPath, JSON.stringify({ ...index, content_sha256: "0".repeat(64) }));
    await expect(read()).rejects.toThrow("filename digest");
    await writeFile(indexPath, JSON.stringify({ ...index, bytes: [1] }));
    await expect(read()).rejects.toThrow("byte size");
    await writeFile(indexPath, JSON.stringify(index));
    await rm(path);
    expect((await read()).status).toBe("missing");
    await writeFile(indexPath, JSON.stringify({ ...index, files: [], bytes: [], content_sha256: createHash("sha256").update("").digest("hex") }));
    expect((await read()).status).toBe("empty");
    const publisherRoot = join(root, "publisher");
    const stateRoot = join(publisherRoot, "state");
    const held = await fixtureInput(stateRoot, { count: 1 });
    const selected = {
      ...held.curation.rows[0]!,
      source: { ...held.curation.rows[0]!.source, publisher_id: "recorded-publisher" },
    };
    const day = held.fixture.date;
    const owner = writer(held.fixture.run_id);
    const identity = { date: day, run_id: owner.run_id, item_id: "recorded-item-01",
      url_key: selected.url_key, source_id: selected.source_id, stage: "publish" as const, outcome: "ok" as const };
    const health = await writeRows(stateRoot, "item-health", day, ItemHealthPublicationSchema,
      [identity, identity, { ...identity, stage: "extract" }], owner, ITEM_HEALTH_ROW_SCHEMA_VERSION);
    const publication = await writeRows(stateRoot, "published", day, PublishedRowSchema,
      [{ version: PUBLISHED_ROW_SCHEMA_VERSION, published_on: day, url_key: selected.url_key, item_id: identity.item_id }],
      owner, PUBLISHED_ROW_SCHEMA_VERSION);
    const snapshots = await writeRows(stateRoot, "editorial-selections", day, EditorialSelectionRowSchema,
      [selected], owner, EditorialSelectionContract.schemaVersion);
    const writeIndex = async (files: PersistLedgerResult["files"]) => {
      const file = files[0]!;
      const path = join(stateRoot, file.path);
      const names = [basename(path)];
      await writeFile(join(dirname(path), "index.json"), JSON.stringify({
        version: "2026-10-03", ledger: "editorial-selections", date: day, files: names,
        content_sha256: createHash("sha256").update(names.join("\n")).digest("hex"),
        bytes: [(await stat(path)).size], listed_at: held.fixture.observed_at,
      }));
    };
    await writeIndex(snapshots.files);
    const localFiles = (files: PersistLedgerResult["files"]) => files.map(file => `state/${file.path}`);
    const request = {
      root: publisherRoot, day, published: registration("published"), item_health: registration("item-health"),
      selections: registration("editorial-selections"),
      published_days: [{ day, raw_files: localFiles(publication.files) }],
      health_days: [{ day, raw_files: localFiles(health.files) }],
    };
    const counted = await readPublisherPublication(request);
    expect(counted.availability).toBe("available");
    expect(counted.counts.get("recorded-publisher")).toBe(1);
    expect(counted.gaps).toEqual([]);
    const native = await readWritten(stateRoot, "editorial-selections", day, selectionContract, snapshots);
    const compact = await compactSelections(stateRoot, held, native.rows, "daily");
    expect((await readPublisherPublication(request)).counts).toEqual(counted.counts);
    await rm(compact.path);
    await writeFile(compact.indexPath, JSON.stringify({
      ...compact.index, entries: [{ covers: day, rows: 0, bytes: 0, state: "lost" }],
    }));
    expect((await readPublisherPublication(request)).availability).toBe("unavailable");
    await rm(compact.indexPath);
    const differentRun = await writeRows(stateRoot, "editorial-selections", day, EditorialSelectionRowSchema,
      [selected], { ...owner, run_id: `${day}-999999` }, selectionContract.schemaVersion);
    await writeIndex(differentRun.files);
    expect((await readPublisherPublication(request)).gaps).toContain("recorded_publisher_unavailable");
    const previousDay = new Date(Date.parse(`${day}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10);
    await writeRows(stateRoot, "editorial-selections", previousDay, EditorialSelectionRowSchema,
      [{ ...selected, date: previousDay }], { ...owner, run_id: `${previousDay}-1` }, selectionContract.schemaVersion);
    await rm(join(dirname(join(stateRoot, differentRun.files[0]!.path)), "index.json"));
    const crossDay = await readPublisherPublication(request);
    expect(crossDay.availability).toBe("unavailable");
    expect(crossDay.gaps).toContain("recorded_publisher_unavailable");
    for (const snapshot of [
      { ...selected, source: { ...selected.source, publisher_id: null } },
      selected,
    ]) {
      const rows = snapshot.source.publisher_id === null ? [snapshot]
        : [snapshot, { ...snapshot, source: { ...snapshot.source, publisher_id: "conflicting-publisher" } }];
      const ambiguous = await writeRows(stateRoot, "editorial-selections", day, EditorialSelectionRowSchema,
        rows, { ...owner, attempt: 2 }, selectionContract.schemaVersion);
      await writeIndex(ambiguous.files);
      const gap = await readPublisherPublication(request);
      expect(gap.availability).toBe("unavailable");
      expect(gap.counts.size).toBe(0);
      expect(gap.gaps).toContain("recorded_publisher_unavailable");
    }
    const empty = await readPublisherPublication({ ...request, published_days: [{ day, raw_files: [] }] });
    expect(empty.availability).toBe("available");
    expect(empty.counts.size).toBe(0);
    const missing = await readPublisherPublication({ ...request, published_days: [] });
    expect(missing.availability).toBe("unavailable");
    const invalidIndex = join(publisherRoot, "invalid-publication-index.json");
    for (const contents of ["{", JSON.stringify({ version: "not-a-version" })]) {
      await writeFile(invalidIndex, contents);
      const invalid = await readPublisherPublication({
        ...request, published_days: [{ day, raw_index: "invalid-publication-index.json" }],
      });
      expect(invalid.availability).toBe("unavailable");
      expect(invalid.counts.size).toBe(0);
      expect(invalid.gaps).toEqual(["invalid_publication_history"]);
    }
    expect(classifyPublicationHistoryError(new TypeError("unexpected programming error"))).toBeNull();
    expect(classifyPublicationHistoryError(new Error("unexpected programming error"))).toBeNull();
    expect(classifyPublicationHistoryError(new SyntaxError("unexpected programming error"))).toBeNull();
    expect(classifyPublicationHistoryError("unexpected non-error")).toBeNull();
    expect(classifyPublicationHistoryError(new LedgerHistoryReadError("renamed integrity diagnostic")))
      .toBe("renamed integrity diagnostic");
    await writeIndex(snapshots.files);
    await writeFile(join(dirname(join(stateRoot, snapshots.files[0]!.path)), "index.json"), "{");
    expect((await readPublisherPublication(request)).gaps).toEqual(["invalid_publication_history"]);
    for (const bytes of [new Uint8Array([1, 2, 3]), new Uint8Array(20)]) {
      await writeFile(join(stateRoot, publication.files[0]!.path), bytes);
      await expect(readLedgerDay({
        ledger: "published", day, contract: { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION },
        rawFiles: publication.files.map(file => join(stateRoot, file.path)),
      })).rejects.toThrow();
      const corrupt = await readPublisherPublication(request);
      expect(corrupt.availability).toBe("unavailable");
      expect(corrupt.counts.size).toBe(0);
      expect(corrupt.gaps).toEqual(["invalid_publication_history"]);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 60_000);

test("native digest tampering, wrong ledger, schema, index counts and raw identity are rejected", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-integrity-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const file = input.persisted.selections.files[0]!;
    const path = join(root, file.path);
    const raw = await readLedgerParquet(path, "editorial-selections", selectionContract);
    await expect(readLedgerParquet(path, "dispatches", selectionContract)).rejects.toThrow("Parquet ledger");
    await expect(readLedgerParquet(path, "editorial-selections", { ...selectionContract, schemaVersion: "2026-10-19" })).rejects.toThrow("Parquet row schema version");
    const compact = await compactSelections(root, input, raw.rows, "daily");
    await writeFile(compact.indexPath, JSON.stringify({ ...compact.index, entries: [{ ...compact.index.entries[0], rows: 2 }] }));
    await expect(readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: compact.indexPath } })).rejects.toThrow("row count or byte size");
    await writeFile(compact.indexPath, JSON.stringify({ ...compact.index, entries: [{ ...compact.index.entries[0], state: "empty", rows: 0, bytes: 0 }] }));
    await expect(readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: compact.indexPath } })).rejects.toThrow("declares no file");
    const bytes = await readFile(path);
    const metadata = readMetadata(bytes);
    const footer = metadata.fileMetadata();
    const pairs = new Map<string, string>(footer.keyValueMetadata());
    footer.free();
    metadata.free();
    pairs.set("content_sha256", "0".repeat(64));
    const table = tableFromIPC(readParquet(bytes).intoIPCStream());
    const originalDigest = pairs.get("content_sha256")!;
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(table, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "editorial-selections", selectionContract)).rejects.toThrow("content digest");
    pairs.set("content_sha256", originalDigest);
    pairs.set("attempt", "02");
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(table, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "editorial-selections", selectionContract)).rejects.toThrow("identifier differs");
    pairs.set("attempt", "01");
    const changedRow = { ...raw.rows[0]!.identity, ...raw.rows[0]!.row, shard: 7 };
    pairs.set("content_sha256", digestRows([changedRow], appendIdentityColumns(describeObjectSchema(EditorialSelectionRowSchema).fields)));
    const changedTable = table.setChild("shard", vectorFromArray([7n], new Int64()));
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(changedTable, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "editorial-selections", selectionContract)).rejects.toThrow("Raw row identity");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("complete original files beat a newer partial retry and replay exact original selected text", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-attempts-"));
  try {
    const { input, source, sourceWritten, history, packed } = await completeHistory(root);
    const complete = selectCompleteAttempt(history);
    expect(complete.selected?.attempt).toBe(1);
    expect(readHistoricalSelections(complete.selected!).map(article => article.content)).toEqual(packed.dispatches.map(row => row.content));
    const partial = await writeRows(root, "source-runs", input.fixture.date, SourceRunRecordSchema,
      [{ ...source(2), expected_source_count: 2 }], writer(input.fixture.run_id, 2), SourceRunContract.schemaVersion);
    const sources = await readWritten(root, "source-runs", input.fixture.date,
      SourceRunContract,
      { status: "written", files: [...sourceWritten.files, ...partial.files] });
    const resolution = selectCompleteAttempt({ ...history, sources });
    expect(resolution.selected?.attempt).toBe(1);
    expect(resolution.findings.find(finding => finding.attempt === 2)?.status).toBe("incomplete");
    const zero = await writeRows(root, "source-runs", input.fixture.date, SourceRunRecordSchema,
      [source(3, true)], writer(input.fixture.run_id, 3), SourceRunContract.schemaVersion);
    const zeroSources = await readWritten(root, "source-runs", input.fixture.date,
      SourceRunContract,
      { status: "written", files: [...sourceWritten.files, ...partial.files, ...zero.files] });
    const empty = selectCompleteAttempt({ ...history, sources: zeroSources });
    expect(empty.selected?.attempt).toBe(3);
    expect(readHistoricalSelections(empty.selected!)).toEqual([]);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("compacted original-file proof is explicitly unverifiable rather than a count-shaped success", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-proof-gap-"));
  try {
    const { input, history } = await completeHistory(root);
    const raw = history.ledgers["editorial-selections"];
    const selections = raw.rows.map(held => ({ identity: held.identity, row: EditorialSelectionRowSchema.parse(held.row) }));
    const compact = await compactSelections(root, input, selections, "monthly");
    const packed = await readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { monthly: compact.indexPath } });
    const resolution = selectCompleteAttempt({ ...history, ledgers: { ...history.ledgers, "editorial-selections": packed } });
    expect(packed.rows).toEqual(selections);
    expect(resolution.selected).toBeNull();
    expect(resolution.findings[0]!.status).toBe("unverifiable");
    expect(resolution.findings[0]!.reason).toContain("original raw-file membership");
    const source = history.sources.rows[0]!;
    const altered = SourceRunRecordSchema.parse({
      ...source.row, completion_evidence: source.row.completion_evidence!.map(item => ({
        ...item, files: item.files.map(file => ({ ...file, content_sha256: "0".repeat(64) })),
      })),
    });
    const unproved = selectCompleteAttempt({ ...history, sources: { ...history.sources, rows: [{ ...source, row: altered }] } });
    expect(unproved.selected).toBeNull();
    expect(unproved.findings[0]!.reason).toContain("commitment differs");
  } finally { await rm(root, { recursive: true, force: true }); }
});
