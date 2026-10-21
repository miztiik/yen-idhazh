/** Reads real writer output through WASM and Arrow against bounded fixtures. */
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { describe, expect, test } from "bun:test";
import { tableFromIPC } from "apache-arrow";
import {
  ArticleAssessmentRecordSchema,
  DiversityMetricRowSchema,
  FileEnvelopeSchema,
  FOOTER_METADATA_KEYS,
  OPTIONAL_FOOTER_METADATA_KEYS,
  FeedIngestDispatchSchema,
  RowIdentitySchema,
  WriterIdentitySchema,
  validateEnvelopeContainer,
} from "@idhazh/common-contracts";
import type { FileEnvelope } from "@idhazh/common-contracts";
import { readMetadata, readParquet } from "parquet-wasm/esm";
import type { Field } from "apache-arrow";
import { z } from "zod";
import { createUnitId, persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings, PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { appendIdentityColumns, describeObjectSchema } from "../src/row-schema";
import { digestRows, serializeRowsBytes } from "../src/parquet/row-digest";
import { buildArrowTable } from "../src/parquet/arrow-builder";
import { initializeParquetWasm } from "../src/parquet/wasm-serializer";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(packageRoot, "..", "..");
const compression: LedgerSettings = {
  format: "parquet",
  compression_raw: "snappy",
  compression_compact: "zstd",
};

const writerContext = WriterIdentitySchema.parse({
  run_id: "2026-10-21-123",
  attempt: 3,
  job: null,
  pipeline_name: "plan",
  task_name: "seal-article-ledger",
  shard: 2,
  producer: "tests.ledger-file-writer",
  git_sha: "a".repeat(40),
});

function registration(ledger: string, lifecycleStatus: LedgerRegistration["lifecycle_status"] = "active"): LedgerRegistration {
  return {
    name: ledger,
    family: "feed-ingest-plan",
    grain: "raw-and-compact",
    lifecycle_status: lifecycleStatus,
    prefix: ["feed-ingest-plan", ledger],
  };
}

function policy() {
  return {
    policy_version: "feed-ingest-plan-test",
    config_sha256: "b".repeat(64),
    min_words_article: 180,
    min_words_abstract: 60,
    max_age_hours: 1e20,
    recency_half_life_hours: 1e-7,
    recency_weight: 1.0,
    source_authority_weight: 1.0,
    base_source_allowance: 3,
    bonus_uncovered_event_cluster: 0,
    bonus_underrepresented_vertical: 0,
    bonus_unique_evidence: 0,
    lambda_source: 0.0,
    lambda_source_kind: 0.0,
    lambda_domain: 0.0,
    lambda_vertical: 0.0,
    lambda_desk: 0.0,
    lambda_lens: 0.0,
    lambda_event_type: 0.0,
    lambda_event_cluster: 0.0,
    lambda_entity: 0.0,
    lambda_coverage: 0.0,
  };
}

function assessment(day: string, categories: string[] | null) {
  const observedAt = `${day}T10:00:00Z`;
  return ArticleAssessmentRecordSchema.parse({
    date: day,
    correlation_id: "2026-10-21-123",
    candidate_id: "c".repeat(64),
    source_id: "fixture-source",
    source: {
      source_id: "fixture-source",
      feed_url: "https://example.org/feed.xml",
      title: "Caf\u00e9 \u6771\u4eac",
      vertical: "world",
      kind: "reporting",
      tier: 1,
      form: "article",
      status: "active",
      weight: 1.0,
      applied_tier_weight: 1e-7,
    },
    labels: {
      assigned_desk: "world",
      lenses: ["world"],
      event_types: ["release"],
      event_cluster_id: null,
      entities: [],
      origin: "fixture",
      matcher_version: "fixture-1",
    },
    canonical_url: null,
    url_key: null,
    stage: "harvest-feeds",
    decision: "admitted",
    reason: null,
    observed_at: observedAt,
    policy: policy(),
    effective_published_at: observedAt,
    publication_clock: "published_at",
    age_hours: -0.0,
    max_age_hours: 1e20,
    extracted_word_count: 180,
    source_form: "article",
    extraction_outcome: "success",
    word_threshold: 180,
    author_present: false,
    publisher_identity: "\u00c9diteur",
    attribution_status: "available",
    paywall: categories === null ? null : false,
    categories,
    required_fields_present: categories === null ? null : true,
    suitability_status: categories === null ? "unavailable" : "available",
    informative_verdict_status: "not_assessed",
    informative_verdict: null,
    informative_evaluator_version: null,
    suitability_verdict_status: "not_assessed",
    suitability_verdict: null,
    suitability_evaluator_version: null,
    score_evidence: null,
    score_evidence_status: "not_assessed",
  });
}

function diversity() {
  return DiversityMetricRowSchema.parse({
    date: "2026-10-21",
    correlation_id: "2026-10-21-123",
    run_id: "2026-10-21-123",
    metric: "lost_diversity_by_stage",
    basis: "stage",
    as_of: "2026-10-21T10:00:00Z",
    window_start: null,
    window_end: null,
    dimension: "source",
    stage: "selection",
    window_days: null,
    dimension_value: null,
    value: -0.0,
    unit: "source_difference",
    before_value: 1.0,
    after_value: 1.0,
    numerator: null,
    denominator: null,
    item_count: null,
    source_count: null,
    history_coverage_days: null,
    history_required_days: null,
    algorithm_version: "fixture-1",
    config_sha256: "d".repeat(64),
    availability: "available",
    unavailable_reason: null,
    top_k: null,
  });
}

function normalizeArrowValue(value: unknown): unknown {
  if (typeof value === "bigint") return Number(value);
  if (Array.isArray(value)) return value.map(normalizeArrowValue);
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") {
    return normalizeArrowValue(value.toJSON());
  }
  return Object.fromEntries(
    Object.entries(value).map(([key, child]) => [key, normalizeArrowValue(child)]),
  );
}

