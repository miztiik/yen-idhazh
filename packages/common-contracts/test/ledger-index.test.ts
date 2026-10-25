/** Do the small index copies match bounded recorded fields, vocabulary and validation rules? */
import { expect, test } from "bun:test";
import {
  COMPACT_INDEX_VERSION, CompactEntrySchema, CompactIndexSchema, EntryStateSchema,
  PeriodSchema, RawDayIndexSchema,
} from "../src/index";

type Fixture = { index_contracts: {
  raw_fields: string[]; compact_fields: string[]; entry_fields: string[];
  states: ("packed" | "empty" | "lost")[]; periods: ("daily" | "monthly" | "yearly")[];
  legacy_entry: { covers: string; rows: number; bytes: number };
  legacy_defaults: { state: "packed"; lost_days: string[]; set_aside: number }; filename: string;
} };
async function fixture() {
  return (await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/ledger-history.json", import.meta.url)).json() as Fixture).index_contracts;
}
test("recorded index fields and vocabularies stay aligned without a backend process", async () => {
  const recorded = await fixture();
  expect(Object.keys(RawDayIndexSchema.shape)).toEqual(recorded.raw_fields);
  expect(Object.keys(CompactIndexSchema.shape)).toEqual(recorded.compact_fields);
  expect(Object.keys(CompactEntrySchema.shape)).toEqual(recorded.entry_fields);
  expect(EntryStateSchema.options).toEqual(recorded.states);
  expect(PeriodSchema.options).toEqual(recorded.periods);
  expect(CompactEntrySchema.parse(recorded.legacy_entry)).toEqual({ ...recorded.legacy_entry, ...recorded.legacy_defaults });
});
test("index validation preserves named empty, lost and historical default meanings", async () => {
  const recorded = await fixture();
  const raw = {
    version: "2026-10-03", ledger: "editorial-selections", date: "2026-10-21",
    files: [recorded.filename], content_sha256: "a".repeat(64), listed_at: "2026-10-21T12:00:00Z",
  };
  expect(RawDayIndexSchema.parse(raw).bytes).toBeNull();
  expect(RawDayIndexSchema.safeParse({ ...raw, files: [recorded.filename, recorded.filename] }).success).toBe(false);
  expect(RawDayIndexSchema.safeParse({ ...raw, files: ["../escape.parquet"] }).success).toBe(false);
  expect(RawDayIndexSchema.safeParse({ ...raw, bytes: [] }).success).toBe(false);
  const base = {
    version: "2026-10-07", ledger: "editorial-selections", period: "daily",
    entries: [{ covers: "2026-10-21", rows: 0, bytes: 0, state: "empty" }],
  };
  expect(CompactIndexSchema.parse(base).entries[0]!.state).toBe("empty");
  const packed = {
    ...base,
    version: COMPACT_INDEX_VERSION,
    entries: [{
      covers: "2026-10-21", rows: 1, bytes: 128, file_sha256: "a".repeat(64),
    }],
  };
  expect(CompactIndexSchema.parse(packed).entries[0]!.file_sha256).toBe("a".repeat(64));
  const invalid = [
    { entries: [{ ...base.entries[0], file_sha256: "a".repeat(64) }] },
    { entries: [{ covers: "2026-10-21", rows: 1, bytes: 128, file_sha256: "not-a-digest" }] },
    { entries: [{ ...base.entries[0], state: "lost", rows: 1 }] },
    { entries: [{ ...base.entries[0], bytes: 1 }] },
    { entries: [base.entries[0], base.entries[0]] },
    { entries: [{ ...base.entries[0], covers: "2026-10" }] },
    { entries: [{ ...base.entries[0], lost_days: ["2026-10-21"] }] },
    { expired_through: "2025" },
    { period: "monthly", entries: [{ covers: "2026-10", rows: 0, bytes: 0, state: "lost" }] },
    { period: "monthly", entries: [{ covers: "2026-10", rows: 0, bytes: 0, lost_days: ["2026-10-32"] }] },
    { period: "monthly", entries: [{ covers: "2026-10", rows: 0, bytes: 0, lost_days: ["2026-09-30"] }] },
    { period: "monthly", entries: [{ covers: "2026-10", rows: 0, bytes: 0, lost_days: ["2026-10-02", "2026-10-01"] }] },
    { period: "yearly", expired_through: "2026", entries: [{ covers: "2026", rows: 0, bytes: 0 }] },
  ];
  for (const patch of invalid) expect(CompactIndexSchema.safeParse({ ...base, ...patch }).success).toBe(false);
});
