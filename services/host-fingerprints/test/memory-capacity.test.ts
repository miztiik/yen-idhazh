/** Does total RAM retain kernel precision without inventing missing capacity? */
import { expect, test } from "bun:test";
import { rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { collectFingerprint } from "../src/collect-fingerprint";
import { parseMemoryTotalMib } from "../src/inspect/memory-capacity";
import { fixture } from "./fixture";

test("bounded meminfo transcripts preserve exact MiB and refuse invalid totals", async () => {
  const input = z.object({
    cases: z.array(z.object({
      name: z.string(), input: z.string(), expected: z.number().nullable(),
    })),
  }).parse(await Bun.file(new URL("../../../tests/fixtures/host-fingerprints/meminfo-cases.json", import.meta.url)).json());
  for (const entry of input.cases) {
    expect(parseMemoryTotalMib(entry.input), entry.name).toBe(entry.expected);
  }
});

test("missing, malformed and oversized meminfo leave capacity unavailable, not zero", async () => {
  const f = await fixture();
  try {
    const path = join(f.root, "proc/meminfo");
    const original = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(original.row.machine_memory_total_mib).toBe(16383.75);
    await rm(path);
    const missing = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(missing.row.machine_memory_total_mib).toBeNull();
    expect(missing.unavailable.machine_memory_total_mib).toBe("meminfo_unavailable");
    await writeFile(path, "MemTotal: 0 kB\n");
    const invalid = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(invalid.row.machine_memory_total_mib).toBeNull();
    expect(invalid.unavailable.machine_memory_total_mib).toBe("meminfo_invalid");
    await writeFile(path, `MemTotal: 16776960 kB\n${" ".repeat(f.config.max_input_bytes)}`);
    const oversized = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(oversized.row.machine_memory_total_mib).toBeNull();
    expect(oversized.unavailable["/proc/meminfo"]).toBe("input_too_large");
    expect(oversized.row.fingerprint).toBe(original.row.fingerprint);
  } finally { await f.cleanup(); }
});