function requiredFooterValue(metadata: ReadonlyMap<string, string>, key: string): string {
  const value = metadata.get(key);
  if (value === undefined) throw new Error(`Parquet footer is missing ${key}`);
  return value;
}

function parseFooterEnvelope(metadata: ReadonlyMap<string, string>) {
  return validateEnvelopeContainer(FileEnvelopeSchema.parse({
    version: requiredFooterValue(metadata, "envelope_version"),
    row_schema_version: requiredFooterValue(metadata, "schema_version"),
    tier: requiredFooterValue(metadata, "tier"),
    ledger: requiredFooterValue(metadata, "ledger"),
    covers: requiredFooterValue(metadata, "covers"),
    period: metadata.get("period") ?? null,
    written_at_ms: Number(requiredFooterValue(metadata, "written_at_ms")),
    identity: {
      run_id: requiredFooterValue(metadata, "run_id"),
      attempt: Number(requiredFooterValue(metadata, "attempt")),
      job: metadata.get("job") ?? null,
      pipeline_name: metadata.get("pipeline_name") ?? null,
      task_name: metadata.get("task_name") ?? null,
      shard: Number(requiredFooterValue(metadata, "shard")),
      producer: requiredFooterValue(metadata, "producer"),
      git_sha: requiredFooterValue(metadata, "git_sha"),
    },
    unit_id: requiredFooterValue(metadata, "unit_id"),
    file_id: requiredFooterValue(metadata, "file_id"),
    content_sha256: requiredFooterValue(metadata, "content_sha256"),
    writer: requiredFooterValue(metadata, "writer"),
    writer_version: requiredFooterValue(metadata, "writer_version"),
    compression: requiredFooterValue(metadata, "compression"),
    built_from: metadata.has("built_from") ? Number(metadata.get("built_from")) : null,
  }), "parquet");
}

async function readActualParquet(path: string) {
  await initializeParquetWasm();
  const bytes = await readFile(path);
  const metadata = readMetadata(bytes);
  const fileMetadata = metadata.fileMetadata();
  const footer = new Map(
    [...fileMetadata.keyValueMetadata()].map(([key, value]) => [String(key), String(value)]),
  );
  const footerRowCount = fileMetadata.numRows();
  metadata.free();

  const wasmTable = readParquet(bytes);
  const table = tableFromIPC(wasmTable.intoIPCStream());
  const rows = table.toArray().map((row) =>
    normalizeArrowValue(row) as Record<string, unknown>,
  );
  return {
    footer,
    footerRowCount,
    rows,
    fields: table.schema.fields,
  };
}

