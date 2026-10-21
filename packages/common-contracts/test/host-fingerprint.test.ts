/** Does the complete TS host contract retain the recorded existing hardware row? */
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { HostFingerprintRowSchema, fingerprintV2 } from "../src/index";

const fixtureUrl = new URL("../../../tests/fixtures/host-fingerprints/host-schema.json", import.meta.url);
test("retains every recorded host field and binds to the named authority's field set", async () => {
  const fixture = await Bun.file(fixtureUrl).json();
  const row = HostFingerprintRowSchema.parse(fixture.row);
  expect(row).toEqual(fixture.row);
  expect(Object.keys(row)).toEqual(Object.keys(fixture.columns));
  const source = await Bun.file(new URL("../../../backend/idhazh/contracts/host_fingerprint.py", import.meta.url)).text();
  const declaration = source.split("class HostFingerprintRow(Contract):")[1]?.split("    def __init__(")[0];
  const names = [...(declaration ?? "").matchAll(/^    ([a-z]\w*): /gm)].map((match) => match[1]);
  expect(["version", ...names]).toEqual(Object.keys(fixture.columns));
  expect(row.fingerprint).toBe(createHash("sha256").update(fixture.identity_ascii_json, "ascii").digest("hex").slice(0, 16));
});
test("algorithm 2 excludes capacity, microcode, placement, clocks and caller context", async () => {
  const { row } = await Bun.file(fixtureUrl).json();
  expect(fingerprintV2(row)).toBe("27f9cc4dc522f48d");
  expect(fingerprintV2({ ...row, cpu_allowed_processors: 1, microcode: "changed", cpu_model: row.cpu_model })).toBe(row.fingerprint);
  expect(fingerprintV2({ ...row, cpu_model: "another CPU" })).not.toBe(row.fingerprint);
  expect(() => fingerprintV2({ ...row, flags: "avx2 avx2" })).toThrow();
  expect(() => fingerprintV2({ ...row, cpu_family: -1 })).toThrow();
  expect(fingerprintV2({ cpu_family: null, cpu_model: null, cpu_model_number: null, cpu_stepping: null, cpu_vendor: null, flags: "", l3_cache_bytes: 0 })).toBeNull();
});
test("algorithm 2 uses recorded ASCII escaping for non-ASCII CPU labels", async () => {
  const fixture = await Bun.file(fixtureUrl).json();
  const expected = fixture.unicode_identity;
  expect(fingerprintV2({ ...fixture.row, cpu_model: expected.cpu_model })).toBe(expected.fingerprint);
  expect(createHash("sha256").update(expected.ascii_json, "ascii").digest("hex").slice(0, 16)).toBe(expected.fingerprint);
});
test.each([
  { pipeline_name: null }, { job: "wrong-task" }, { shard: true }, { cpu_physical_cores: 5 },
  { cpu_allowed_processors: 5 }, { cpu_quota_state: "unlimited" },
  { cpu_target_measured_at: null }, { cpu_target_measured_at: "2026-10-21T17:00:00Z" },
  { measured_at: "2026-02-30T00:00:00Z" }, { fingerprint: "0".repeat(16) },
  { cpu_family: "6" }, { boot_seconds: Infinity }, { server_prompt_tokens: 2 ** 63 },
  { extra: 1 }, { version: "1999-01-01" }, { cpu_logical_processors: 0 },
])("refuses inconsistent or lossy host input %j", async (patch) => {
  const fixture = await Bun.file(fixtureUrl).json();
  expect(HostFingerprintRowSchema.safeParse({ ...fixture.row, ...patch }).success).toBe(false);
});
test("accepts supported normalized versions without changing recorded cells", async () => {
  const fixture = await Bun.file(fixtureUrl).json();
  for (const version of ["2026-10-10", "2026-10-12", "2026-10-14"] as const) {
    expect(HostFingerprintRowSchema.parse({ ...fixture.row, version }).version).toBe(version);
  }
});
