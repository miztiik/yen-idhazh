/** Can a public-package consumer reproduce a real file's canonical row commitment? */
import { expect, test } from "bun:test";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { tableFromIPC } from "apache-arrow";
import initialize, { readMetadata, readParquet } from "parquet-wasm/esm";
import {
  RejectedArticleRowContract, RejectedArticleRowSchema, WriterIdentitySchema,
  deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { z } from "zod";
import {
  appendIdentityColumns, describeObjectSchema, digestRows, persistLedger, readPlannerParquet,
} from "@idhazh/ledger-file-writer";
import { plannerRecordings } from "./planner-recordings";

function normalizeValue(value: unknown): unknown {
  if (typeof value === "bigint") return Number(value);
  if (Array.isArray(value)) return value.map(normalizeValue);
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") return normalizeValue(value.toJSON());
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, normalizeValue(child)]));
}

test("public schema descriptors and digest verify native raw readback", async () => {
  const root = await mkdtemp(join(tmpdir(), "ledger-reader-integrity-"));
  try {
    await initialize();
    const schema = z.strictObject({ date: z.string(), label: z.string(), score: z.number(), count: z.int() });
    const row = { date: "2026-10-21", label: "Caf\u00e9", score: 1e-7, count: 3 };
    const writerContext = WriterIdentitySchema.parse({
      run_id: "2026-10-21-10", attempt: 1, job: "plan", shard: 0,
      producer: "tests.integrity", git_sha: "a".repeat(40),
    });
    const context = {
      ledger: "feed-health", outputRoot: root, writerContext,
      rowContract: { schema, schemaVersion: "2026-10-20" },
      registryEntry: {
        name: "feed-health", family: "feed-health", grain: "raw-and-compact" as const,
        lifecycle_status: "active" as const, prefix: ["feed-health"],
      },
      ledgerSettings: { format: "parquet" as const, compression_raw: "snappy" as const, compression_compact: "zstd" as const },
    };
    const raw = await persistLedger({ ...context, period: { tier: "raw", covers: row.date }, rows: [row] });
    expect(raw.status).toBe("written");
    const file = raw.files[0]!;
    const bytes = await readFile(join(root, file.path));
    const table = tableFromIPC(readParquet(bytes).intoIPCStream());
    const record = Object.fromEntries(Object.entries(table.get(0)!.toJSON()).map(([key, cell]) =>
      [key, typeof cell === "bigint" ? Number(cell) : cell]));
    const columns = appendIdentityColumns(describeObjectSchema(schema).fields);
    const metadata = readMetadata(bytes);
    const footer = metadata.fileMetadata();
    try {
      expect(digestRows([record], columns)).toBe(footer.keyValueMetadata().get("content_sha256"));
      expect(digestRows([record], columns)).toBe(file.content_sha256);
      expect(digestRows([{ ...record, score: 2 }], columns)).not.toBe(file.content_sha256);
    } finally {
      footer.free();
      metadata.free();
    }
    expect(columns.find(column => column.name === "count")?.type.scalar).toBe("int64");
    expect(columns.find(column => column.name === "score")?.type.scalar).toBe("float64");
    for (const recording of plannerRecordings()) {
      const result = await persistLedger({
        ledger: recording.name, outputRoot: root, rowContract: recording.contract,
        registryEntry: {
          name: recording.name, family: "feed-ingest-plan", grain: "raw-and-compact",
          lifecycle_status: "active", prefix: ["feed-ingest-plan", recording.name],
        },
        ledgerSettings: context.ledgerSettings, period: { tier: "raw", covers: "2026-10-20" },
        rows: [recording.row],
      });
      expect(result.status).toBe("written");
      const actual = await readFile(join(root, result.files[0]!.path));
      const plannerColumns = describeObjectSchema(recording.contract.schema).fields;
      const decoded = tableFromIPC(readParquet(actual).intoIPCStream()).toArray()
        .map(row => normalizeValue(row) as Record<string, unknown>);
      const footerMetadata = readMetadata(actual);
      const footer = footerMetadata.fileMetadata();
      try {
        // A public-package reader uses declared row columns, not invented RowIdentity cells.
        expect(decoded).toEqual([recording.row]);
        expect(digestRows(decoded, plannerColumns)).toBe(footer.keyValueMetadata().get("content_sha256"));
        expect(footer.keyValueMetadata().has("unit_id")).toBe(false);
        expect(footer.keyValueMetadata().has("run_id")).toBe(false);
        expect(result.files[0]).not.toHaveProperty("unit_id");
        expect(() => digestRows(decoded, appendIdentityColumns(plannerColumns))).toThrow();
      } finally {
        footer.free();
        footerMetadata.free();
      }
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("reads an old rejected-article footer with a bounded unknown retained reason", async () => {
  const root = await mkdtemp(join(tmpdir(), "ledger-reader-compatibility-"));
  const day = "2026-10-20";
  const run = `${day}-1`;
  const unknownReason = "LEGACY_REASON_NOT_ACTIVE";
  const registration = {
    name: "rejected-articles", family: "feed-ingest-plan", grain: "raw-and-compact" as const,
    lifecycle_status: "active" as const, prefix: ["feed-ingest-plan", "rejected-articles"],
  };
  const row = RejectedArticleRowSchema.parse({
    run_id: run, attempt: 1, date: day,
    candidate_id: deriveCandidateId(run, "fixture-feed", 1),
    url_key: deriveUrlKey("https://example.com/legacy-article"),
    feed_id: "fixture-feed", stage: "curate-article-portfolio",
    reason_code: unknownReason, freshness_cutoff_at: null,
  });
  try {
    const written = await persistLedger({
      ledger: "rejected-articles",
      rowContract: { ...RejectedArticleRowContract, schemaVersion: "2026-10-27" },
      outputRoot: root, registryEntry: registration,
      ledgerSettings: {
        format: "parquet", compression_raw: "snappy", compression_compact: "zstd",
      },
      period: { tier: "raw", covers: day }, rows: [row],
    });
    expect(written.status).toBe("written");
    if (written.status !== "written") return;
    const file = written.files[0]!;
    expect(file.content_sha256).not.toBe("");
    expect(RejectedArticleRowContract.schemaVersion).toBe("2026-10-29");
    expect(RejectedArticleRowContract.acceptedSchemaVersions).toEqual(["2026-10-27", "2026-10-29"]);
    const actual = await readPlannerParquet(
      join(root, file.path), "rejected-articles", RejectedArticleRowContract,
    );
    expect(actual.envelope.row_schema_version).toBe("2026-10-27");
    expect(actual.rows).toEqual([row]);
    expect(actual.rows[0]?.reason_code).toBe(unknownReason);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