async function checkParquetReadback<T extends object>(
  ledger: FileEnvelope["ledger"],
  root: string,
  files: readonly PersistedLedgerFile[],
  schema: z.ZodType<T>,
) {
  const columns = appendIdentityColumns(describeObjectSchema(schema).fields);
  const expectedSchema = buildArrowTable(columns, []).schema;
  const expectedKeys = [
    ...FOOTER_METADATA_KEYS.filter((key) =>
    !OPTIONAL_FOOTER_METADATA_KEYS.includes(key as typeof OPTIONAL_FOOTER_METADATA_KEYS[number]),
    ),
    "ARROW:schema",
  ];
  const checkedFiles = [];
  for (const file of files) {
    const path = resolve(root, ...file.path.split("/"));
    const actual = await readActualParquet(path);
    const envelope = parseFooterEnvelope(actual.footer);
    const actualKeys = [...actual.footer.keys()].sort();
    const declaredKeys = [
      ...expectedKeys,
      ...OPTIONAL_FOOTER_METADATA_KEYS.filter((key) => actual.footer.has(key)),
    ].sort();
    expect(actualKeys).toEqual(declaredKeys);
    expect(actual.fields.map((field) => [field.name, field.type.toString(), field.nullable]))
      .toEqual(expectedSchema.fields.map((field: Field) => [
        field.name,
        field.type.toString(),
        field.nullable,
      ]));
    expect(actual.rows.length).toBe(actual.footerRowCount);
    expect(actual.footerRowCount).toBe(file.row_count);
    expect(envelope.ledger).toBe(ledger);
    expect(envelope.file_id).toBe(file.file_id);
    expect(envelope.unit_id).toBe(file.unit_id);
    expect(digestRows(actual.rows, columns)).toBe(envelope.content_sha256);
    checkedFiles.push({
      covers: envelope.covers,
      tier: envelope.tier,
      period: envelope.period,
      row_count: actual.footerRowCount,
      content_sha256: envelope.content_sha256,
      identity: envelope.identity,
      rows: actual.rows,
    });
  }
  return { files: checkedFiles };
}

type LedgerRegistryFile = {
  families: {
    name: string;
    lifecycle_status: LedgerRegistration["lifecycle_status"];
    ledgers: { name: string; grain: string; prefix: string[] }[];
  }[];
};

async function registeredEntry(ledger: string): Promise<LedgerRegistration> {
  const registry = JSON.parse(
    await readFile(join(repositoryRoot, "config", "ledgers.json"), "utf8"),
  ) as LedgerRegistryFile;
  for (const family of registry.families) {
    const entry = family.ledgers.find((candidate) => candidate.name === ledger);
    if (entry !== undefined) {
      if (entry.grain !== "raw-and-compact") throw new Error(`${ledger} fixture is not a raw-and-compact ledger`);
      return {
        name: entry.name,
        family: family.name,
        grain: "raw-and-compact",
        lifecycle_status: family.lifecycle_status,
        prefix: entry.prefix,
      };
    }
  }
  throw new Error(`${ledger} is absent from the named ledger registry`);
}

async function readLedgerFixture(name: string): Promise<unknown> {
  return JSON.parse(
    await readFile(join(repositoryRoot, "tests", "fixtures", "ledger-file-writer", name), "utf8"),
  );
}

