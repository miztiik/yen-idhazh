/** Which saved window is reused, and when do recorded clocks prove its result is newer? */
import { expect, test } from "bun:test";
import { FeedHealthReliabilitySchema } from "@idhazh/common-contracts";
import { selectSavedReliability } from "../src/read-ledger-history/saved-reliability";

const empty = () => FeedHealthReliabilitySchema.parse({
  productive: 0, attempted: 0, success_fraction: null, production_factor: null,
  from_day: "2026-10-30", through_day: "2026-10-31", complete: true,
});
const productive = () => FeedHealthReliabilitySchema.parse({
  ...empty(), productive: 1, attempted: 1, success_fraction: 1, production_factor: 1,
});

test("different widths ending on the same day remain separate questions for a changed window", () => {
  const narrow = empty();
  const wide = { ...productive(), from_day: "2026-10-29" };
  expect(selectSavedReliability([
    { at: "2026-10-29T10:00:00.000Z", value: wide },
    { at: "2026-10-29T10:00:00.000Z", value: narrow },
  ], { from_day: "2026-10-31", through_day: "2026-11-01" }, "2026-11-01T12:00:00.000Z"))
    .toEqual({ value: narrow, conflicting: [] });
});

test("definite same-window order selects the newer result without accepting a future clock", () => {
  const newer = productive();
  expect(selectSavedReliability([
    { at: "2026-10-29T10:00:00.000Z", value: empty() },
    { at: "2026-10-29T10:00:01.000Z", value: newer },
    { at: "2026-11-02T10:00:00.000Z", value: empty() },
  ], { from_day: "2026-10-30", through_day: "2026-10-31" }, "2026-10-31T12:00:00.000Z"))
    .toEqual({ value: newer, conflicting: [] });
});
