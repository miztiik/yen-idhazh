/** Read real writer bytes through WASM and Arrow without changing other families' protocol. */
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { describe, expect, test } from "bun:test";
import { tableFromIPC } from "apache-arrow";
import {
  DateStampSchema, FileEnvelopeSchema, FOOTER_METADATA_KEYS, OPTIONAL_FOOTER_METADATA_KEYS,
  PLANNER_FOOTER_METADATA_KEYS, PLANNER_OPTIONAL_FOOTER_METADATA_KEYS,
  PlannerFileEnvelopeSchema, PlannerLedgerNameSchema, RowIdentitySchema, WriterIdentitySchema,
  SELECTED_ARTICLE_VERSION, SelectedArticlesArtifactSchema, SelectedArticleRowSchema,
  selectedArticleMetadata, validateEnvelopeContainer,
} from "@idhazh/common-contracts";
import type { FileEnvelope, PlannerFileEnvelope } from "@idhazh/common-contracts";
import { readMetadata, readParquet } from "parquet-wasm/esm";
import type { Field } from "apache-arrow";
import { z } from "zod";
import { createUnitId, persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings, PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { appendIdentityColumns, describeObjectSchema } from "../src/row-schema";
import { digestRows, serializeRowsBytes } from "../src/parquet/row-digest";
import { buildArrowTable } from "../src/parquet/arrow-builder";
import { initializeParquetWasm } from "../src/parquet/wasm-serializer";
import { plannerRecordings, selectedArticle } from "./planner-recordings";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const compression: LedgerSettings = { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" };
const writerContext = WriterIdentitySchema.parse({
  run_id: "2026-10-21-123", attempt: 3, job: null, pipeline_name: "plan",
  task_name: "seal-article-ledger", shard: 2, producer: "tests.ledger-file-writer", git_sha: "a".repeat(40),
});
// A generic-format fixture, not a planner payload or a substitute persisted contract.
const NestedSchema = z.strictObject({
  date: DateStampSchema, title: z.string(), categories: z.array(z.string()).nullable(),
  score: z.number().finite(), count: z.int().nonnegative(),
  evidence: z.strictObject({
    value: z.number().finite().nullable(), known: z.boolean(), tags: z.array(z.string()),
  }).nullable(),
});
const CountRowSchema = z.strictObject({ date: DateStampSchema, count: z.int().nonnegative(), factor: z.number().finite().nullable() });
function assessment(day: string, categories: string[] | null) {
  return NestedSchema.parse({
    date: day, title: "Caf\u00e9 \u6771\u4eac", categories, score: -0.0, count: 3,
    evidence: categories === null ? null : { value: 1e-7, known: false, tags: [] },
  });
}
function diversity() {
  return CountRowSchema.parse({ date: "2026-10-21", count: 0, factor: null });
}
function registration(ledger: string, lifecycle_status: LedgerRegistration["lifecycle_status"] = "active"): LedgerRegistration {
  const planner = PlannerLedgerNameSchema.safeParse(ledger).success;
  return {
    name: ledger, family: planner ? "feed-ingest-plan" : ledger, grain: "raw-and-compact",
    lifecycle_status, prefix: planner ? ["feed-ingest-plan", ledger] : [ledger],
  };
}
function normalizeArrowValue(value: unknown): unknown {
  if (typeof value === "bigint") return Number(value);
  if (Array.isArray(value)) return value.map(normalizeArrowValue);
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") return normalizeArrowValue(value.toJSON());
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, normalizeArrowValue(child)]));
}
function requiredFooterValue(metadata: ReadonlyMap<string, string>, key: string): string {
  const value = metadata.get(key);
  if (value === undefined) throw new Error(`Parquet footer is missing ${key}`);
  return value;
}
function parseFooterEnvelope(metadata: ReadonlyMap<string, string>): FileEnvelope | PlannerFileEnvelope {
  const common = {
    version: requiredFooterValue(metadata, "envelope_version"),
    row_schema_version: requiredFooterValue(metadata, "schema_version"),
    tier: requiredFooterValue(metadata, "tier"), ledger: requiredFooterValue(metadata, "ledger"),
    covers: requiredFooterValue(metadata, "covers"), period: metadata.get("period") ?? null,
    file_id: requiredFooterValue(metadata, "file_id"), content_sha256: requiredFooterValue(metadata, "content_sha256"),
    writer: requiredFooterValue(metadata, "writer"), writer_version: requiredFooterValue(metadata, "writer_version"),
    compression: requiredFooterValue(metadata, "compression"),
  };
  if (PlannerLedgerNameSchema.safeParse(common.ledger).success) {
    return PlannerFileEnvelopeSchema.parse({ ...common, updated_at: metadata.get("updated_at") ?? null });
  }
  return validateEnvelopeContainer(FileEnvelopeSchema.parse({
    ...common, written_at_ms: Number(requiredFooterValue(metadata, "written_at_ms")),
    identity: {
      run_id: requiredFooterValue(metadata, "run_id"), attempt: Number(requiredFooterValue(metadata, "attempt")),
      job: metadata.get("job") ?? null, pipeline_name: metadata.get("pipeline_name") ?? null,
      task_name: metadata.get("task_name") ?? null, shard: Number(requiredFooterValue(metadata, "shard")),
      producer: requiredFooterValue(metadata, "producer"), git_sha: requiredFooterValue(metadata, "git_sha"),
    },
    unit_id: requiredFooterValue(metadata, "unit_id"),
    built_from: metadata.has("built_from") ? Number(metadata.get("built_from")) : null,
  }), "parquet");
}
async function readActualParquet(path: string) {
  await initializeParquetWasm();
  const bytes = await readFile(path);
  const metadata = readMetadata(bytes);
  const fileMetadata = metadata.fileMetadata();
  const footer = new Map([...fileMetadata.keyValueMetadata()].map(([key, value]) => [String(key), String(value)]));
  const footerRowCount = fileMetadata.numRows();
  fileMetadata.free();
  metadata.free();
  const table = tableFromIPC(readParquet(bytes).intoIPCStream());
  return {
    footer, footerRowCount, fields: table.schema.fields,
    rows: table.toArray().map(row => normalizeArrowValue(row) as Record<string, unknown>),
  };
}
async function checkParquetReadback<T extends object>(
  ledger: string, root: string, files: readonly PersistedLedgerFile[], schema: z.ZodType<T>,
) {
  const planner = PlannerLedgerNameSchema.safeParse(ledger).success;
  const fields = describeObjectSchema(schema).fields;
  const columns = planner ? fields : appendIdentityColumns(fields);
  const expectedSchema = buildArrowTable(columns, []).schema;
  const checked = [];
  for (const file of files) {
    const actual = await readActualParquet(resolve(root, ...file.path.split("/")));
    const envelope = parseFooterEnvelope(actual.footer);
    const keys = planner ? PLANNER_FOOTER_METADATA_KEYS : FOOTER_METADATA_KEYS;
    const optional: readonly string[] = planner ? PLANNER_OPTIONAL_FOOTER_METADATA_KEYS : OPTIONAL_FOOTER_METADATA_KEYS;
    expect([...actual.footer.keys()].sort()).toEqual([
      ...keys.filter(key => !optional.includes(key) || actual.footer.has(key)), "ARROW:schema",
    ].sort());
    expect(actual.fields.map(field => [field.name, field.type.toString(), field.nullable])).toEqual(
      expectedSchema.fields.map((field: Field) => [field.name, field.type.toString(), field.nullable]),
    );
    expect(actual.rows.length).toBe(actual.footerRowCount);
    expect(actual.footerRowCount).toBe(file.row_count);
    expect(String(envelope.ledger)).toBe(ledger);
    expect(envelope.file_id).toBe(file.file_id);
    expect(digestRows(actual.rows, columns)).toBe(envelope.content_sha256);
    if (planner) {
      expect(file).not.toHaveProperty("unit_id");
      expect(actual.fields.map(field => field.name)).toEqual(Object.keys(z.toJSONSchema(schema).properties!));
    } else {
      if (!("unit_id" in envelope) || file.unit_id === undefined) {
        throw new Error("ordinary ledger readback lost its original work-unit identity");
      }
      expect(envelope.unit_id).toBe(file.unit_id);
    }
    checked.push({
      ...actual, envelope, covers: envelope.covers, tier: envelope.tier, period: envelope.period,
      row_count: actual.footerRowCount, identity: "identity" in envelope ? envelope.identity : null,
    });
  }
  return { files: checked };
}
async function registeredEntry(name: string): Promise<LedgerRegistration> {
  const registry = JSON.parse(await readFile(join(repositoryRoot, "config", "ledgers.json"), "utf8")) as {
    families: { name: string; lifecycle_status: LedgerRegistration["lifecycle_status"]; ledgers: { name: string; prefix: string[] }[] }[];
  };
  for (const family of registry.families) {
    const entry = family.ledgers.find(candidate => candidate.name === name);
    if (entry) return { ...registration(name), family: family.name, lifecycle_status: family.lifecycle_status, prefix: entry.prefix };
  }
  throw new Error(`${name} is absent from the named registry`);
}
async function readLedgerFixture(name: string): Promise<unknown> {
  return JSON.parse(await readFile(join(repositoryRoot, "tests", "fixtures", "ledger-file-writer", name), "utf8"));
}
async function withOutputRoot<T>(run: (root: string) => Promise<T>): Promise<T> {
  const root = await mkdtemp(join(tmpdir(), "ledger-file-writer-"));
  try { return await run(root); } finally { await rm(root, { recursive: true, force: true }); }
}

