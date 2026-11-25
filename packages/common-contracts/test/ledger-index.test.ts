/** Do the small index copies match bounded recorded fields, vocabulary and validation rules? */
import { expect, test } from "bun:test";
import {
  COMPACT_INDEX_VERSION, CompactCoverageSchema, CompactEntrySchema, CompactIndexSchema, CoverageStateSchema,
  EntryStateSchema, PeriodSchema, RawDayIndexSchema, compactPeriods,
} from "../src/index";

type Fixture = { index_contracts: {
  raw_fields: string[]; compact_fields: string[]; entry_fields: string[]; coverage_fields: string[];
  states: ("packed" | "empty" | "lost")[]; periods: ("daily" | "monthly" | "yearly")[];
  coverage_states: ("empty" | "lost")[]; compact_version: string;
  minimal_entry: { covers: string; rows: number; bytes: number };
  entry_defaults: { state: "packed"; lost_days: string[]; set_aside: number }; filename: string;
} };
async function fixture() {
  return (await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/ledger-history.json", import.meta.url)).json() as Fixture).index_contracts;
}
test("recorded index fields and vocabularies stay aligned without a backend process", async () => {
  const recorded = await fixture();
  expect(Object.keys(RawDayIndexSchema.shape)).toEqual(recorded.raw_fields);
  expect(Object.keys(CompactIndexSchema.shape)).toEqual(recorded.compact_fields);
  expect(Object.keys(CompactEntrySchema.shape)).toEqual(recorded.entry_fields);
  expect(Object.keys(CompactCoverageSchema.shape)).toEqual(recorded.coverage_fields);
  expect(EntryStateSchema.options).toEqual(recorded.states);
  expect(CoverageStateSchema.options).toEqual(recorded.coverage_states);
  expect(COMPACT_INDEX_VERSION).toBe(recorded.compact_version);
  expect(PeriodSchema.options).toEqual(recorded.periods);
  expect(CompactEntrySchema.parse(recorded.minimal_entry)).toEqual({ ...recorded.minimal_entry, ...recorded.entry_defaults });
});
test("index validation keeps raw listings and no-file coverage distinct", async () => {
  const recorded = await fixture();
  const raw = {
    version: "2026-10-03", ledger: "feed-health", date: "2026-10-21",
    files: [recorded.filename], content_sha256: "a".repeat(64), listed_at: "2026-10-21T12:00:00Z",
  };
  expect(RawDayIndexSchema.parse(raw).bytes).toBeNull();
  expect(RawDayIndexSchema.safeParse({ ...raw, files: [recorded.filename, recorded.filename] }).success).toBe(false);
  expect(RawDayIndexSchema.safeParse({ ...raw, files: ["../escape.parquet"] }).success).toBe(false);
  expect(RawDayIndexSchema.safeParse({ ...raw, bytes: [] }).success).toBe(false);
  const base = {
    version: COMPACT_INDEX_VERSION, ledger: "feed-health", period: "daily",
    entries: [], coverage: [{ covers: "2026-10-21", state: "empty" }],
  };
  expect(CompactIndexSchema.parse(base).coverage[0]!.state).toBe("empty");
  const packed = {
    ...base,
    coverage: [],
    entries: [{
      covers: "2026-10-21", rows: 1, bytes: 128, file_sha256: "a".repeat(64),
    }],
  };
  expect(CompactIndexSchema.parse(packed).entries[0]!.file_sha256).toBe("a".repeat(64));
  const invalid = [
    { coverage: [{ ...base.coverage[0], file_sha256: "a".repeat(64) }] },
    { entries: [{ covers: "2026-10-21", rows: 1, bytes: 128, file_sha256: "not-a-digest" }] },
    { coverage: [{ ...base.coverage[0], state: "lost", rows: 1 }] },
    { coverage: [{ ...base.coverage[0], bytes: 1 }] },
    { coverage: [base.coverage[0], base.coverage[0]] },
    { coverage: [{ ...base.coverage[0], covers: "2026-10" }] },
    { coverage: [{ ...base.coverage[0], lost_days: ["2026-10-21"] }] },
    { expired_through: "2025" },
    { period: "monthly", coverage: [{ covers: "2026-10", state: "lost" }] },
    ...[["2026-10-32"], ["2026-09-30"], ["2026-10-02", "2026-10-01"]].map(lost_days => ({
      period: "monthly", coverage: [{ covers: "2026-10", state: "empty", lost_days }],
    })),
    { period: "yearly", expired_through: "2026", coverage: [{ covers: "2026", state: "empty" }] },
  ];
  for (const patch of invalid) expect(CompactIndexSchema.safeParse({ ...base, ...patch }).success).toBe(false);
});

test("checked periods include real zero-row files and separate no-file coverage", () => {
  const empty = { covers: "2026-10-21", state: "empty", set_aside: 1 };
  const packed = { covers: "2026-10-22", rows: 0, bytes: 128 };
  const base = { ledger: "feed-health", period: "daily", version: COMPACT_INDEX_VERSION, entries: [packed], coverage: [empty] };
  const checked = compactPeriods(CompactIndexSchema.parse(base));
  expect(checked[0]).toMatchObject({ ...empty, rows: 0, bytes: 0 });
  expect(checked[1]).toMatchObject({ ...packed, state: "packed" });
  for (const patch of [
    { coverage: undefined }, { coverage: [{ ...empty, covers: packed.covers }] },
    { entries: [{ ...packed, state: "empty" }] }, { version: "2026-10-25" },
  ]) {
    expect(CompactIndexSchema.safeParse({ ...base, ...patch }).success).toBe(false);
  }
});
