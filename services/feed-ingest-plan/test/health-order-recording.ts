/** Do identical native observations keep every lifecycle decision through all compact tiers? */
import { expect } from "bun:test";
import { mkdir, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import {
  CompactIndexSchema, FeedHealthContract, SourceSnapshotSchema,
} from "@idhazh/common-contracts";
import type { FeedHealthRow } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistedLedgerFile, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { readFeedHistory, endpointKey } from "../src/read-ledger-history/read-feed-history";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { sourceSnapshot } from "../src/harvest-feeds/load-harvest-inputs";
import { recordedPlan } from "./plan-recordings";

export async function verifyHealthOrderCompaction() {
  const fixture = await recordedPlan();
  try {
    const base = FeedHealthContract.schema.parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/feed-health-row.json", import.meta.url,
    )).json());
    const legacyVersion = "2026-09-02T20:00";
    const legacy = { ...FeedHealthContract.legacyVersions[legacyVersion], schemaVersion: legacyVersion };
    const day = base.date;
    const second = base.checked_at.slice(0, -1);
    const recording = z.object({
      threshold: z.int().positive(), run_suffixes: z.tuple([z.string(), z.string()]),
      cases: z.array(z.object({
        id: z.string(), times: z.tuple([z.string(), z.string()]),
        kinds: z.tuple([FeedHealthContract.schema.shape.outcome, FeedHealthContract.schema.shape.outcome]),
        statuses: z.tuple([z.number().nullable(), z.number().nullable()]),
        expected: z.enum(["eligible", "unknown", "resting", "retired"]),
      })),
    }).parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/health-order-cases.json", import.meta.url,
    )).json());
    const cases = recording.cases.map(test => ({ ...test, times: test.times.map(time => second + time) }));
    const template = sourceSnapshot(fixture.inputs.harvest, fixture.inputs.harvest.sources[0]!);
    const sources = cases.map(test => SourceSnapshotSchema.parse({
      ...template, source_id: test.id, feed_url: `${template.feed_url}?ordering=${test.id}`,
      status: test.id === "known-retired" ? "retired" : template.status,
    }));
    const writer = (run_id: string, producer: string) => ({
      run_id, attempt: 1, job: null, pipeline_name: "feed-ingest-plan", task_name: "plan",
      shard: 0, producer, git_sha: "a".repeat(40),
    });
    const rawFiles: PersistedLedgerFile[] = [];
    const originals: StoredLedgerRow<FeedHealthRow>[] = [];
    for (const [index, suffix] of recording.run_suffixes.entries()) {
      const run_id = `${day}-${suffix}`;
      const all = cases.map((test, sourceIndex) => FeedHealthContract.schema.parse({
        ...base, version: test.times[index]!.includes(".") ? FeedHealthContract.schemaVersion : legacy.schemaVersion,
        run_id, checked_at: test.times[index], feed_id: test.id,
        endpoint_key: endpointKey(sources[sourceIndex]!.feed_url),
        outcome: test.kinds[index], status: test.statuses[index],
        items: test.kinds[index] === "ok" ? 3 : 0,
        robots_outcome: test.kinds[index] === "skipped" ? null : base.robots_outcome,
        target_attempted: test.kinds[index] !== "skipped",
      }));
      for (const old of [true, false]) {
        const rows = all.filter(row => (row.version === legacy.schemaVersion) === old);
        const written = await persistLedger({
          ledger: "feed-health", registryEntry: fixture.inputs.registrations.feed_health,
          outputRoot: fixture.inputs.outputRoot, ledgerSettings: fixture.inputs.ledgerSettings,
          writerContext: writer(run_id, old ? "tests.legacy-health" : "tests.precise-health"),
          period: { tier: "raw", covers: day },
          rowContract: old ? legacy : FeedHealthContract, rows,
        });
        rawFiles.push(...written.files);
        for (const file of written.files) {
          const held = await readLedgerParquet(join(fixture.inputs.outputRoot, file.path), "feed-health", FeedHealthContract);
          originals.push(...held.rows);
        }
      }
    }
    const input = {
      root: fixture.directory, now: "2026-10-24T00:00:00.000Z", run_id: "2026-10-24-99",
      sources, policy: { ...fixture.inputs.clock_config.collect,
        availability_strikes_before_rest: recording.threshold },
      health: fixture.inputs.registrations.feed_health,
    };
    const rawPaths = rawFiles.map(file => `state/${file.path}`);
    const before = await readFeedHistory({ ...input, health_days: [{ day, raw_files: rawPaths }] });
    for (const test of cases) expect(before.sources.get(test.id)!.lifecycle).toBe(test.expected);
    const signature = (rows: readonly StoredLedgerRow<FeedHealthRow>[]) =>
      JSON.stringify(rows.toSorted((a, b) => `${a.row.feed_id}:${a.row.run_id}`.localeCompare(`${b.row.feed_id}:${b.row.run_id}`)));
    const originalSignature = signature(originals);
    for (const period of ["daily", "monthly", "yearly"] as const) {
      const covers = period === "daily" ? day : period === "monthly" ? day.slice(0, 7) : day.slice(0, 4);
      const packed = await persistLedger({
        ledger: "feed-health", registryEntry: fixture.inputs.registrations.feed_health,
        outputRoot: fixture.inputs.outputRoot, ledgerSettings: fixture.inputs.ledgerSettings,
        writerContext: writer(`${day}-100`, `tests.pack-${period}`),
        period: { tier: "compact", period, covers, builtFrom: rawFiles.length },
        rowContract: FeedHealthContract, rows: originals,
      });
      const file = packed.files[0]!;
      const held = await readLedgerParquet(join(fixture.inputs.outputRoot, file.path), "feed-health", FeedHealthContract);
      expect(signature(held.rows)).toBe(originalSignature);
      const index = join(fixture.inputs.outputRoot, "compact", "feed-health", "index", `${period}.json`);
      await mkdir(dirname(index), { recursive: true });
      await writeFile(index, JSON.stringify(CompactIndexSchema.parse({
        version: "2026-10-07", ledger: "feed-health", period,
        entries: [{ covers, state: "packed", rows: held.rows.length,
          bytes: (await stat(join(fixture.inputs.outputRoot, file.path))).size }],
      })));
      const after = await readFeedHistory({
        ...input, health_days: [{ day, indexes: { [period]: `state/compact/feed-health/index/${period}.json` }, raw_files: rawPaths }],
      });
      expect([...after.sources]).toEqual([...before.sources]);
      const clockRows = (rows: readonly FeedHealthRow[]) => rows.map(row =>
        [row.feed_id, row.run_id, row.version, row.checked_at]).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
      expect(clockRows(after.rows)).toEqual(clockRows(before.rows));
    }
    expect(fixture.transport.requests).toHaveLength(0);
  } finally { await fixture.close(); }
}
