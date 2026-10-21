/** Verifies both identifier forms against Python's ledger identity rules. */
import { describe, expect, test } from "bun:test";
import { createUnitId } from "../src/uuid/unit-id";
import { createFileId } from "../src/uuid/file-id";

describe("Python ledger identity parity", () => {
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
  });
});
