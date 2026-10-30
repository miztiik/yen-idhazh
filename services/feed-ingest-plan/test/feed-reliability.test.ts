/** Do only the two saved feed-read ratios use downward thousandths? */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  FeedHealthStateRowContract, FeedHealthStateRowSchema, LEGACY_FEED_HEALTH_STATE_VERSION,
  SourceSnapshotSchema,
} from "@idhazh/common-contracts";
import { readPlannerParquet } from "@idhazh/ledger-file-writer";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { feedReliability } from "../src/read-ledger-history/feed-reliability";
import { captureHealthRows, inputEndpointKey, summarizePlanningHealth } from "../src/read-ledger-history/health-summary";
import { projectFeedHealthFields } from "../src/read-ledger-history/read-feed-health-fields";
import { compactRows, writeRows } from "./partition-fixtures";

type Case = {
  productive: number; attempted: number; floor: number;
  success_fraction: number; production_factor: number;
};

test("recorded ratios and arbitrary floors truncate downward without a decimal setting", async () => {
  const fixture = await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/feed-reliability.json", import.meta.url)).json() as { cases: Case[] };
  for (const row of fixture.cases) {
    const actual = feedReliability(row.productive, row.attempted, row.floor);
    expect(actual).toEqual({ success_fraction: row.success_fraction, production_factor: row.production_factor });
    expect(JSON.parse(JSON.stringify(actual))).toEqual(actual);
  }
});

test("invalid counts and floors fail explicitly instead of becoming valid-looking ratios", () => {
  for (const [productive, attempted] of [[-1, 1], [2, 1], [0, 0], [1.5, 2], [1, Infinity], [1, Number.MAX_SAFE_INTEGER + 1]]) {
    expect(() => feedReliability(productive!, attempted!, 0)).toThrow("safe read counts");
  }
  for (const floor of [-1, 1.1, NaN, Infinity]) {
    expect(() => feedReliability(1, 2, floor)).toThrow("floor must be finite");
  }
});

test("health capture and raw/compact files retain truncated numbers without changing original evidence", async () => {
  const day = "2026-10-20";
  const source = SourceSnapshotSchema.parse({
    feed_id: "recorded-news", feed_url: "https://news.example/feed.xml", title: "Recorded feed",
    publisher_id: null, tier: 2, status: "active", weight: 0.8, applied_tier_weight: 0.6,
  });
  const seed = plannerRecordings(day).find(record => record.name === "feed-health-state")!;
  const rows = Array.from({ length: 22 }, (_, index) => FeedHealthStateRowSchema.parse({
    ...seed.row, feed_id: source.feed_id, endpoint_key: inputEndpointKey(source.feed_url),
    checked_at: `${day}T12:00:00Z`, run_id: `${day}-${100 + index}`,
    outcome: index === 0 ? "transient" : "ok", items: index === 0 ? 0 : 1,
  }));
  const projected = projectFeedHealthFields(day, rows);
  const input = {
    uses: {
      feed_rest: projected.feed_rest, feed_reliability: projected.feed_reliability,
      article_admission: projected.article_admission,
    },
    sources: [source], now: `${day}T23:59:59Z`, days: [{ day, complete: true }],
    lifecycle_window_days: 1,
    policy: { availability_strikes_before_rest: 5, reliability_window_days: 1, reliability_floor: 0.5 },
  };
  const summary = summarizePlanningHealth(input);
  const captured = captureHealthRows([rows[0]!], summary.sources);
  expect(captured[0]!.reliability).toMatchObject({
    productive: 21, attempted: 22, success_fraction: 0.954, production_factor: 0.954, complete: true,
  });
  expect(FeedHealthStateRowSchema.parse(JSON.parse(JSON.stringify(captured[0])))).toEqual(captured[0]!);
  expect(summarizePlanningHealth({ ...input, days: [{ day, complete: false }] })
    .sources.get(source.feed_id)!.reliability).toMatchObject({ success_fraction: 0.954, complete: false });
  expect(summarizePlanningHealth({
    ...input, uses: {
      feed_rest: { rows: [], gaps: [] }, feed_reliability: { rows: [], gaps: [] },
      article_admission: { rows: [], gaps: [] },
    },
  }).sources.get(source.feed_id)!.reliability).toBeNull();
  const root = await mkdtemp(join(tmpdir(), "feed-reliability-"));
  try {
    const raw = await writeRows(root, "feed-health-state", day, FeedHealthStateRowContract, captured);
    const actual = await readPlannerParquet(join(root, raw.files[0]!.path), "feed-health-state", FeedHealthStateRowContract);
    expect(actual.rows).toEqual(captured);
    const compact = await compactRows(root, "feed-health-state", day, FeedHealthStateRowContract, actual.rows, "daily");
    expect((await readPlannerParquet(compact.path!, "feed-health-state", FeedHealthStateRowContract)).rows).toEqual(captured);
    const historical = FeedHealthStateRowSchema.parse({
      ...captured[0], reliability: { ...captured[0]!.reliability, success_fraction: 21 / 22, production_factor: 21 / 22 },
    });
    const old = await writeRows(root, "feed-health-state", day,
      { ...FeedHealthStateRowContract, schemaVersion: LEGACY_FEED_HEALTH_STATE_VERSION }, [historical]);
    expect((await readPlannerParquet(join(root, old.files[0]!.path), "feed-health-state", FeedHealthStateRowContract)).rows)
      .toEqual([historical]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
