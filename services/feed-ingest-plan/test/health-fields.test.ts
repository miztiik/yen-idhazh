/** Can each health use read only its fields without losing file or fact integrity? */
import { expect, test } from "bun:test";
import { copyFile, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { z } from "zod";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema, FeedIngestEventSchema } from "@idhazh/common-contracts";
import { persistLedger, readPlannerParquet, readStoredPlannerParquet } from "@idhazh/ledger-file-writer";
import { createStageLogger } from "../src/logging/structured-logger";
import { readFeedHealthFieldsDay } from "../src/read-ledger-history/read-feed-health-fields";
import { createPlannerHistoryCache, readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { healthFieldFixture, rewriteHealthFields } from "./health-field-fixtures";
import { commitFixtureFiles, compactRows, registration, settings } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";

const shape = FeedHealthStateRowSchema.shape;
const schema = z.object(shape);

test("compatible health columns accept older and newer row stamps while strict readers and writers refuse", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-stamps-"));
  try {
    const { row, written } = await healthFieldFixture(root);
    const path = join(root, written.files[0]!.path);
    for (const stamp of ["2026-10-25", "2026-10-27", "2027-01-01"]) {
      await rewriteHealthFields(path, [row], schema, { stamp });
      const cache = createPlannerHistoryCache<Record<string, unknown>>();
      const input = {
        day: row.date, raw_files: [written.files[0]!.path],
      };
      const read = await readFeedHealthFieldsDay(root, registration("feed-health-state"), input, cache);
      expect(read.complete).toBe(true);
      for (const use of Object.values(read.uses)) {
        expect(use.rows).toHaveLength(1);
        expect(use.gaps).toEqual([]);
        expect(use.partial_rows).toEqual([]);
      }
      if (stamp !== FeedHealthStateRowContract.schemaVersion) {
        expect((await readPlannerDay<Record<string, unknown>>(root, registration("feed-health-state"),
          input, FeedHealthStateRowContract, cache)).complete).toBe(false);
        await expect(readPlannerParquet(path, "feed-health-state", FeedHealthStateRowContract)).rejects.toThrow();
        await expect(persistLedger({
          ledger: "feed-health-state", outputRoot: root, registryEntry: registration("feed-health-state"),
          rowContract: { ...FeedHealthStateRowContract, schemaVersion: stamp }, ledgerSettings: settings,
          period: { tier: "raw", covers: row.date }, rows: [row], updatedAt: row.checked_at!,
        })).rejects.toThrow();
      }
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("unrelated missing, added and retyped columns do not change any health use", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-columns-"));
  try {
    const { row, written } = await healthFieldFixture(root);
    const path = join(root, written.files[0]!.path);
    const variant = schema.omit({ permission: true, reliability: true, articles_selected: true }).extend({
      status: z.string(), detail: z.object({ label: z.string(), readings: z.array(z.number()) }),
      rejection_counts: z.array(z.object(shape.rejection_counts.element.shape).omit({ stage: true }).extend({
        detail: z.string(),
      })),
    });
    const stored = variant.parse({
      ...row, status: "retained", detail: { label: "extra", readings: [0.25, 0.5] },
      rejection_counts: row.rejection_counts.map(reason => ({ ...reason, detail: "unrelated" })),
    });
    await rewriteHealthFields(path, [stored], variant);
    const read = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    });
    expect(read.complete).toBe(true);
    for (const use of Object.values(read.uses)) expect(use.gaps).toEqual([]);
    expect(read.uses.request_totals.rows[0]).toMatchObject({ feed_requests: 2, article_requests: 4, robots_requests: 0 });
    expect(read.uses.feed_reliability.rows[0]).toMatchObject({ outcome: "ok", items: 4 });
    await expect(readPlannerParquet(path, "feed-health-state", FeedHealthStateRowContract)).rejects.toThrow();
    await rewriteHealthFields(path, [{ ...stored, detail: { label: "tampered", readings: [0.25, 0.5] } }], variant,
      { preserve_digest: true });
    await expect(readStoredPlannerParquet(path, "feed-health-state")).rejects.toThrow("digest");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("request field gaps retain independent checks and individual valid counters without inventing zero", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-partial-"));
  try {
    const { row, written } = await healthFieldFixture(root);
    const path = join(root, written.files[0]!.path);
    const variant = schema.omit({ article_requests: true });
    const stored = { ...variant.parse(row), feed_requests: -1, robots_requests: null };
    await rewriteHealthFields(path, [stored], variant);
    const logged: unknown[] = [];
    const correlation_id = randomUUID();
    const log = createStageLogger({ run_id: row.run_id, correlation_id }, event => logged.push(event));
    const read = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    }, createPlannerHistoryCache(), undefined, log);
    expect(read.complete).toBe(true);
    expect(read.uses.request_totals.rows).toEqual([]);
    expect(read.uses.request_totals.partial_rows).toEqual([{
      date: row.date, run_id: row.run_id, attempt: row.attempt, feed_id: row.feed_id,
      endpoint_key: row.endpoint_key, robots_requests: null,
    }]);
    expect(read.uses.request_totals.gaps).toEqual([
      expect.objectContaining({ use: "request_totals", field: "feed_requests", day: row.date, code: "invalid" }),
      expect.objectContaining({ use: "request_totals", field: "article_requests", day: row.date, code: "missing" }),
    ]);
    expect(logged).toHaveLength(2);
    expect(logged.map(event => FeedIngestEventSchema.parse(event))).toEqual(expect.arrayContaining([
      expect.objectContaining({
        run_id: row.run_id, correlation_id, operation: "history", phase: "failed",
        details: expect.objectContaining({
          source: "feed-health-field", failed_check: "feed_requests", reason: "invalid",
        }),
      }),
      expect.objectContaining({
        run_id: row.run_id, correlation_id, operation: "history", phase: "failed",
        details: expect.objectContaining({
          source: "feed-health-field", failed_check: "article_requests", reason: "missing",
        }),
      }),
    ]));
    expect(logged.every(event => FeedIngestEventSchema.parse(event).occurred_at.endsWith("Z"))).toBe(true);
    for (const use of [read.uses.feed_rest, read.uses.feed_reliability, read.uses.article_admission]) {
      expect(use.rows).toHaveLength(1);
      expect(use.gaps).toEqual([]);
    }
    await rewriteHealthFields(path, [variant.parse(row)], variant);
    const partial = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    });
    expect(partial.uses.request_totals.partial_rows[0]).toMatchObject({ feed_requests: 2, robots_requests: 0 });
    expect(partial.uses.request_totals.partial_rows[0]).not.toHaveProperty("article_requests");
    await rewriteHealthFields(path, [{ ...row, article_requests: null }], schema);
    const unknown = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    });
    expect(unknown.uses.request_totals.rows[0]?.article_requests).toBeNull();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("invalid types, observation dates and admission counts affect only their declared uses", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-invalid-"));
  try {
    const { row, written } = await healthFieldFixture(root);
    const path = join(root, written.files[0]!.path);
    const variant = schema.extend({ feed_requests: z.string() });
    const stored = { ...row, feed_requests: "2", checked_at: "2026-10-24T10:00:00Z", article_candidates: -1 };
    await rewriteHealthFields(path, [stored], variant);
    const read = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    });
    expect(read.uses.request_totals.gaps[0]).toMatchObject({ field: "feed_requests", code: "invalid" });
    for (const use of [read.uses.feed_rest, read.uses.feed_reliability]) {
      expect(use.rows).toEqual([]);
      expect(use.gaps[0]).toMatchObject({ field: "checked_at", code: "invalid" });
      expect(use.partial_rows[0]).not.toHaveProperty("checked_at");
    }
    expect(read.uses.article_admission.rows).toEqual([]);
    expect(read.uses.article_admission.gaps[0]).toMatchObject({ field: "article_candidates", code: "invalid" });
    const missingCount = schema.extend({
      rejection_counts: z.array(z.object(shape.rejection_counts.element.shape).omit({ count: true })),
    });
    await rewriteHealthFields(path, [missingCount.parse(row)], missingCount);
    const nested = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    });
    expect(nested.uses.article_admission.gaps[0]).toMatchObject({
      field: "rejection_counts.0.count", code: "missing", day: row.date,
    });
    expect(nested.uses.request_totals.rows).toHaveLength(1);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("captured raw and compact members share field-based reading and duplicate protection", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-compact-"));
  try {
    const { row, written } = await healthFieldFixture(join(root, "state"));
    const compact = await compactRows(join(root, "state"), "feed-health-state", row.date,
      FeedHealthStateRowContract, [row], "monthly", root);
    const path = compact.path!;
    await rewriteHealthFields(path, [row], schema, { stamp: "2027-01-01" });
    const paths = [relative(root, path).replaceAll("\\", "/"), ...written.files.map(file => `state/${file.path}`)];
    await commitFixtureFiles(root, paths);
    const read = async () => readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_revision: await fixtureGit(root, ["rev-parse", "--verify", "HEAD"]),
    });
    const held = await read();
    expect(held.complete).toBe(true);
    for (const use of Object.values(held.uses)) {
      expect(use.rows).toHaveLength(1);
      expect(use.gaps).toEqual([]);
    }
    await rewriteHealthFields(path, [{ ...row, feed_requests: 9 }], schema);
    await commitFixtureFiles(root, [paths[0]!]);
    await expect(read()).rejects.toThrow("Conflicting copies");
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);

