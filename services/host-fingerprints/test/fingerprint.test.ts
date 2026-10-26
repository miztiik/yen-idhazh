/** Do real bounded Linux files produce complete, honest hardware measurements? */
import { expect, test } from "bun:test";
import { rm, writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { collectFingerprint } from "../src/collect-fingerprint";
import { ServiceConfigSchema, SelectedSettingsSchema } from "../src/config";
import { parseCpuIds } from "../src/inspect/cpu-topology";
import { probeBufferMib } from "../src/inspect/copy-bandwidth";
import { fingerprintV2 } from "@idhazh/common-contracts";
import { fixture } from "./fixture";

test("full Linux fixture collects hardware, quota, affinity, clocks, placement and task counters", async () => {
  const f = await fixture();
  try {
    const { row } = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(row).toMatchObject(f.input.expected);
    expect(row.vm_size).toBe("Standard_D4ds_v5");
    expect(row.cpu_target_measured_at! >= row.measured_at!).toBe(true);
    expect(row).toMatchObject({ model_load_ms: 123.5, job_seconds: 42, server_prompt_tokens: 320, server_prompt_seconds: 1.25, fingerprint_version: 2, memcpy_probe_mib: 0, memcpy_gib_s: null });
  } finally { await f.cleanup(); }
});
test.each(["win32", "darwin"] as const)("unsupported %s never fabricates readings", async (platform) => {
  const f = await fixture();
  try {
    const result = await collectFingerprint(f.capture, f.config, f.settings, { ...f.inspection, platform });
    expect(result.row.cpu_logical_processors).toBeNull();
    expect(result.row.fingerprint).toBeNull();
    expect(result.row.cpu_quota_state).toBeNull();
    expect(result.row.machine_memory_total_mib).toBeNull();
    expect(result.unavailable.machine_memory_total_mib).toBe("unsupported_platform");
    expect(result.unavailable.platform).toBe("unsupported_platform");
  } finally { await f.cleanup(); }
});
test.each(["", "0-3,2", "1-0", "1,x", "0-999999999999", "-1", "0,,1"])("rejects malformed or unbounded online list %s", (input) => {
  expect(parseCpuIds(input, 32)).toBeNull();
});
test("sparse CPU ids remain identities, not the highest id plus one", () => {
  expect(parseCpuIds("0,2,7-9", 5)).toEqual([0, 2, 7, 8, 9]);
  expect(parseCpuIds("0,2,7-9", 4)).toBeNull();
});
test("missing one topology or frequency entry never shrinks the logical count", async () => {
  const f = await fixture();
  try {
    await rm(join(f.root, "sys/devices/system/cpu/cpu9/topology/core_id"));
    await rm(join(f.root, "sys/devices/system/cpu/cpu9/cpufreq/cpuinfo_max_freq"));
    const { row, unavailable } = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(row.cpu_logical_processors).toBe(4);
    expect(row.cpu_physical_cores).toBeNull();
    expect(row.cpu_reported_max_mhz).toBeNull();
    expect(unavailable.cpu_physical_cores).toBe("incomplete_topology");
  } finally { await f.cleanup(); }
});
test("unavailable ancestor makes quota unknown even with a finite child", async () => {
  const f = await fixture();
  try {
    await rm(join(f.root, "sys/fs/cgroup/jobs/cpu.max"));
    const { row } = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(row.cpu_quota_state).toBe("unavailable");
    expect(row.cpu_quota_cores).toBeNull();
    expect(row.cpu_allowed_processors).toBe(2);
  } finally { await f.cleanup(); }
});
test("v1 quota includes every ancestor and selects the tightest", async () => {
  const f = await fixture();
  try {
    await writeFile(join(f.root, "proc/self/cgroup"), "2:cpu,cpuacct:/jobs/task\n");
    for (const [node, amount] of [["", -1], ["jobs", 50000], ["jobs/task", 200000]] as const) {
      const path = join(f.root, "sys/fs/cgroup/cpu", node);
      await mkdir(path, { recursive: true });
      await writeFile(join(path, "cpu.cfs_quota_us"), String(amount));
      await writeFile(join(path, "cpu.cfs_period_us"), "100000");
    }
    const result = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(result.row.cpu_quota_cores).toBe(0.5);
    expect(result.row.cpu_quota_state).toBe("finite");
    await rm(join(f.root, "sys/fs/cgroup/cpu/jobs/cpu.cfs_quota_us"));
    expect((await collectFingerprint(f.capture, f.config, f.settings, f.inspection)).row.cpu_quota_state).toBe("unavailable");
  } finally { await f.cleanup(); }
});
test("all unlimited ancestors, missing affinity and bounded depth remain honest", async () => {
  const f = await fixture();
  try {
    for (const path of ["", "jobs", "jobs/task"]) await writeFile(join(f.root, "sys/fs/cgroup", path, "cpu.max"), "max 100000");
    await writeFile(join(f.root, "proc/self/status"), "Cpus_allowed_list:\t11\n");
    const result = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(result.row.cpu_quota_state).toBe("unlimited");
    expect(result.row.cpu_allowed_processors).toBeNull();
    f.config.max_cgroup_depth = 1;
    expect((await collectFingerprint(f.capture, f.config, f.settings, f.inspection)).row.cpu_quota_state).toBe("unavailable");
  } finally { await f.cleanup(); }
});
test.each(["-1 100000", "0 100000", "200000 0", "max nope", "1 2 extra"])("invalid v2 quota %s cannot become a reading", async (quota) => {
  const f = await fixture();
  try {
    await writeFile(join(f.root, "sys/fs/cgroup/jobs/cpu.max"), quota);
    const { row } = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(row.cpu_quota_state).toBe("unavailable");
    expect(row.cpu_quota_cores).toBeNull();
  } finally { await f.cleanup(); }
});
test("frequency off and oversized cpuinfo have explicit unavailable reasons", async () => {
  const f = await fixture();
  try {
    f.settings.observability.host_fingerprint_frequency_enabled = false;
    const disabled = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(disabled.row.cpu_observed_mhz).toBeNull();
    expect(disabled.unavailable.cpu_reported_max_mhz).toBe("configured_off");
    f.config.max_input_bytes = 32;
    const bounded = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(bounded.row.cpu_vendor).toBeNull();
    expect(bounded.unavailable["/proc/cpuinfo"]).toBe("input_too_large");
  } finally { await f.cleanup(); }
});
test("configured copy uses derived cache-clearing buffers and measures real transfers", async () => {
  const f = await fixture();
  try {
    expect(probeBufferMib(1, 50331648, 2)).toBe(96);
    expect(probeBufferMib(0, 50331648, 2)).toBe(0);
    await writeFile(join(f.root, "sys/devices/system/cpu/cpu0/cache/index2/size"), "1K");
    f.settings.observability.host_fingerprint_bandwidth_jobs = ["inspect-host"];
    f.settings.observability.host_fingerprint_bandwidth_floor_mib = 1;
    const { row } = await collectFingerprint(f.capture, f.config, f.settings, f.inspection);
    expect(row.memcpy_probe_mib).toBe(2);
    expect(row.memcpy_gib_s).toBeGreaterThan(0);
    expect(row.fingerprint).toBe(fingerprintV2(row));
  } finally { await f.cleanup(); }
});
test("authored controls refuse missing fields and invalid settings", async () => {
  const f = await fixture();
  try {
    expect(ServiceConfigSchema.safeParse({ ...f.config, max_input_bytes: 0 }).success).toBe(false);
    expect(ServiceConfigSchema.safeParse({ ...f.config, metadata_url: "https://example.org" }).success).toBe(false);
    expect(SelectedSettingsSchema.safeParse({ ...f.settings, observability: {} }).success).toBe(false);
    for (const value of [undefined, "false"]) {
      expect(SelectedSettingsSchema.safeParse({
        ...f.settings, observability: { ...f.settings.observability, host_fingerprint_placement_enabled: value },
      }).success).toBe(false);
    }
  } finally { await f.cleanup(); }
});
test("recorded placement parses independently; explicit opt-out reads no metadata", async () => {
  const f = await fixture();
  try {
    const { parsePlacement, collectPlacement } = await import("../src/inspect/placement");
    expect(parsePlacement(f.input.metadata)).toEqual({
      vm_size: "Standard_D4ds_v5", vm_location: "eastus", vm_zone: "1", vm_fault_domain: "0",
    });
    expect(parsePlacement({ vmSize: 123 })).toBeNull();
    f.config.metadata_url = null;
    const unavailable: Record<string, string> = {};
    expect(await collectPlacement(f.config, f.settings, { unavailable })).toBeNull();
    expect(unavailable.placement).toBe("configured_off");
  } finally { await f.cleanup(); }
});
test.skipIf(process.platform !== "linux")("live Linux collection, distinct from Windows fixture evidence", async () => {
  const f = await fixture();
  try {
    const result = await collectFingerprint(f.capture, f.config, f.settings, { metadata: Response.json(f.input.metadata) });
    expect(result.row.cpu_logical_processors).toBeGreaterThan(0);
    expect(result.row.cpu_allowed_processors).toBeGreaterThan(0);
    console.error(JSON.stringify({ event: "live_linux_host", cpu_model: result.row.cpu_model, logical_processors: result.row.cpu_logical_processors, quota_state: result.row.cpu_quota_state }));
  } finally { await f.cleanup(); }
});