async function withOutputRoot<T>(run: (root: string) => Promise<T>): Promise<T> {
  const root = await mkdtemp(join(tmpdir(), "ledger-file-writer-"));
  try {
    return await run(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

describe("ledger Parquet readback", () => {
  test("serializes the recorded canonical compatibility vector", () => {
    const schema = z.object({
      big: z.number(),
      float_one: z.number(),
      list: z.array(z.string()),
      maybe: z.string().nullable(),
      negative_zero: z.number(),
      nested: z.object({
        items: z.array(z.string()),
        value: z.number().int().nullable(),
      }),
      small: z.number(),
      "z-unicode": z.string(),
    });
    const row = {
      big: 1e20,
      float_one: 1.0,
      list: ["na\u00efve", "\u6771\u4eac"],
      maybe: null,
      negative_zero: -0.0,
      nested: { items: ["\u00c9diteur"], value: null },
      small: 1e-7,
      "z-unicode": "Caf\u00e9 \u6771\u4eac",
    };
    const fields = describeObjectSchema(schema).fields;
    const bytes = serializeRowsBytes([row], fields);
    expect(bytes.toString("ascii")).toBe(
      "{\"big\":1e+20,\"float_one\":1.0,\"list\":[\"na\\u00efve\",\"\\u6771\\u4eac\"],\"maybe\":null,\"negative_zero\":-0.0,\"nested\":{\"items\":[\"\\u00c9diteur\"],\"value\":null},\"small\":1e-07,\"z-unicode\":\"Caf\\u00e9 \\u6771\\u4eac\"}\n",
    );
    expect(digestRows([row], fields)).toBe(
      "9514b5931807b27fbaf18c43c7371ada4bab45fd745ff4b3564dad032cdad67e",
    );
  });

  test("writes raw day groups and compact rows through one registered contract", async () => {
    await withOutputRoot(async (root) => {
      const rows = [assessment("2026-10-20", ["na\u00efve", "\u6771\u4eac"]), assessment("2026-10-21", null)];
      const raw = await persistLedger({
        ledger: "article-assessments",
        rowContract: { schema: ArticleAssessmentRecordSchema, schemaVersion: "2026-10-20" },
        rows,
        outputRoot: root,
        period: { tier: "raw", covers: "2026-10-21" },
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("article-assessments"),
      });
      expect(raw.status).toBe("written");
      if (raw.status !== "written") throw new Error("raw rows were not written");
      expect(raw.files.map((file) => file.covers)).toEqual(["2026-10-20", "2026-10-21"]);

      const rawReadback = await checkParquetReadback(
        "article-assessments",
        root,
        raw.files,
        ArticleAssessmentRecordSchema,
      );
      expect(rawReadback.files.map((file) => file.row_count)).toEqual([1, 1]);
      expect(rawReadback.files.every((file) => file.tier === "raw" && file.period === null)).toBe(true);
      for (const file of rawReadback.files) {
        const expectedRow = rows.find((row) => row.date === file.covers);
        if (expectedRow === undefined) throw new Error(`no input row covers ${file.covers}`);
        expect(file.rows[0]).toMatchObject(expectedRow);
      }

      const identities = raw.files.map((file) => RowIdentitySchema.parse({
        ledger: "article-assessments",
        covers: file.covers,
        run_id: writerContext.run_id,
        attempt: writerContext.attempt,
        job: writerContext.job,
        pipeline_name: writerContext.pipeline_name,
        task_name: writerContext.task_name,
        shard: writerContext.shard,
        unit_id: file.unit_id,
      }));
      const compactRows = rows.map((row, index) => {
        const identity = identities[index];
        if (identity === undefined) throw new Error(`raw writer omitted identity ${index}`);
        return { identity, row };
      });
      const compact = await persistLedger({
        ledger: "article-assessments",
        rowContract: { schema: ArticleAssessmentRecordSchema, schemaVersion: "2026-10-20" },
        rows: compactRows,
        outputRoot: root,
        period: { tier: "compact", period: "monthly", covers: "2026-10", builtFrom: raw.files.length },
        writerContext: WriterIdentitySchema.parse({
          run_id: "2026-10-21-456",
          attempt: 9,
          job: "assemble",
          pipeline_name: null,
          task_name: null,
          shard: 7,
          producer: "tests.ledger-compactor",
          git_sha: "b".repeat(40),
        }),
        ledgerSettings: compression,
        registryEntry: registration("article-assessments"),
      });
      expect(compact.status).toBe("written");
      if (compact.status !== "written") throw new Error("compact rows were not written");
      const compactReadback = await checkParquetReadback(
        "article-assessments",
        root,
        compact.files,
        ArticleAssessmentRecordSchema,
      );
      expect(compactReadback.files[0]?.row_count).toBe(2);
      expect(compactReadback.files[0]?.tier).toBe("compact");
      expect(compactReadback.files[0]?.period).toBe("monthly");
      expect(compactReadback.files[0]?.rows).toEqual(rawReadback.files.flatMap((file) => file.rows));
      expect(compactReadback.files[0]?.identity).toMatchObject({
        run_id: "2026-10-21-456",
        job: "assemble",
        shard: 7,
      });
    });
  });

  test("writes a second registered contract and preserves its original compact identity", async () => {
    await withOutputRoot(async (root) => {
      const row = diversity();
      const raw = await persistLedger({
        ledger: "diversity",
        rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
        rows: [row],
        outputRoot: root,
        period: { tier: "raw", covers: row.date },
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("diversity"),
      });
      if (raw.status !== "written") throw new Error("diversity row was not written");
      const rawReadback = await checkParquetReadback(
        "diversity",
        root,
        raw.files,
        DiversityMetricRowSchema,
      );
      expect(rawReadback.files[0]?.rows[0]).toMatchObject(row);
      const rawFile = raw.files[0];
      if (rawFile === undefined) throw new Error("raw writer omitted its file metadata");
      const identity = RowIdentitySchema.parse({
        ledger: "diversity",
        covers: rawFile.covers,
        run_id: writerContext.run_id,
        attempt: writerContext.attempt,
        job: writerContext.job,
        pipeline_name: writerContext.pipeline_name,
        task_name: writerContext.task_name,
        shard: writerContext.shard,
        unit_id: rawFile.unit_id,
      });

      const compact = await persistLedger({
        ledger: "diversity",
        rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
        rows: [{ identity, row }],
        outputRoot: root,
        period: { tier: "compact", period: "daily", covers: row.date, builtFrom: 1 },
        writerContext: WriterIdentitySchema.parse({
          run_id: "2026-10-21-457",
          attempt: 8,
          job: "assemble",
          pipeline_name: null,
          task_name: null,
          shard: 6,
          producer: "tests.ledger-compactor",
          git_sha: "b".repeat(40),
        }),
        ledgerSettings: compression,
        registryEntry: registration("diversity"),
      });
      if (compact.status !== "written") throw new Error("compact diversity row was not written");
      const compactReadback = await checkParquetReadback(
        "diversity",
        root,
        compact.files,
        DiversityMetricRowSchema,
      );
      expect(compactReadback.files[0]?.rows).toEqual(rawReadback.files[0]?.rows);
      expect(compactReadback.files[0]?.identity).toMatchObject({
        run_id: "2026-10-21-457",
        job: "assemble",
        shard: 6,
      });
    });
  });

  test("keeps empty raw output absent and writes a typed empty compact file", async () => {
    await withOutputRoot(async (root) => {
      const base = {
        ledger: "diversity",
        rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
        outputRoot: root,
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("diversity"),
      };
      const raw = await persistLedger({
        ...base,
        rows: [],
        period: { tier: "raw", covers: "2026-10-21" },
      });
      expect(raw).toEqual({ status: "empty", files: [] });

      const compact = await persistLedger({
        ...base,
        rows: [],
        period: { tier: "compact", period: "daily", covers: "2026-10-21", builtFrom: 0 },
      });
      if (compact.status !== "written") throw new Error("empty compact period was not written");
      const readback = await checkParquetReadback("diversity", root, compact.files, DiversityMetricRowSchema);
      expect(readback.files[0]?.row_count).toBe(0);
      expect(readback.files[0]?.tier).toBe("compact");
    });
  });

  test("writes a narrowed host-fingerprint identity row without claiming hardware retention", async () => {
    await withOutputRoot(async (root) => {
      const HostFingerprintIdentityCollisionSchema = z.object({
        version: z.string(),
        date: z.string(),
        run_id: z.string(),
        job: z.string(),
        pipeline_name: z.string().nullable(),
        task_name: z.string().nullable(),
        shard: z.number().int(),
        flags: z.string(),
      });
      const fixture = await readLedgerFixture("host-fingerprint-row.json");
      expect(fixture).toHaveProperty("cpu_model");
      const row = HostFingerprintIdentityCollisionSchema.parse(fixture);
      expect(row).not.toHaveProperty("cpu_model");
      const hostWriter = WriterIdentitySchema.parse({
        run_id: "2026-10-21-777",
        attempt: 4,
        job: "operator",
        pipeline_name: null,
        task_name: null,
        shard: 7,
        producer: "tests.host-fingerprint",
        git_sha: "c".repeat(40),
      });
      const registrationEntry = await registeredEntry("host-fingerprint");
      expect(registrationEntry.prefix).toEqual(["host-fingerprint"]);
      const raw = await persistLedger({
        ledger: "host-fingerprint",
        rowContract: {
          schema: HostFingerprintIdentityCollisionSchema,
          schemaVersion: "2026-10-14",
        },
        rows: [row],
        outputRoot: root,
        period: { tier: "raw", covers: "2026-10-21" },
        writerContext: hostWriter,
        ledgerSettings: compression,
        registryEntry: registrationEntry,
      });
      if (raw.status !== "written") throw new Error("host fingerprint row was not written");
      const readback = await checkParquetReadback(
        "host-fingerprint",
        root,
        raw.files,
        HostFingerprintIdentityCollisionSchema,
      );
      expect(readback.files[0]?.identity).toMatchObject({ job: "operator", shard: 7 });
      expect(readback.files[0]?.rows[0]).toMatchObject({
        run_id: "2026-10-21-555",
        job: "work",
        pipeline_name: null,
        task_name: null,
        shard: 1,
      });
      expect(readback.files[0]?.rows[0]).toMatchObject(row);
      expect(readback.files[0]?.rows[0]).not.toHaveProperty("cpu_model");
    });
  });

  test("writes a real dispatch with worker assignment distinct from writer shard", async () => {
    await withOutputRoot(async (root) => {
      const dispatch = FeedIngestDispatchSchema.parse(
        await readLedgerFixture("feed-ingest-dispatch-row.json"),
      );
      expect(dispatch.partition.worker_assignment).not.toBe(writerContext.shard);
      const raw = await persistLedger({
        ledger: "dispatches",
        rowContract: { schema: FeedIngestDispatchSchema, schemaVersion: "2026-10-20" },
        rows: [dispatch],
        outputRoot: root,
        period: { tier: "raw", covers: dispatch.content.date },
        writerContext,
        ledgerSettings: compression,
        registryEntry: await registeredEntry("dispatches"),
      });
      if (raw.status !== "written") throw new Error("dispatch row was not written");
      const readback = await checkParquetReadback(
        "dispatches",
        root,
        raw.files,
        FeedIngestDispatchSchema,
      );
      expect(readback.files[0]?.identity.shard).toBe(writerContext.shard);
      expect(readback.files[0]?.rows[0]?.partition).toEqual(dispatch.partition);
      expect(readback.files[0]?.rows[0]?.content).toEqual(dispatch.content);
      expect(readback.files[0]?.rows[0]?.selection).toEqual(dispatch.selection);
      expect(readback.files[0]?.rows[0]).toMatchObject(dispatch);
    });
  });

  test("rejects invalid rows without writing any file", async () => {
    await withOutputRoot(async (root) => {
      const invalid = { ...assessment("2026-10-21", null), source_id: "different-source" };
      await expect(persistLedger({
        ledger: "article-assessments",
        rowContract: { schema: ArticleAssessmentRecordSchema, schemaVersion: "2026-10-20" },
        rows: [invalid],
        outputRoot: root,
        period: { tier: "raw", covers: "2026-10-21" },
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("article-assessments"),
      })).rejects.toThrow();
      expect(await readdir(root)).toEqual([]);
    });
  });

  test("rejects a registry prefix that can escape the output root", async () => {
    await withOutputRoot(async (root) => {
      const unsafeRegistration: LedgerRegistration = {
        ...registration("article-assessments"),
        prefix: ["feed-ingest-plan", "..", "article-assessments"],
      };
      await expect(persistLedger({
        ledger: "article-assessments",
        rowContract: { schema: ArticleAssessmentRecordSchema, schemaVersion: "2026-10-20" },
        rows: [assessment("2026-10-21", null)],
        outputRoot: root,
        period: { tier: "raw", covers: "2026-10-21" },
        writerContext,
        ledgerSettings: compression,
        registryEntry: unsafeRegistration,
      })).rejects.toThrow("unsafe path segment");
      expect(await readdir(root)).toEqual([]);
    });
  });

  test("preflights every raw destination before writing the first file", async () => {
    await withOutputRoot(async (root) => {
      const blockedDay = resolve(root, "raw", "feed-ingest-plan", "article-assessments", "2026", "10", "21");
      await mkdir(dirname(blockedDay), { recursive: true });
      await writeFile(blockedDay, "not a directory");

      await expect(persistLedger({
        ledger: "article-assessments",
        rowContract: { schema: ArticleAssessmentRecordSchema, schemaVersion: "2026-10-20" },
        rows: [assessment("2026-10-20", null), assessment("2026-10-21", null)],
        outputRoot: root,
        period: { tier: "raw", covers: "2026-10-21" },
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("article-assessments"),
      })).rejects.toThrow();

      const firstDay = resolve(root, "raw", "feed-ingest-plan", "article-assessments", "2026", "10", "20");
      expect(await readdir(firstDay)).toEqual([]);
    });
  });

  test("skips new raw rows for inactive ledgers but still compacts stored rows", async () => {
    await withOutputRoot(async (root) => {
      const row = diversity();
      for (const lifecycleStatus of ["paused", "retired"] as const) {
        const skipped = await persistLedger({
          ledger: "diversity",
          rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
          rows: [row],
          outputRoot: root,
          period: { tier: "raw", covers: row.date },
          writerContext,
          ledgerSettings: compression,
          registryEntry: registration("diversity", lifecycleStatus),
        });
        expect(skipped).toMatchObject({
          status: "skipped",
          reason: "ledger_not_active",
          warning: { ledger: "diversity", lifecycle_status: lifecycleStatus, row_count: 1 },
          files: [],
        });
      }
      expect(await readdir(root)).toEqual([]);

      for (const job of ["migrate", "run-tasks", "history"] as const) {
        for (const lifecycleStatus of ["paused", "retired"] as const) {
          const maintained = await persistLedger({
            ledger: "diversity",
            rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
            rows: [row],
            outputRoot: root,
            period: { tier: "raw", covers: row.date },
            writerContext: WriterIdentitySchema.parse({
              ...writerContext,
              job,
              pipeline_name: null,
              task_name: null,
              producer: `tests.${job}`,
            }),
            ledgerSettings: compression,
            registryEntry: registration("diversity", lifecycleStatus),
          });
          expect(maintained.status).toBe("written");
        }
      }

      const identity = RowIdentitySchema.parse({
        ledger: "diversity",
        covers: row.date,
        run_id: writerContext.run_id,
        attempt: writerContext.attempt,
        job: writerContext.job,
        pipeline_name: writerContext.pipeline_name,
        task_name: writerContext.task_name,
        shard: writerContext.shard,
        unit_id: createUnitId({
          ledger: "diversity",
          covers: row.date,
          runId: writerContext.run_id,
          job: writerContext.job,
          pipelineName: writerContext.pipeline_name,
          taskName: writerContext.task_name,
          shard: writerContext.shard,
          producer: writerContext.producer,
        }),
      });
      const compact = await persistLedger({
        ledger: "diversity",
        rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
        rows: [{ identity, row }],
        outputRoot: root,
        period: { tier: "compact", period: "daily", covers: row.date, builtFrom: 1 },
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("diversity", "paused"),
      });
      if (compact.status !== "written") throw new Error("paused ledger did not compact its stored row");
      const readback = await checkParquetReadback("diversity", root, compact.files, DiversityMetricRowSchema);
      expect(readback.files[0]?.row_count).toBe(1);
    });
  });
});
