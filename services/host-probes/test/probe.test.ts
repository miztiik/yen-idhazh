/** Do bounded Linux inputs produce honest interval CPU and memory readings? */
import { afterEach, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { copyFileSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseCpuCounters, calculateCpuPercentages } from "../src/probe/cpu-sampler";
import { parseMemoryInfo, parseVmstat } from "../src/probe/memory-probe";
import { sampleHost } from "../src/probe/sample-host";
import { createSampleHandler, SAMPLE_PATH } from "../src/api/server";
import { loadConfig, ProbeConfigSchema } from "../src/config";
import { profileTask, startTaskProfile } from "../src/task-profile/task-profiler";
import { TaskProfileSchema } from "../src/task-profile/profile-schema";
import type { TaskProfile } from "../src/task-profile/profile-schema";
import { readProcessIdentity, readProcessMemory } from "../src/task-profile/process-memory";
import { TaskCollector } from "../src/task-profile/task-collector";
import { CollectorInputSchema } from "../src/task-profile/profile-schema";

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
  const processInput = JSON.parse(await fixture("host-probes/process-inputs.json"));
  for (const pid of [process.pid, processInput.pid]) {
    await mkdir(join(directory, String(pid)), { recursive: true });
    await Bun.write(join(directory, String(pid), "stat"), processInput.stat.replace("4242 ", `${pid} `));
    await Bun.write(join(directory, String(pid), "status"), processInput.status);
  }
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

  const config = await loadConfig();
  config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: true,
    cpu_window_ms: 30, poll_interval_ms: 10, max_retained_samples: 8 };
  const reports: TaskProfile[] = [];
  const options = {
    config, context: { platform: "linux", procRoot: directory },
    server: { pid: 4242, start_ticks: "12345" },
    report: (profile: TaskProfile) => { reports.push(profile); },
  };
  const identity = { pipeline_name: "recorded-work", task_name: "cpu-bound-work",
    run_id: "recorded-run", correlation_id: randomUUID(), request_id: randomUUID() };
  await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
  const watcher = await startTaskProfile(options, identity);
  if (watcher === null) throw new Error("Enabled task sampler did not start");
  copyFileSync(fileURLToPath(new URL("runtime/2026-08-30-probe-proc-stat-at-end.txt", fixtureRoot)), join(directory, "stat"));
  const processInput = JSON.parse(await fixture("host-probes/process-inputs.json"));
  await Bun.write(join(directory, String(process.pid), "status"), processInput.closing_status);
  const blockedAt = performance.now();
  // Real bounded CPU work prevents this event loop from running a sampling timer.
  while (performance.now() - blockedAt < 200) createHash("sha256").update(processInput.status).digest();
  const closing = watcher.close("success");
  expect(watcher.close("error")).toBe(closing);
  const profile = TaskProfileSchema.parse(await closing);
  expect(reports).toEqual([profile]);
  expect(profile.elapsed_ms).toBeGreaterThanOrEqual(200);
  expect(profile.periodic_sample_count).toBeGreaterThan(1);
  expect(profile.sample_count).toBe(profile.periodic_sample_count + 2);
  expect(profile.samples.length).toBeLessThanOrEqual(profile.config.max_retained_samples);
  expect(profile.cpu.value?.user).toBeCloseTo(53 / 7991 * 100, 10);
  expect(profile.processes.worker.closing.pid).toBe(process.pid);
  expect(profile.processes.worker.closing.memory_kb).toEqual({ rss: 700, hwm_lifetime: 900, anon: 500 });
  expect(profile.processes.worker.sampled_rss_max_kb).toBe(700);
  expect(profile.processes.worker.major_faults_delta).toBe(0);
  expect(profile.processes.server.closing.memory_kb.rss).toBe(600);
  expect(profile.machine_available_min_kb).toBe(8192000);
  expect(profile.machine_major_faults_delta).toBe(0);
  expect(profile.samples.some(sample => sample.cpu_window.full_window)).toBe(true);
  expect(profile.samples.every(sample => sample.observed_at.endsWith("Z"))).toBe(true);
  const collectorInput = CollectorInputSchema.parse({
    identity, config: config.task_profile, max_proc_bytes: config.max_proc_bytes,
    worker_pid: process.pid, server: options.server, context: options.context,
  });
  const bounded = new TaskCollector(collectorInput);
  for (let index = 0; index < config.task_profile.max_retained_samples * 2; index++) bounded.poll();
  const retained = bounded.close("success");
  expect(retained.sample_count).toBeGreaterThan(config.task_profile.max_retained_samples);
  expect(retained.samples).toHaveLength(config.task_profile.max_retained_samples);
  expect(bounded.close("error")).toBe(retained);
  await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
  const reset = new TaskCollector(collectorInput);
  await Bun.write(join(directory, "stat"), "cpu 1 0 0 1 0 0 0 0\n");
  reset.poll();
  await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-end.txt"));
  expect(reset.close("success").cpu.reason).toBe("counter_reset");
  await expect(profileTask(options, identity, () => { throw new Error("actual task failed"); }))
    .rejects.toThrow("actual task failed");
  expect(reports.at(-1)?.outcome).toBe("error");
  const abort = new AbortController();
  await expect(profileTask(options, identity, () => {
    abort.abort(new Error("task cancelled"));
    abort.signal.throwIfAborted();
  }, { signal: abort.signal })).rejects.toThrow("task cancelled");
  expect(reports.at(-1)?.outcome).toBe("cancelled");
  await expect(profileTask({ ...options, report: () => { throw new Error("report failed"); } },
    identity, () => { throw new Error("actual task failed"); })).rejects.toThrow(AggregateError);
  const quick = await startTaskProfile(options, identity);
  const partial = await quick!.close("success");
  expect(partial.samples[0]?.cpu_window.full_window).toBe(false);
  expect(partial.samples.at(-1)?.phase).toBe("closing");
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
  const context = { platform: "linux", procRoot: directory };
  const owned = { pid: 4242, start_ticks: "12345" };
  expect(readProcessIdentity(owned.pid, config.max_proc_bytes, context).value).toMatchObject(owned);
  expect(readProcessMemory(owned, config.max_proc_bytes, context).memory_kb.rss).toBe(600);
  expect(readProcessMemory({ ...owned, start_ticks: "1" }, config.max_proc_bytes, context).unavailable.major_faults).toBe("pid_reused");
  await Bun.write(join(directory, "4242", "status"), "VmRSS:\tbad kB\nVmHWM:\t900 kB\n");
  const missing = readProcessMemory(owned, config.max_proc_bytes, context);
  expect(missing.memory_kb).toEqual({ rss: null, hwm_lifetime: 900, anon: null });
  expect(missing.unavailable).toEqual({ "memory_kb.rss": "invalid_data", "memory_kb.anon": "missing_field" });
  await rm(join(directory, "4242", "stat"));
  expect(readProcessMemory(owned, config.max_proc_bytes, context).unavailable.major_faults).toBe("process_exited");
  const processInput = JSON.parse(await fixture("host-probes/process-inputs.json"));
  await Bun.write(join(directory, "4242", "stat"), processInput.stat.replace(") R ", ") Z "));
  expect(readProcessMemory(owned, config.max_proc_bytes, context).unavailable.major_faults).toBe("process_exited");
  const identity = { pipeline_name: "off", task_name: "off", run_id: "off", request_id: randomUUID(), correlation_id: randomUUID() };
  await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
  await mkdir(join(directory, "meminfo"));
  await rm(join(directory, String(process.pid), "stat"));
  await mkdir(join(directory, String(process.pid), "stat"));
  let cpuOnly: TaskProfile | undefined;
  await profileTask({
    config: { ...config, task_profile: { ...config.task_profile, enabled: true, memory_enabled: false } },
    context, report: profile => { cpuOnly = profile; },
  }, identity, () => "CPU-only work");
  expect(cpuOnly?.processes.worker.closing.unavailable["memory_kb.rss"]).toBe("configured_off");
  expect(cpuOnly?.samples.at(-1)?.unavailable["memory_kb.total"]).toBe("configured_off");
  // Unexpected I/O errors would fail collection; whole off must not read even this input.
  await rm(join(directory, "stat"));
  await mkdir(join(directory, "stat"));
  let reported = false;
  expect(await profileTask({ config, context, report: () => { reported = true; } }, identity, () => "actual work")).toBe("actual work");
  expect(reported).toBe(false);
  const enabled = { ...config, task_profile: { ...config.task_profile, enabled: true } };
  await expect(startTaskProfile({ config: enabled, context, report: () => {} }, {
    pipeline_name: "error", task_name: "error", run_id: "error", request_id: randomUUID(), correlation_id: randomUUID(),
  })).rejects.toThrow("collector");
});

test("configuration rejects unknown fields, missing fields and invalid controls by name", async () => {
  expect(ProbeConfigSchema.safeParse({}).success).toBe(false);
  const config = { ...(await loadConfig()), sample_interval_ms: 1, listen_host: "127.0.0.1", listen_port: 3005, max_proc_bytes: 1024 };
  expect(ProbeConfigSchema.safeParse(config).success).toBe(true);
  expect(config.task_profile.enabled).toBe(false);
  expect(config.task_profile.memory_enabled).toBe(false);
  for (const [field, value] of [
    ["cpu_window_ms", 0], ["poll_interval_ms", 0], ["max_retained_samples", 1], ["lifecycle_timeout_ms", 0],
  ] as const) expect(ProbeConfigSchema.safeParse({
    ...config, task_profile: { ...config.task_profile, [field]: value },
  }).success).toBe(false);
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
