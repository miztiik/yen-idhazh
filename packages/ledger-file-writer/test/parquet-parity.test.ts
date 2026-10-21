/** Exercises the public writer against the Python ledger reader and real files. */
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdir, mkdtemp, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { describe, expect, test } from "bun:test";
import { ArticleAssessmentRecordSchema, DiversityMetricRowSchema, RowIdentitySchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import { createUnitId, persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings, PersistedLedgerFile } from "@idhazh/ledger-file-writer";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(packageRoot, "..", "..");
const parityScript = join(packageRoot, "test", "verify-python-parity.py");
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

function absoluteFiles(root: string, files: readonly PersistedLedgerFile[]): string[] {
  return files.map((file) => resolve(root, ...file.path.split("/")));
}

function checkPythonParity(ledger: string, files: readonly string[]) {
  const pathSeparator = process.platform === "win32" ? ";" : ":";
  const pythonPath = [join(repositoryRoot, "backend"), process.env.PYTHONPATH]
    .filter(Boolean)
    .join(pathSeparator);
  const result = spawnSync("python", [parityScript, ledger, ...files], {
    cwd: repositoryRoot,
    encoding: "utf8",
    env: { ...process.env, PYTHONPATH: pythonPath },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || result.stdout);
  return JSON.parse(result.stdout) as {
    files: {
      covers: string;
      tier: "raw" | "compact";
      period: "daily" | "monthly" | "yearly" | null;
      row_count: number;
      content_sha256: string;
      identity: Record<string, unknown>;
      rows: Record<string, unknown>[];
    }[];
  };
}

async function withOutputRoot<T>(run: (root: string) => Promise<T>): Promise<T> {
  const root = await mkdtemp(join(tmpdir(), "ledger-file-writer-"));
  try {
    return await run(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

describe("Python-readable ledger Parquet", () => {
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

      const rawPaths = absoluteFiles(root, raw.files);
      const rawParity = checkPythonParity("article-assessments", rawPaths);
      expect(rawParity.files.map((file) => file.row_count)).toEqual([1, 1]);
      expect(rawParity.files.every((file) => file.tier === "raw" && file.period === null)).toBe(true);

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
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("article-assessments"),
      });
      expect(compact.status).toBe("written");
      if (compact.status !== "written") throw new Error("compact rows were not written");
      const compactParity = checkPythonParity("article-assessments", absoluteFiles(root, compact.files));
      expect(compactParity.files[0]?.row_count).toBe(2);
      expect(compactParity.files[0]?.tier).toBe("compact");
      expect(compactParity.files[0]?.period).toBe("monthly");
      expect(compactParity.files[0]?.rows).toEqual(rawParity.files.flatMap((file) => file.rows));
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
      const rawParity = checkPythonParity("diversity", absoluteFiles(root, raw.files));
      const identityCells = rawParity.files[0]?.rows[0];
      if (!identityCells) throw new Error("Python reader did not return the stored identity");
      const identity = RowIdentitySchema.parse(identityCells);

      const compact = await persistLedger({
        ledger: "diversity",
        rowContract: { schema: DiversityMetricRowSchema, schemaVersion: "2026-10-20" },
        rows: [{ identity, row }],
        outputRoot: root,
        period: { tier: "compact", period: "daily", covers: row.date, builtFrom: 1 },
        writerContext,
        ledgerSettings: compression,
        registryEntry: registration("diversity"),
      });
      if (compact.status !== "written") throw new Error("compact diversity row was not written");
      const compactParity = checkPythonParity("diversity", absoluteFiles(root, compact.files));
      expect(compactParity.files[0]?.rows).toEqual(rawParity.files[0]?.rows);
      expect(compactParity.files[0]?.identity).toEqual(rawParity.files[0]?.identity);
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
      const parity = checkPythonParity("diversity", absoluteFiles(root, compact.files));
      expect(parity.files[0]?.row_count).toBe(0);
      expect(parity.files[0]?.tier).toBe("compact");
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
        expect(skipped).toEqual({ status: "skipped", reason: "ledger_not_active", files: [] });
      }
      expect(await readdir(root)).toEqual([]);

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
      const parity = checkPythonParity("diversity", absoluteFiles(root, compact.files));
      expect(parity.files[0]?.row_count).toBe(1);
    });
  });
});