describe("ledger Parquet readback", () => {
  test("serializes the recorded canonical compatibility vector", () => {
    const schema = z.object({
      big: z.number(), float_one: z.number(), list: z.array(z.string()),
      maybe: z.string().nullable(), negative_zero: z.number(),
      nested: z.object({ items: z.array(z.string()), value: z.number().int().nullable() }),
      small: z.number(), "z-unicode": z.string(),
    });
    const row = {
      big: 1e20, float_one: 1.0, list: ["na\u00efve", "\u6771\u4eac"], maybe: null,
      negative_zero: -0.0, nested: { items: ["\u00c9diteur"], value: null },
      small: 1e-7, "z-unicode": "Caf\u00e9 \u6771\u4eac",
    };
    const fields = describeObjectSchema(schema).fields;
    expect(serializeRowsBytes([row], fields).toString("ascii")).toBe(
      "{\"big\":1e+20,\"float_one\":1.0,\"list\":[\"na\\u00efve\",\"\\u6771\\u4eac\"],\"maybe\":null,\"negative_zero\":-0.0,\"nested\":{\"items\":[\"\\u00c9diteur\"],\"value\":null},\"small\":1e-07,\"z-unicode\":\"Caf\\u00e9 \\u6771\\u4eac\"}\n",
    );
    expect(digestRows([row], fields)).toBe("9514b5931807b27fbaf18c43c7371ada4bab45fd745ff4b3564dad032cdad67e");
  });

  test("writes raw day groups and compact rows through one registered contract", async () => {
    await withOutputRoot(async root => {
      const rows = [assessment("2026-10-20", ["na\u00efve", "\u6771\u4eac"]), assessment("2026-10-21", null)];
      const context = {
        ledger: "feed-health", outputRoot: root, writerContext, ledgerSettings: compression,
        registryEntry: registration("feed-health"), rowContract: { schema: NestedSchema, schemaVersion: "2026-10-20" },
      };
      const raw = await persistLedger({ ...context, rows, period: { tier: "raw", covers: "2026-10-21" } });
      if (raw.status !== "written") throw new Error("raw rows were not written");
      expect(raw.files.map(file => file.covers)).toEqual(["2026-10-20", "2026-10-21"]);
      const rawReadback = await checkParquetReadback("feed-health", root, raw.files, NestedSchema);
      expect(rawReadback.files.map(file => file.row_count)).toEqual([1, 1]);
      const compactRows = rows.map((row, index) => ({
        row, identity: RowIdentitySchema.parse({
          ledger: "feed-health", covers: row.date, run_id: writerContext.run_id,
          attempt: writerContext.attempt, job: writerContext.job, pipeline_name: writerContext.pipeline_name,
          task_name: writerContext.task_name, shard: writerContext.shard, unit_id: raw.files[index]!.unit_id,
        }),
      }));
      const compact = await persistLedger({
        ...context, rows: compactRows, period: { tier: "compact", period: "monthly", covers: "2026-10", builtFrom: 2 },
        writerContext: WriterIdentitySchema.parse({ ...writerContext, attempt: 9, shard: 7 }),
      });
      if (compact.status !== "written") throw new Error("compact rows were not written");
      const readback = await checkParquetReadback("feed-health", root, compact.files, NestedSchema);
      expect(readback.files[0]!.rows).toEqual(rawReadback.files.flatMap(file => file.rows));
      expect(readback.files[0]!.identity?.shard).toBe(7);
    });
  });

  test("writes a second registered contract and preserves its original compact identity", async () => {
    await withOutputRoot(async root => {
      const row = diversity();
      const context = {
        ledger: "seen", outputRoot: root, writerContext, ledgerSettings: compression,
        registryEntry: registration("seen"), rowContract: { schema: CountRowSchema, schemaVersion: "2026-10-20" },
      };
      const raw = await persistLedger({ ...context, rows: [row], period: { tier: "raw", covers: row.date } });
      if (raw.status !== "written") throw new Error("count row was not written");
      const first = await checkParquetReadback("seen", root, raw.files, CountRowSchema);
      const identity = RowIdentitySchema.parse({
        ledger: "seen", covers: row.date, run_id: writerContext.run_id, attempt: writerContext.attempt,
        job: writerContext.job, pipeline_name: writerContext.pipeline_name, task_name: writerContext.task_name,
        shard: writerContext.shard, unit_id: raw.files[0]!.unit_id,
      });
      const compact = await persistLedger({
        ...context, rows: [{ identity, row }], period: { tier: "compact", period: "daily", covers: row.date, builtFrom: 1 },
      });
      if (compact.status !== "written") throw new Error("count row was not compacted");
      const readback = await checkParquetReadback("seen", root, compact.files, CountRowSchema);
      expect(readback.files[0]!.rows).toEqual(first.files[0]!.rows);
    });
  });

  test("keeps empty raw output absent and writes a typed empty compact file", async () => {
    await withOutputRoot(async root => {
      const recording = plannerRecordings().find(row => row.name === "plan-runs")!;
      const context = { ledger: recording.name, outputRoot: root, rowContract: recording.contract, ledgerSettings: compression, registryEntry: registration(recording.name) };
      expect(await persistLedger({ ...context, rows: [], period: { tier: "raw", covers: "2026-10-20" } })).toEqual({ status: "empty", files: [] });
      const compact = await persistLedger({ ...context, rows: [], period: { tier: "compact", period: "daily", covers: "2026-10-20", builtFrom: 0 } });
      if (compact.status !== "written") throw new Error("typed empty planner compact file was not written");
      expect((await checkParquetReadback(recording.name, root, compact.files, recording.contract.schema)).files[0]!.row_count).toBe(0);
    });
  });

  test("writes a narrowed host-fingerprint identity row without claiming hardware retention", async () => {
    await withOutputRoot(async root => {
      const schema = z.object({
        version: z.string(), date: z.string(), run_id: z.string(), job: z.string(),
        pipeline_name: z.string().nullable(), task_name: z.string().nullable(),
        shard: z.number().int(), flags: z.string(),
      });
      const fixture = await readLedgerFixture("host-fingerprint-row.json");
      expect(fixture).toHaveProperty("cpu_model");
      const row = schema.parse(fixture);
      const hostWriter = WriterIdentitySchema.parse({
        run_id: "2026-10-21-777", attempt: 4, job: "operator", shard: 7,
        producer: "tests.host-fingerprint", git_sha: "c".repeat(40),
      });
      const raw = await persistLedger({
        ledger: "host-fingerprint", rowContract: { schema, schemaVersion: "2026-10-14" },
        rows: [row], outputRoot: root, period: { tier: "raw", covers: "2026-10-21" },
        writerContext: hostWriter, ledgerSettings: compression, registryEntry: await registeredEntry("host-fingerprint"),
      });
      if (raw.status !== "written") throw new Error("host fingerprint row was not written");
      const readback = await checkParquetReadback("host-fingerprint", root, raw.files, schema);
      expect(readback.files[0]!.identity).toMatchObject({ job: "operator", shard: 7 });
      expect(readback.files[0]!.rows[0]).toMatchObject({ run_id: "2026-10-21-555", job: "work", shard: 1 });
      expect(readback.files[0]!.rows[0]).not.toHaveProperty("cpu_model");
    });
  });

  test("writes all four planner ledgers without article text or generic identity", async () => {
    await withOutputRoot(async root => {
      const article = selectedArticle();
      const before = structuredClone(article);
      const metadata = selectedArticleMetadata(article);
      const artifact = SelectedArticlesArtifactSchema.parse({
        schema_version: SELECTED_ARTICLE_VERSION, run_id: "2026-10-20-1", attempt: 1,
        date: "2026-10-20", evaluated_at: "2026-10-20T10:00:00.123Z", articles: [article],
      });
      expect(article).toEqual(before);
      expect(metadata).not.toHaveProperty("article_text");
      expect(artifact.articles[0]!.article_text).toBe(before.article_text);
      for (const recording of plannerRecordings()) {
        const context = { ledger: recording.name, rowContract: recording.contract, outputRoot: root, ledgerSettings: compression, registryEntry: await registeredEntry(recording.name) };
        const raw = await persistLedger({
          ...context, rows: [recording.row, recording.row], period: { tier: "raw", covers: "2026-10-20" },
          ...(recording.name === "feed-health-state" ? { updatedAt: "2026-10-21T00:00:00.001Z" } : {}),
        });
        if (raw.status !== "written") throw new Error(`${recording.name} was not written`);
        const readback = await checkParquetReadback(recording.name, root, raw.files, recording.contract.schema);
        expect(readback.files[0]!.rows).toEqual([recording.row]);
        expect(readback.files[0]!.rows[0]).not.toHaveProperty("article_text");
        expect(readback.files[0]!.footer.has("run_id")).toBe(false);
        expect(readback.files[0]!.footer.has("unit_id")).toBe(false);
        expect(readback.files[0]!.footer.has("git_sha")).toBe(false);
        if (recording.name === "feed-health-state") expect(readback.files[0]!.footer.get("updated_at")).toBe("2026-10-21T00:00:00.001Z");
        for (const [period, covers] of [["daily", "2026-10-20"], ["monthly", "2026-10"], ["yearly", "2026"]] as const) {
          const recordedRetry = plannerRecordings("2026-10-20", 2).find(row => row.name === recording.name)!.row;
          const retry = recording.name === "plan-runs" ? { ...recordedRetry, duration_ms: null } : recordedRetry;
          const compact = await persistLedger({ ...context, rows: [recording.row, recording.row, retry], period: { tier: "compact", period, covers, builtFrom: 2 } });
          if (compact.status !== "written") throw new Error("planner compact file was not written");
          const packed = await checkParquetReadback(recording.name, root, compact.files, recording.contract.schema);
          expect(packed.files[0]!.row_count).toBe(recording.name === "discovered-articles" ? 1 : 2);
          if (recording.name === "feed-health-state") expect(packed.files[0]!.rows.reduce((sum, row) => sum + Number(row.article_requests), 0)).toBe(2);
          if (recording.name === "plan-runs") expect(packed.files[0]!.rows.some(row => row.duration_ms === null)).toBe(true);
        }
      }
      const discovery = plannerRecordings()[0]!;
      const raw = await persistLedger({
        ledger: discovery.name, rowContract: discovery.contract,
        rows: [{ ...discovery.row, first_seen_at: "2026-10-21T10:00:00Z", date: "2026-10-21" }, discovery.row],
        outputRoot: root, ledgerSettings: compression, registryEntry: registration(discovery.name),
        period: { tier: "raw", covers: "2026-10-21" },
      });
      if (raw.status !== "written") throw new Error("global discovery minimum was not written");
      expect(raw.files.map(file => file.covers)).toEqual(["2026-10-20"]);
    });
  });

  test("rejects invalid rows without writing any file", async () => {
    await withOutputRoot(async root => {
      const recording = plannerRecordings().find(row => row.name === "selected-articles")!;
      const context = { ledger: recording.name, outputRoot: root, rowContract: recording.contract, registryEntry: registration(recording.name), ledgerSettings: compression, period: { tier: "raw" as const, covers: "2026-10-20" } };
      for (const change of [{ article_text: "not allowed" }, { unit_id: "not allowed" }, { estimated_work: 0.5 }]) {
        await expect(persistLedger({ ...context, rows: [{ ...recording.row, ...change }] })).rejects.toThrow();
      }
      await expect(persistLedger({ ...context, rows: [recording.row], rowContract: {
        schema: SelectedArticleRowSchema.safeExtend({ article_text: z.string().optional() }), schemaVersion: recording.contract.schemaVersion,
      } })).rejects.toThrow("declared current planner row contract");
      await expect(persistLedger({ ...context, rows: [recording.row, { ...recording.row, title: "Conflicting copy" }] })).rejects.toThrow("conflicting duplicate");
      await expect(persistLedger({
        ...context, rows: [{ ...SelectedArticleRowSchema.parse(recording.row), url_key: "f".repeat(64) }],
        rowContract: { schema: z.strictObject(SelectedArticleRowSchema.shape), schemaVersion: recording.contract.schemaVersion },
      })).rejects.toThrow();
      const health = plannerRecordings().find(row => row.name === "feed-health-state")!;
      await expect(persistLedger({
        ...context, ledger: health.name, registryEntry: registration(health.name),
        rowContract: health.contract, rows: [health.row, { ...health.row, attempt: 2 }],
      })).rejects.toThrow("one run attempt");
      expect(await readdir(root)).toEqual([]);
    });
  });

  test("rejects a registry prefix that can escape the output root", async () => {
    await withOutputRoot(async root => {
      await expect(persistLedger({
        ledger: "feed-health", rowContract: { schema: NestedSchema, schemaVersion: "2026-10-20" },
        rows: [assessment("2026-10-21", null)], outputRoot: root, period: { tier: "raw", covers: "2026-10-21" },
        writerContext, ledgerSettings: compression, registryEntry: { ...registration("feed-health"), prefix: ["feed-health", "..", "feed-health"] },
      })).rejects.toThrow("unsafe path segment");
      expect(await readdir(root)).toEqual([]);
    });
  });

  test("preflights every raw destination before writing the first file", async () => {
    await withOutputRoot(async root => {
      const blocked = resolve(root, "raw", "feed-health", "2026", "10", "21");
      await mkdir(dirname(blocked), { recursive: true });
      await writeFile(blocked, "not a directory");
      await expect(persistLedger({
        ledger: "feed-health", rowContract: { schema: NestedSchema, schemaVersion: "2026-10-20" },
        rows: [assessment("2026-10-20", null), assessment("2026-10-21", null)],
        outputRoot: root, period: { tier: "raw", covers: "2026-10-21" }, writerContext,
        ledgerSettings: compression, registryEntry: registration("feed-health"),
      })).rejects.toThrow();
      expect(await readdir(resolve(root, "raw", "feed-health", "2026", "10", "20"))).toEqual([]);
    });
  });

  test("skips new raw rows for inactive ledgers but still compacts stored rows", async () => {
    await withOutputRoot(async root => {
      const row = diversity();
      const context = { ledger: "seen", rowContract: { schema: CountRowSchema, schemaVersion: "2026-10-20" }, outputRoot: root, writerContext, ledgerSettings: compression };
      for (const lifecycle of ["paused", "retired"] as const) {
        const skipped = await persistLedger({ ...context, rows: [row], period: { tier: "raw", covers: row.date }, registryEntry: registration("seen", lifecycle) });
        expect(skipped).toMatchObject({ status: "skipped", reason: "ledger_not_active", files: [] });
      }
      expect(await readdir(root)).toEqual([]);
      for (const job of ["migrate", "run-tasks", "history"] as const) {
        for (const lifecycle of ["paused", "retired"] as const) {
          const maintained = await persistLedger({
            ...context, rows: [row], period: { tier: "raw", covers: row.date },
            writerContext: WriterIdentitySchema.parse({ ...writerContext, job, pipeline_name: null, task_name: null }),
            registryEntry: registration("seen", lifecycle),
          });
          expect(maintained.status).toBe("written");
        }
      }
      const identity = RowIdentitySchema.parse({
        ledger: "seen", covers: row.date, run_id: writerContext.run_id, attempt: writerContext.attempt,
        job: writerContext.job, pipeline_name: writerContext.pipeline_name, task_name: writerContext.task_name,
        shard: writerContext.shard, unit_id: createUnitId({
          ledger: "seen", covers: row.date, runId: writerContext.run_id, job: writerContext.job,
          pipelineName: writerContext.pipeline_name, taskName: writerContext.task_name,
          shard: writerContext.shard, producer: writerContext.producer,
        }),
      });
      const compact = await persistLedger({ ...context, rows: [{ identity, row }], period: { tier: "compact", period: "daily", covers: row.date, builtFrom: 1 }, registryEntry: registration("seen", "paused") });
      if (compact.status !== "written") throw new Error("paused ordinary ledger did not compact");
      expect((await checkParquetReadback("seen", root, compact.files, CountRowSchema)).files[0]!.row_count).toBe(1);
    });
  });
});
