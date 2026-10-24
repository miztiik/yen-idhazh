/** Do bounded Linux inputs produce honest interval CPU and memory readings? */
import { afterEach, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { copyFileSync, writeFileSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseCpuCounters, calculateCpuPercentages } from "../src/probe/cpu-sampler";
import { parseMemoryInfo, parseVmstat } from "../src/probe/memory-probe";
import { sampleHost } from "../src/probe/sample-host";
import { createSampleHandler, SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../src/api/server";
import { loadConfig, ProbeConfigSchema } from "../src/config";
import { profileTask, startTaskProfile } from "../src/task-profile/task-profiler";
import { TaskProfileSchema } from "../src/task-profile/profile-schema";
import type { TaskProfile } from "../src/task-profile/profile-schema";
import { readProcessMemory } from "../src/task-profile/process-memory";
import { parseProcessStat, readProcessIdentity } from "../src/task-profile/process-stat";
import { calculateProcessCpu } from "../src/task-profile/process-cpu";
import { parseClockTicks } from "../src/task-profile/clock-ticks";
import { TaskCollector } from "../src/task-profile/task-collector";
import { CollectorInputSchema } from "../src/task-profile/profile-schema";
import { startCacheCounters } from "../src/cache-probe/cache-counters";
import { measureWorkingSetLatency } from "../src/cache-probe/working-set-latency";
import { classifyPerfFailure, parsePerfCounters } from "../src/cache-probe/perf-output";
import { CacheProbeController } from "../src/cache-probe/cache-controller";
import { parseMultichaseOutput } from "../src/cache-probe/latency-output";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../src/api/task-command-schema";

const fixtureRoot = new URL("../../../tests/fixtures/", import.meta.url);
const temporaryDirectories: string[] = [];

async function fixture(path: string): Promise<string> {
  return Bun.file(new URL(path, fixtureRoot)).text();
}

function command(path: string, body: unknown, signal?: AbortSignal): Request {
  return new Request(`http://localhost${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    ...(signal === undefined ? {} : { signal }),
  });
}

function taskIdentity() {
  return { pipeline_name: "recorded-work", task_name: "pinned-task", run_id: "recorded-run",
    correlation_id: randomUUID(), request_id: randomUUID() };
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
  const recorded = JSON.parse(await fixture("host-probes/process-inputs.json"));
  const opening = parseProcessStat(recorded.pid, recorded.stat);
  if (opening.reason !== null) throw new Error("Recorded process stat must contain its identity and counters");
  const clock = parseClockTicks(recorded.clock_ticks);
  expect(clock).toEqual({ value: 100, reason: null });
  const malformed = parseProcessStat(recorded.pid, recorded.stat.replace("7 0 3 0", "7 0 invalid 0"));
  expect(malformed.reason).toBeNull();
  expect(malformed.value?.cpu.reason).toBe("invalid_data");
  expect(malformed.value?.major_faults.value).toBe(7);
  for (const interval of recorded.cpu_intervals) {
    const closing = parseProcessStat(recorded.pid, interval.closing_stat);
    if (closing.reason !== null) throw new Error(`Invalid recorded process interval: ${interval.name}`);
    expect(calculateProcessCpu(opening.value.cpu, closing.value.cpu, interval.elapsed_ms, clock)).toEqual({
      value: { cpu_time_ms: interval.cpu_time_ms, percent_one_core: interval.percent_one_core }, reason: null,
    });
  }
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
  expect(classifyPerfFailure("No permission to enable LLC-loads:u event.")).toBe("permission_denied");
  expect(classifyPerfFailure("Cannot find PMU `cpu'")).toBe("event_unsupported");
  for (const text of ["", "NaN;;LLC-loads:u;1;100.00", "1;ns;LLC-loads:u;1;100.00",
    "1;;cache-references;1;100.00", "1;;LLC-loads:u;0;100.00", "1;;LLC-loads:u;1;0.00",
    "1;;LLC-loads:u;1;101.00", "9007199254740992;;LLC-loads:u;1;100.00"]) {
    expect(() => parsePerfCounters(text, ["LLC-loads:u"])).toThrow();
  }
  expect(() => parseMultichaseOutput("", {
    working_set_bytes: 4096, stride_bytes: 64, tlb_locality_bytes: 4096, samples: 2,
  })).toThrow();
  // These are CSV arithmetic inputs, not hardware readings or evidence that a host exposed a PMU.
  const format = parsePerfCounters("7;;LLC-loads:u;500;50.00;;\n0;;LLC-load-misses:u;500;50.00;;", ["LLC-loads:u", "LLC-load-misses:u"]);
  expect(format.map(event => event.count)).toEqual([7, 0]);
  expect(format.every(event => event.time_enabled_ns_estimate === 1000 && event.multiplexing === "reported")).toBe(true);
  const unsupported = parsePerfCounters("<not supported>;;LLC-loads:u;0;100.00;;\n<not counted>;;LLC-load-misses:u;0;100.00;;",
    ["LLC-loads:u", "LLC-load-misses:u"]);
  expect(unsupported.map(event => event.support)).toEqual(["unsupported", "not_counted"]);
  expect(unsupported.every(event => event.count === null && event.running_percent === null)).toBe(true);
  const start = { value: { user: 90071992547409920n, system: 7n }, reason: null };
  const end = { value: { user: 90071992547409921n, system: 7n }, reason: null };
  const clock = parseClockTicks("250\n");
  expect(calculateProcessCpu(start, end, 2, clock)).toEqual({
    value: { cpu_time_ms: 4, percent_one_core: 200 }, reason: null,
  });
  expect(calculateProcessCpu(end, start, 1000, clock).reason).toBe("counter_reset");
  expect(calculateProcessCpu(start, start, 0, clock).reason).toBe("no_interval");
  expect(calculateProcessCpu(start, start, 1000, clock).value?.percent_one_core).toBe(0);
  expect(calculateProcessCpu(start, end, 1000, { value: null, reason: "clock_ticks_unavailable" }).reason)
    .toBe("clock_ticks_unavailable");
  for (const text of ["", "0", "-1", "NaN", "100 100", "1.5", "9007199254740992"]) {
    expect(parseClockTicks(text).reason).toBe("invalid_data");
  }
  expect(parseProcessStat(4242, "4242 bad stat").reason).toBe("invalid_data");
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
    const observedAt = performance.now();
    const pending = sampleHost(config, { platform: "linux", procRoot: directory });
    const update = (async () => {
      await Bun.sleep(25);
      copyFileSync(
        fileURLToPath(new URL("runtime/2026-08-30-probe-proc-stat-at-end.txt", fixtureRoot)),
        join(directory, "stat"),
      );
    })();
    const [sample] = await Promise.all([pending, update]);
    expect(sample.interval_ms).toBeGreaterThan(0);
    expect(sample.interval_ms).toBeLessThanOrEqual(performance.now() - observedAt);
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
  config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true,
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
    worker_pid: process.pid, target: null, clock_ticks_per_second: parseClockTicks(processInput.clock_ticks),
    expires_after_ms: null, server: options.server, context: options.context,
  });
  const bounded = new TaskCollector(collectorInput);
  for (let index = 0; index < config.task_profile.max_retained_samples * 2; index++) bounded.poll();
  const retained = bounded.close("success");
  expect(retained.sample_count).toBeGreaterThan(config.task_profile.max_retained_samples);
  expect(retained.samples).toHaveLength(config.task_profile.max_retained_samples);
  expect(bounded.close("error")).toBe(retained);
  const machineOnly = new TaskCollector(CollectorInputSchema.parse({
    ...collectorInput, config: { ...collectorInput.config, memory_enabled: false },
  })).close("success");
  expect(machineOnly.machine_available_min_kb).toBe(8192000);
  expect(machineOnly.processes.worker.closing.unavailable["memory_kb.rss"]).toBe("configured_off");
  expect(retained.processes.worker.cpu.value).toEqual({ cpu_time_ms: 0, percent_one_core: 0 });
  expect(retained.processes.worker.cpu_interval_ms).toBeGreaterThan(0);
  const processStat = join(directory, String(process.pid), "stat");
  const openingStat = processInput.stat.replace("4242 ", `${process.pid} `);
  for (const failure of ["counter_reset", "pid_reused"] as const) {
    await Bun.write(processStat, openingStat);
    const processCollector = new TaskCollector(CollectorInputSchema.parse({
      ...collectorInput, server: null, config: { ...collectorInput.config, memory_enabled: false },
    }));
    await Bun.write(processStat, failure === "counter_reset" ? openingStat.replace("7 0 3 0", "7 0 2 0")
      : openingStat.replace("12345", "12346"));
    processCollector.poll();
    await Bun.write(processStat, openingStat.replace("7 0 3 0", "7 0 103 50"));
    for (let index = 0; index <= config.task_profile.max_retained_samples; index++) processCollector.poll();
    const failed = processCollector.close("success");
    expect(failed.samples).toHaveLength(config.task_profile.max_retained_samples);
    expect(failed.processes.worker.cpu).toEqual({ value: null, reason: failure });
    expect(failed.processes.worker.closing.cpu_window.cpu.reason).toBe(failure);
    expect(failed.end_reason).toBe(failure === "pid_reused" ? "pid_reused" : "task_settled");
  }
  await Bun.write(processStat, openingStat);
  await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
  const reset = new TaskCollector(CollectorInputSchema.parse({
    ...collectorInput, config: {
      ...collectorInput.config, cpu_window_ms: collectorInput.config.lifecycle_timeout_ms,
      max_retained_samples: Math.ceil(collectorInput.config.lifecycle_timeout_ms / collectorInput.config.poll_interval_ms) + 2,
    },
  }));
  await Bun.write(join(directory, "stat"), "cpu 1 0 0 1 0 0 0 0\n");
  reset.poll();
  await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-end.txt"));
  const resetProfile = reset.close("success");
  expect(resetProfile.cpu.reason).toBe("counter_reset");
  expect(resetProfile.samples.at(-1)?.cpu_window.cpu.reason).toBe("counter_reset");
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
  await handler.close();
  const directory = await procDirectory();
  await rm(join(directory, "stat"));
  await mkdir(join(directory, "stat"));
  await rm(join(directory, "4242", "stat"));
  await mkdir(join(directory, "4242", "stat"));
  const disabled = createSampleHandler({ ...config, task_profile: { ...config.task_profile, max_profile_handles: 1 } },
    { platform: "linux", procRoot: directory }, () => { throw new Error("Disabled profiles must not report"); });
  const input = { identity: taskIdentity(), target: { pid: 4242, start_ticks: "12345" } };
  for (let index = 0; index < 3; index++) {
    const start = await disabled(command(START_TASK_PROFILE_PATH, input));
    expect(start.status).toBe(200);
    expect(await start.json()).toEqual({ status: "disabled", reason: "configured_off" });
  }
  expect(await (await disabled(command(STOP_TASK_PROFILE_PATH, { handle: randomUUID(), outcome: "success" }))).json())
    .toEqual({ status: "disabled", reason: "configured_off" });
  for (const field of ["procRoot", "config", "path", "executable", "url"]) {
    expect((await disabled(command(START_TASK_PROFILE_PATH, { ...input, [field]: "refused" }))).status).toBe(400);
  }
  expect((await disabled(command(START_TASK_PROFILE_PATH, { ...input, target: { pid: 0, start_ticks: "12345" } }))).status).toBe(400);
  expect((await disabled(command(STOP_TASK_PROFILE_PATH, { handle: "not-a-handle", outcome: "success" }))).status).toBe(400);
  expect((await disabled(new Request(`http://localhost${START_TASK_PROFILE_PATH}`))).status).toBe(405);
  expect((await disabled(new Request(`http://localhost${START_TASK_PROFILE_PATH}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{",
  }))).status).toBe(400);
  for (const declared of [false, true]) {
    const body = "x".repeat(config.max_request_body_bytes + 1);
    const response = await disabled(new Request(`http://localhost${START_TASK_PROFILE_PATH}`, {
      method: "POST", body, headers: { "Content-Type": "application/json",
        ...(declared ? { "Content-Length": String(body.length) } : {}) },
    }));
    expect(response.status).toBe(413);
  }
  expect((await disabled(new Request(`http://localhost${START_TASK_PROFILE_PATH}`, {
    method: "POST", body: JSON.stringify(input), headers: { "Content-Type": "application/json", Origin: "https://untrusted.example" },
  }))).status).toBe(400);
  await disabled.close();
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
  await handler.close();
  const config = await loadConfig();
  config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: false, max_profile_handles: 1 };
  const profiles: TaskProfile[] = [];
  const profilesHandler = createSampleHandler(config, { platform: "linux", procRoot: directory }, profile => { profiles.push(profile); });
  const input = { identity: taskIdentity(), target: { pid: 4242, start_ticks: "12345" } };
  try {
    expect((await profilesHandler(command(START_TASK_PROFILE_PATH, {
      ...input, target: { ...input.target, start_ticks: "12346" },
    }))).status).toBe(409);
    const competing = await Promise.all([
      profilesHandler(command(START_TASK_PROFILE_PATH, input)),
      profilesHandler(command(START_TASK_PROFILE_PATH, input)),
    ]);
    expect(competing.map(result => result.status).sort()).toEqual([200, 429]);
    const started = StartTaskProfileResponseSchema.parse(await competing.find(result => result.status === 200)!.json());
    if (started.status !== "started") throw new Error("Enabled HTTP task profile did not start");
    expect(started.target).toEqual(input.target);
    expect(Date.parse(started.expires_at)).toBeGreaterThan(Date.now());
    const stopping = await Promise.all([
      profilesHandler(command(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "success" })),
      profilesHandler(command(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "error" })),
    ]);
    expect(stopping.map(result => result.status)).toEqual([200, 200]);
    const bodies = await Promise.all(stopping.map(result => result.text()));
    expect(bodies[0]).toBe(bodies[1]);
    const stopped = StopTaskProfileResponseSchema.parse(JSON.parse(bodies[0]!));
    if (stopped.status !== "stopped") throw new Error("Enabled HTTP task profile did not stop");
    expect(stopped.end_reason).toBe("explicit_stop");
    expect(stopped.profile.outcome).toBe("success");
    expect(stopped.profile.processes.worker.closing.pid).toBe(input.target.pid);
    expect(stopped.profile.processes.worker.closing.start_ticks).toBe(input.target.start_ticks);
    expect(stopped.profile.processes.worker.closing.unavailable["memory_kb.rss"]).toBe("configured_off");
    expect(profiles).toEqual([stopped.profile]);
    const next = StartTaskProfileResponseSchema.parse(await (await profilesHandler(command(START_TASK_PROFILE_PATH, input))).json());
    if (next.status !== "started") throw new Error("Completed handles must not exhaust capacity");
    expect((await profilesHandler(command(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "success" }))).status).toBe(404);
    expect((await profilesHandler(command(STOP_TASK_PROFILE_PATH, { handle: next.handle, outcome: "cancelled" }))).status).toBe(200);
    const aborted = new AbortController();
    aborted.abort();
    expect((await profilesHandler(command(START_TASK_PROFILE_PATH, input, aborted.signal))).status).toBe(400);
    expect(profiles).toHaveLength(2);
    const recorded = JSON.parse(await fixture("host-probes/process-inputs.json"));
    const openingRace = startTaskProfile({
      config, context: { platform: "linux", procRoot: directory }, target: input.target,
      report: () => { throw new Error("A refused opening pin must not report a profile"); },
    }, input.identity);
    writeFileSync(join(directory, "4242", "stat"), recorded.stat.replace("12345", "12346"));
    await expect(openingRace).rejects.toThrow("pin cannot be verified");
    await Bun.write(join(directory, "4242", "stat"), recorded.stat);
    const abortDuringStart = new AbortController();
    const interrupted = startTaskProfile({
      config, context: { platform: "linux", procRoot: directory }, target: input.target,
      report: () => { throw new Error("An aborted start must not report a completed task"); },
    }, input.identity, { signal: abortDuringStart.signal });
    queueMicrotask(() => abortDuringStart.abort());
    await expect(interrupted).rejects.toThrow("start aborted");
    await rm(join(directory, "stat"));
    await mkdir(join(directory, "stat"));
    expect((await profilesHandler(command(START_TASK_PROFILE_PATH, input))).status).toBe(500);
    await rm(join(directory, "stat"), { recursive: true });
    await Bun.write(join(directory, "stat"), await fixture("runtime/2026-08-30-probe-proc-stat-at-start.txt"));
  } finally { await profilesHandler.close(); }
  for (const end_reason of ["owner_exited", "expired", "service_stopped"] as const) {
    let completed: (profile: TaskProfile) => void;
    const reported = new Promise<TaskProfile>(resolve => { completed = resolve; });
    const scoped = createSampleHandler({
      ...config, task_profile: {
        ...config.task_profile, cpu_window_ms: 1000, poll_interval_ms: 1000,
        ...(end_reason === "expired" ? { profile_handle_ttl_ms: 50 } : { poll_interval_ms: 10 }),
      },
    }, { platform: "linux", procRoot: directory }, profile => { completed(profile); });
    try {
      const start = StartTaskProfileResponseSchema.parse(await (await scoped(command(START_TASK_PROFILE_PATH, input))).json());
      if (start.status !== "started") throw new Error("Lifecycle case requires an actual collector");
      if (end_reason === "owner_exited") await rm(join(directory, "4242", "stat"));
      if (end_reason === "service_stopped") {
        const closing = scoped.close();
        expect(scoped.close()).toBe(closing);
        await closing;
        expect((await scoped(command(START_TASK_PROFILE_PATH, input))).status).toBe(503);
      }
      const profile = await reported;
      expect(profile.end_reason).toBe(end_reason);
      expect(profile.outcome).toBe("cancelled");
      if (end_reason !== "service_stopped") {
        const stop = StopTaskProfileResponseSchema.parse(await (await scoped(command(STOP_TASK_PROFILE_PATH, {
          handle: start.handle, outcome: "success",
        }))).json());
        if (stop.status !== "stopped") throw new Error("Automatically closed profile was not retained");
        expect(stop.profile).toEqual(profile);
      }
    } finally {
      await scoped.close();
      const recorded = JSON.parse(await fixture("host-probes/process-inputs.json"));
      await Bun.write(join(directory, "4242", "stat"), recorded.stat);
    }
  }
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
  const cacheEnabled = {
    ...config.cache_probe, counters: { ...config.cache_probe.counters, enabled: true },
    latency: { ...config.cache_probe.latency, enabled: true },
  };
  expect((await (await startCacheCounters(cacheEnabled, { ...owned, start_ticks: "1" }, config.max_proc_bytes, context)).close()).reason)
    .toBe("pid_reused");
  expect((await (await startCacheCounters(cacheEnabled, owned, config.max_proc_bytes, context)).close()).reason)
    .toBe("target_not_owned");
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
  await rm(join(directory, "vmstat"));
  await mkdir(join(directory, "vmstat"));
  let processOnly: TaskProfile | undefined;
  await profileTask({
    config: { ...config, task_profile: { ...config.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: false } },
    context, report: profile => { processOnly = profile; },
  }, identity, () => {
    copyFileSync(fileURLToPath(new URL("runtime/2026-08-30-probe-proc-stat-at-end.txt", fixtureRoot)), join(directory, "stat"));
    return "Actual CPU and PID RAM without machine reads";
  });
  expect(processOnly?.cpu.value?.user).toBeCloseTo(53 / 7991 * 100, 10);
  expect(processOnly?.processes.worker.closing.memory_kb.rss).toBe(600);
  expect(processOnly?.processes.worker.sampled_rss_max_kb).toBe(600);
  expect(processOnly?.machine_available_min_kb).toBeNull();
  expect(processOnly?.machine_major_faults_delta).toBeNull();
  expect(processOnly?.samples.at(-1)?.unavailable["memory_kb.total"]).toBe("configured_off");
  expect(processOnly?.samples.at(-1)?.unavailable.vmstat_major_faults).toBe("configured_off");
  await rm(join(directory, String(process.pid), "status"));
  await mkdir(join(directory, String(process.pid), "status"));
  const cpuInput = CollectorInputSchema.parse({
    identity, config: { ...config.task_profile, enabled: true, memory_enabled: false },
    max_proc_bytes: config.max_proc_bytes, worker_pid: process.pid, target: null, server: null,
    clock_ticks_per_second: parseClockTicks(processInput.clock_ticks), expires_after_ms: null, context,
  });
  const cpuCollector = new TaskCollector(cpuInput);
  await Bun.write(join(directory, String(process.pid), "stat"),
    processInput.cpu_intervals[0].closing_stat.replace("4242 ", `${process.pid} `));
  const independent = cpuCollector.close("success");
  expect(independent.processes.worker.cpu.value?.cpu_time_ms).toBe(3000);
  expect(independent.processes.worker.cpu.value?.percent_one_core).toBeCloseTo(
    100 * 3000 / independent.processes.worker.cpu_interval_ms, 8,
  );
  expect(independent.processes.worker.closing.unavailable["memory_kb.rss"]).toBe("configured_off");
  expect(independent.samples.at(-1)?.unavailable["memory_kb.total"]).toBe("configured_off");
  await rm(join(directory, String(process.pid), "status"), { recursive: true });
  await rm(join(directory, "meminfo"), { recursive: true });
  await Bun.write(join(directory, "meminfo"), await fixture("host-probes/meminfo.txt"));
  const withoutStatus = new TaskCollector(CollectorInputSchema.parse({
    ...cpuInput, config: { ...cpuInput.config, memory_enabled: true },
  }));
  const missingStatus = withoutStatus.close("success");
  expect(missingStatus.processes.worker.cpu.value?.cpu_time_ms).toBe(0);
  expect(missingStatus.processes.worker.closing.unavailable["memory_kb.rss"]).toBe("missing_file");
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
  const target = { pid: 4242, start_ticks: "12345" };
  const counters = await startCacheCounters(config.cache_probe, target, config.max_proc_bytes, context);
  expect(counters.initial?.status).toBe("disabled");
  expect((await counters.close()).measurement_obtained).toBe(false);
  expect((await measureWorkingSetLatency(config.cache_probe, config.max_proc_bytes, context)).status).toBe("disabled");
  expect((await (await startCacheCounters(cacheEnabled, target, config.max_proc_bytes, { platform: "unsupported" })).close()).reason)
    .toBe("unsupported_platform");
  expect((await measureWorkingSetLatency(cacheEnabled, config.max_proc_bytes, { platform: "unsupported" })).reason)
    .toBe("unsupported_platform");
  const controller = new CacheProbeController(cacheEnabled, config.max_proc_bytes, { platform: "unsupported" });
  const pending = controller.startCounters(target);
  expect((await controller.measureLatency()).reason).toBe("concurrency_limit");
  expect((await (await pending).settled).reason).toBe("unsupported_platform");
  await controller.shutdown();
  expect((await (await controller.startCounters(target)).close()).reason).toBe("cancelled");
  expect((await controller.measureLatency()).reason).toBe("cancelled");
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
  expect(config.cache_probe.counters.enabled).toBe(false);
  expect(config.cache_probe.latency.enabled).toBe(false);
  for (const latency of [
    { ...config.cache_probe.latency, stride_bytes: 7 },
    { ...config.cache_probe.latency, working_set_bytes: [4096, 4096] },
    { ...config.cache_probe.latency, working_set_bytes: [4096, 2147483648] },
    { ...config.cache_probe.latency, timeout_ms: 1 },
  ]) expect(ProbeConfigSchema.safeParse({ ...config, cache_probe: { ...config.cache_probe, latency } }).success).toBe(false);
  expect(ProbeConfigSchema.safeParse({
    ...config, cache_probe: { ...config.cache_probe, counters: { ...config.cache_probe.counters, events: ["cache-misses"] } },
  }).success).toBe(false);
  expect(config.task_profile.machine_memory_enabled).toBe(false);
  expect(config.task_profile.poll_interval_ms).toBe(1000);
  for (const [field, value] of [
    ["memory_enabled", "true"], ["machine_memory_enabled", "true"],
    ["cpu_window_ms", 0], ["poll_interval_ms", 0], ["max_retained_samples", 1], ["lifecycle_timeout_ms", 0],
    ["max_profile_handles", 0], ["profile_handle_ttl_ms", 0], ["profile_handle_ttl_ms", 2 ** 31],
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
  expect(ProbeConfigSchema.safeParse({ ...config, listen_host: "0.0.0.0" }).success).toBe(false);
  expect(ProbeConfigSchema.safeParse({ ...config, max_request_body_bytes: 0 }).success).toBe(false);
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