test("duplicates compare actual stored fields before projection and retain endpoint and attempt identity", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-duplicates-"));
  try {
    const { row, written } = await healthFieldFixture(root);
    const path = join(root, written.files[0]!.path);
    const read = () => readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: row.date, raw_files: [written.files[0]!.path],
    });
    await rewriteHealthFields(path, [row, row, { ...row, attempt: 2 }, { ...row, endpoint_key: "2".repeat(64) }], schema);
    expect((await read()).uses.request_totals.rows).toHaveLength(3);
    await rewriteHealthFields(path, [row, { ...row, permission: "denied" }], schema);
    await expect(read()).rejects.toThrow("Conflicting copies");
    const invalid = schema.omit({ attempt: true }).parse(row);
    await rewriteHealthFields(path, [invalid], schema.omit({ attempt: true }));
    const gap = await read();
    for (const use of Object.values(gap.uses)) {
      expect(use.rows).toEqual([]);
      expect(use.partial_rows).toEqual([]);
      expect(use.gaps[0]).toMatchObject({ field: "attempt", code: "missing", identity: null, day: row.date });
    }
    await rewriteHealthFields(path, [{ ...row, date: "2026-10-24" }], schema);
    for (const use of Object.values((await read()).uses)) {
      expect(use.rows).toEqual([]);
      expect(use.gaps).toContainEqual(expect.objectContaining({ field: "date", code: "invalid" }));
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("damaged bytes, wrong ledger identity, renamed files and repeated members never become usable history", async () => {
  const root = await mkdtemp(join(tmpdir(), "health-field-integrity-"));
  try {
    const { row, written } = await healthFieldFixture(root);
    const path = join(root, written.files[0]!.path);
    const input = { day: row.date, raw_files: [written.files[0]!.path] };
    const read = () => readFeedHealthFieldsDay(root, registration("feed-health-state"), input);
    const saved = await readFile(path);
    await writeFile(path, new Uint8Array([1, 2, 3]));
    const damaged = await read();
    expect(damaged.complete).toBe(false);
    expect(damaged.gaps).toEqual(["native_refused"]);
    for (const use of Object.values(damaged.uses)) expect(use.rows).toEqual([]);
    await writeFile(path, saved);
    await rewriteHealthFields(path, [row], schema, { metadata: { ledger: "selected-articles", updated_at: "" } });
    expect((await read()).complete).toBe(false);
    await writeFile(path, saved);
    const renamed = join(dirname(path), `${randomUUID().replace(/-4/, "-8")}.parquet`);
    await copyFile(path, renamed);
    await expect(readStoredPlannerParquet(renamed, "feed-health-state")).rejects.toThrow("filename");
    await expect(readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      ...input, raw_files: [written.files[0]!.path, written.files[0]!.path],
    })).rejects.toThrow("repeats a file");
    await rewriteHealthFields(path, [row], schema, { stamp: "not-a-date" });
    expect((await read()).complete).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
});
