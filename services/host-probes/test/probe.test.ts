/** Do bounded Linux inputs produce honest interval CPU and memory readings? */
import { afterEach, expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseCpuCounters, calculateCpuPercentages } from "../src/probe/cpu-sampler";
import { parseMemoryInfo, parseVmstat } from "../src/probe/memory-probe";
import { sampleHost } from "../src/probe/sample-host";
import { createSampleHandler, SAMPLE_PATH } from "../src/api/server";
import { loadConfig, ProbeConfigSchema } from "../src/config";

const fixtureRoot = new URL("../../../tests/fixtures/", import.meta.url);
const temporaryDirectories: string[] = [];

async function fixture(path: string): Promise<string> {
  return Bun.file(new URL(path, fixtureRoot)).text();
}

async function procDirectory(): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), "idhazh-host-probes-"));
  temporaryDirectories.push(directory);
  await Promise.all([
    Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt")),
    Bun.write(join(directory, "meminfo"), await fixture("host-probes/meminfo.txt")),
    Bun.write(join(directory, "vmstat"), await fixture("host-probes/vmstat.txt")),
  ]);
  return directory;
}

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((path) => rm(path, { recursive: true, force: true })));
});

test("recorded Linux CPU interval and memory satisfy the Row 5 oracle", async () => {
  const start = parseCpuCounters(await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
  const end = parseCpuCounters(await fixture("runtime/2026-08-30-probe-proc-stat-at-end.txt"));
  const cpu = calculateCpuPercentages(start, end);
  expect(cpu.reason).toBeNull();
  expect(cpu.value).not.toBeNull();
  const percentages = Object.values(cpu.value!);
  expect(percentages.every((value) => value >= 0)).toBe(true);
  expect(Math.abs(percentages.reduce((sum, value) => sum + value, 0) - 100)).toBeLessThan(1);
  expect(cpu.value!.user).toBeCloseTo(53 / 7991 * 100, 10);
  expect(cpu.value!.system).toBeCloseTo(10 / 7991 * 100, 10);
  expect(cpu.value!.idle).toBeCloseTo(7928 / 7991 * 100, 10);
  expect(parseMemoryInfo(await fixture("host-probes/meminfo.txt")).value).toEqual({
    total: 16384256, free: 1024000, available: 8192000,
  });
  expect(parseVmstat(await fixture("host-probes/vmstat.txt")).value).toEqual({
    pgfault: 1234567, pgmajfault: 42, pswpin: 0, pswpout: 17,
  });
});

test("nice and interrupts are accounted for, steal is visible, and guests are not counted twice", () => {
  const start = parseCpuCounters("cpu 100 10 20 200 5 3 4 8 50 2");
  const end = parseCpuCounters("cpu 120 15 30 240 10 8 9 18 60 3");
  expect(calculateCpuPercentages(start, end)).toEqual({
    value: { user: 25, system: 20, idle: 40, iowait: 5, steal: 10 }, reason: null,
  });
});

test("missing, malformed, reset and unchanged counters do not invent utilization", () => {
  const counters = parseCpuCounters("cpu 100 0 30 100 5 0 0 1");
  expect(parseCpuCounters("cpu0 1 2 3 4").reason).toBe("invalid_data");
  expect(parseCpuCounters("cpu 1 2 3 4").reason).toBe("invalid_data");
  expect(parseCpuCounters("cpu 1 2 nope 4 5 6 7 8").reason).toBe("invalid_data");
  expect(calculateCpuPercentages(counters, counters).reason).toBe("no_ticks");
  expect(calculateCpuPercentages(counters, parseCpuCounters("cpu 101 0 31 110 4 0 0 1")).reason)
    .toBe("counter_reset");
  expect(calculateCpuPercentages(parseCpuCounters(""), counters).reason).toBe("invalid_data");
  expect(calculateCpuPercentages(
    parseCpuCounters("cpu 90071992547409920 0 0 0 0 0 0 0"),
    parseCpuCounters("cpu 90071992547409921 0 0 1 0 0 0 0"),
  ).value).toEqual({ user: 50, system: 0, idle: 50, iowait: 0, steal: 0 });
});

test("memory fields stay independently unavailable instead of becoming zero", () => {
  const memory = parseMemoryInfo("MemTotal: 123 kB\nMemFree: 1 MB\n");
  expect(memory.value).toEqual({ total: 123, free: null, available: null });
  expect(memory.unavailable).toEqual({ free: "invalid_data", available: "missing_field" });
  expect(parseMemoryInfo("MemTotal: 1 kB\nMemTotal: 2 kB").value.total).toBeNull();
  expect(parseVmstat("pgfault nope").reason).toBe("invalid_data");
});

test("periodic file sampling uses closing minus opening counters and closes with current memory", async () => {
  const directory = await procDirectory();
  for (const sample_interval_ms of [100, 200]) {
    const config = { ...(await loadConfig()), sample_interval_ms };
    await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
    const pending = sampleHost(config, { platform: "linux", procRoot: directory });
    const update = (async () => {
      await Bun.sleep(25);
      copyFileSync(
        fileURLToPath(new URL("runtime/2026-08-30-probe-proc-stat-at-end.txt", fixtureRoot)),
        join(directory, "stat"),
      );
    })();
    const [sample] = await Promise.all([pending, update]);
    expect(sample.interval_ms).toBeGreaterThanOrEqual(config.sample_interval_ms);
    expect(sample.cpu?.user).toBeCloseTo(53 / 7991 * 100, 10);
    expect(sample.memory_kb.available).toBe(8192000);
    expect(sample.vmstat?.pgmajfault).toBe(42);
    expect(sample.unavailable).toEqual({});
    expect(sample.sampled_at).toMatch(/Z$/);
  }
  const unchanged = await sampleHost(
    { ...(await loadConfig()), sample_interval_ms: 1 }, { platform: "linux", procRoot: directory },
  );
  expect(unchanged.cpu).toBeNull();
  expect(unchanged.unavailable.cpu).toBe("no_ticks");
});

test("the real HTTP handler uses the sampler without external network", async () => {
  const config = await loadConfig();
  const handler = createSampleHandler(config, { platform: "unsupported" });
  const response = await handler(new Request(`http://localhost${SAMPLE_PATH}`));
  expect(response.status).toBe(200);
  const sample = await response.json();
  expect(sample.cpu).toBeNull();
  expect(sample.memory_kb).toEqual({ total: null, free: null, available: null });
  expect(sample.unavailable.cpu).toBe("unsupported_platform");
  expect((await handler(new Request(`http://localhost${SAMPLE_PATH}`, { method: "POST" }))).status).toBe(405);
  expect((await handler(new Request("http://localhost/not-a-route"))).status).toBe(404);
});

test("HTTP sampling returns fixture memory and exposes a stopped CPU clock", async () => {
  const directory = await procDirectory();
  const handler = createSampleHandler(
    { ...(await loadConfig()), sample_interval_ms: 1 }, { platform: "linux", procRoot: directory },
  );
  const response = await handler(new Request(`http://localhost${SAMPLE_PATH}`));
  const sample = await response.json();
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(sample.memory_kb.total).toBe(16384256);
  expect(sample.vmstat.pgmajfault).toBe(42);
  expect(sample.cpu).toBeNull();
  expect(sample.unavailable).toEqual({ cpu: "no_ticks" });
});

test("missing and oversized proc files are explicit while valid siblings survive", async () => {
  const directory = await procDirectory();
  const config = { ...(await loadConfig()), sample_interval_ms: 1 };
  await rm(join(directory, "stat"));
  await Bun.write(join(directory, "vmstat"), "x".repeat(config.max_proc_bytes + 1));
  const sample = await sampleHost(config, { platform: "linux", procRoot: directory });
  expect(sample.cpu).toBeNull();
  expect(sample.unavailable.cpu).toBe("missing_file");
  expect(sample.memory_kb.total).toBe(16384256);
  expect(sample.vmstat).toBeNull();
  expect(sample.unavailable.vmstat).toBe("too_large");
  await rm(join(directory, "meminfo"));
  const missingMemory = await sampleHost(config, { platform: "linux", procRoot: directory });
  expect(missingMemory.memory_kb).toEqual({ total: null, free: null, available: null });
  expect(missingMemory.unavailable["memory_kb.total"]).toBe("missing_file");
});

test("configuration rejects unknown fields, missing fields and invalid controls by name", () => {
  expect(ProbeConfigSchema.safeParse({}).success).toBe(false);
  const config = { sample_interval_ms: 1, listen_host: "127.0.0.1", listen_port: 3005, max_proc_bytes: 1024 };
  expect(ProbeConfigSchema.safeParse(config).success).toBe(true);
  for (const sample_interval_ms of [0, -1, 0.5, NaN, Infinity, "1"]) {
    const result = ProbeConfigSchema.safeParse({ ...config, sample_interval_ms });
    expect(result.success).toBe(false);
    if (!result.success) expect(result.error.issues[0]?.path).toEqual(["sample_interval_ms"]);
  }
  expect(ProbeConfigSchema.safeParse({ ...config, listen_port: 65536 }).success).toBe(false);
  expect(ProbeConfigSchema.safeParse({ ...config, surprise: true }).success).toBe(false);
});

test("configuration file errors fail explicitly without exposing absolute paths", async () => {
  const directory = await procDirectory();
  const path = join(directory, "config.json");
  await expect(loadConfig(path)).rejects.toThrow("Cannot read config/host-probes.json as JSON");
  await Bun.write(path, "{");
  await expect(loadConfig(path)).rejects.toThrow("Cannot read config/host-probes.json as JSON");
  await Bun.write(path, JSON.stringify({ sample_interval_ms: 0 }));
  await expect(loadConfig(path)).rejects.toThrow("sample_interval_ms");
});

test("the one-shot CLI returns a sample and invalid arguments fail without success output", async () => {
  const entrypoint = fileURLToPath(new URL("../src/index.ts", import.meta.url));
  const process = Bun.spawn([Bun.which("bun")!, entrypoint, "--sample"], { stdout: "pipe", stderr: "pipe" });
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(process.stdout).text(), new Response(process.stderr).text(), process.exited,
  ]);
  expect(exitCode).toBe(0);
  expect(stderr).toBe("");
  const sample = JSON.parse(stdout);
  expect(sample.sampled_at).toMatch(/Z$/);
  expect(sample).toHaveProperty("cpu");
  expect(sample).toHaveProperty("memory_kb");
  expect(sample).toHaveProperty("vmstat");
  const invalid = Bun.spawn([Bun.which("bun")!, entrypoint, "--unknown"], { stdout: "pipe", stderr: "pipe" });
  const [invalidOut, invalidError, invalidExit] = await Promise.all([
    new Response(invalid.stdout).text(), new Response(invalid.stderr).text(), invalid.exited,
  ]);
  expect(invalidExit).toBe(1);
  expect(invalidOut).toBe("");
  expect(JSON.parse(invalidError).error).toContain("Usage:");
});
