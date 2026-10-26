/** Verifies both identifier forms against recorded ledger identity vectors. */
import { describe, expect, test } from "bun:test";
import { createUnitId } from "../src/uuid/unit-id";
import { createFileId, createPlannerFileId } from "../src/uuid/file-id";

describe("recorded ledger identity vectors", () => {
  test("uses the repository UUIDv5 namespace and generic pipeline identity", () => {
    expect(createUnitId({
      ledger: "covers",
      covers: "2026-10-20",
      runId: "2026-10-20-123",
      job: null,
      pipelineName: "plan",
      taskName: "source-runs",
      shard: 2,
      producer: "test.writer",
    })).toBe("6375f642-cc1d-54e3-bf2f-60112d783f1b");
  });

  test("preserves the legacy job identity seed", () => {
    expect(createUnitId({
      ledger: "covers",
      covers: "2026-10-20",
      runId: "2026-10-20-123",
      job: "harvest-feeds",
      pipelineName: null,
      taskName: null,
      shard: 2,
      producer: "test.writer",
    })).toBe("74bc5cd8-0518-57e4-b5a1-cba02ee73d15");
  });

  test("packs the clock and selected digest bits into UUIDv8", () => {
    expect(createFileId({
      unit: "6375f642-cc1d-54e3-bf2f-60112d783f1b",
      attempt: 3,
      writtenAtMs: 1792497600000,
    })).toBe("01a1592e-c600-84d0-96e4-7bb01708ce01");
    const plannerIds = Array.from({ length: 16 }, () => createPlannerFileId(1792497600000));
    expect(new Set(plannerIds).size).toBe(16);
    expect(plannerIds.every(id => /^01a1592e-c600-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id))).toBe(true);
    expect(() => createPlannerFileId(-1)).toThrow();
  });
});
