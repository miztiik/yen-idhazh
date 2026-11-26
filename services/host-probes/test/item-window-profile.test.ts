import { afterEach, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRootContext } from "@idhazh/common-contracts";
import {
  createSampleHandler, START_ITEM_WINDOW_PATH, STOP_ITEM_WINDOW_PATH, STOP_TASK_PROFILE_PATH,
} from "../src/api/server";
import { StartItemWindowResponseSchema, StopItemWindowResponseSchema } from "../src/api/task-command-schema";
import { loadConfig } from "../src/config";
import { ItemWindowCollector } from "../src/task-profile/item-window-collector";
import { itemCpuShares, parseItemTicks } from "../src/task-profile/item-window-cpu";
import { CollectorInputSchema, OwnedProcessSchema } from "../src/task-profile/profile-schema";
import { readProcessIdentity } from "../src/task-profile/process-stat";

const tempRoots: string[] = [];
const identity = { pipeline_name: "digest", run_id: "fixture-day", task_name: "work-item" };
const target = { pid: 342, start_ticks: "12" };
const server = { pid: 567, start_ticks: "13" };

function stat(pid: number, start: string, faults: number) {
  return `${pid} (recorded) S 1 1 1 0 -1 0 0 0 ${faults} 0 100 200 0 0 20 0 1 0 ${start}\n`;
}

async function procRoot() {
  const root = await mkdtemp(join(tmpdir(), "idhazh-item-window-"));
  tempRoots.push(root);
  for (const pin of [target, server]) {
    await mkdir(join(root, String(pin.pid)));
    await Bun.write(join(root, String(pin.pid), "stat"), stat(pin.pid, pin.start_ticks, 7));
  }
  return root;
}

async function frame(root: string, cpu: string, available: number, load = "0.5",
  workerRss = 0, serverRss = 0, serverHwm = 0, serverFaults = 7) {
  await Promise.all([
    Bun.write(join(root, "stat"), `cpu ${cpu}\n`),
    Bun.write(join(root, "meminfo"),
      `MemTotal: 16000 kB\nMemAvailable: ${available} kB\nCached: 3000 kB\nSwapFree: 0 kB\nSwapTotal: 1024 kB\n`),
    Bun.write(join(root, "loadavg"), `${load} 0.25 0.20 1/5 567\n`),
    Bun.write(join(root, String(target.pid), "status"),
      `VmRSS: ${workerRss} kB\nRssAnon: ${workerRss / 2} kB\n`),
    Bun.write(join(root, String(server.pid), "status"),
      `VmRSS: ${serverRss} kB\nVmHWM: ${serverHwm} kB\nRssAnon: ${serverRss / 2} kB\n`),
    Bun.write(join(root, String(server.pid), "stat"), stat(server.pid, server.start_ticks, serverFaults)),
  ]);
}

function post(path: string, body: unknown) {
  return new Request(`http://localhost${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

afterEach(async () => {
  for (const root of tempRoots.splice(0)) await rm(root, { recursive: true, force: true });
});

test("the item oracle uses rounded elapsed shares, adjacent polls and only endpoint server gauges", async () => {
  const root = await procRoot();
  const cfg = await loadConfig();
  const context = { platform: "linux", procRoot: root };
  await frame(root, "9007199254741100 20 40 400 10 5 5 40 12 4", 8000, "0.4", 420, 4000, 9000);
  const watch = new ItemWindowCollector(CollectorInputSchema.parse({
    operation: createRootContext(), identity, context, target, server,
    config: { ...cfg.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true },
    max_proc_bytes: cfg.max_proc_bytes, worker_pid: target.pid, clock_ticks_per_second: { value: null, reason: "configured_off" },
    expires_after_ms: null, item_poll_ms: 1000,
  }));
  await frame(root, "9007199254741110 20 40 460 10 5 5 50 20 4", 4000, "0.5", 450, 4500, 10000);
  watch.poll();
  await frame(root, "9007199254741170 20 72 462 10 5 11 50 49 4", 3500, "0.6", 480, 4800, 11000);
  watch.poll();
  await frame(root, "9007199254741170 20 72 1362 10 5 11 50 49 4", 6000, "1.75", 512, 4096, 8000, 12);
  const closed = watch.close("success", "explicit_stop");
  expect(closed.cells).toEqual({
    cpu_busy_pct: 10, cpu_busy_max: 98, cpu_busy_min: 10, cpu_steal_pct: 0.93, load_1m: 1.75,
    llama_rss_bytes: 4096 * 1024, llama_rss_anon_bytes: 2048 * 1024,
    llama_rss_peak_bytes: 9000 * 1024, llama_major_faults: 5,
    python_rss_bytes: 512 * 1024, python_rss_anon_bytes: 256 * 1024,
    os_mem_available_bytes: 6000 * 1024, os_mem_total_bytes: 16000 * 1024, os_mem_cached_bytes: 3000 * 1024,
    os_swap_free_bytes: 0, os_swap_total_bytes: 1024 * 1024, os_mem_available_min_bytes: 3500 * 1024,
  });
  expect(watch.close("error", "explicit_stop")).toBe(closed);
});

test("item CPU math keeps missing steal, rejects guest resets and matches Python at rounding edges", () => {
  const shares = (start: string, end: string) => itemCpuShares(parseItemTicks(start), parseItemTicks(end));
  expect(shares("cpu 0 0 0 0", "cpu 1 0 0 799 0 0 0 2")).toEqual({ busy: 0.12, steal: null });
  expect(shares("cpu 0 0 0 0\n", "cpu 3 0 0 797")).toEqual({ busy: 0.38, steal: null });
  expect(shares("cpu 0 0 0 0\n", "cpu 107 0 0 3893")).toEqual({ busy: 2.67, steal: null });
  expect(shares("cpu 0 0 0 0 0 0 0 0 10 0", "cpu 5 0 0 5 0 0 0 0 9 0")).toBeNull();
  expect(shares("cpu 5 0 0 5", "cpu 4 0 0 7")).toBeNull();
  expect(shares("cpu 5 0 0 5", "cpu 5 0 0 5")).toBeNull();
});

test("zero polls close both endpoints without memory reads, and mode handles cannot cross", async () => {
  const root = await procRoot();
  const config = await loadConfig();
  config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true };
  const context = { platform: "linux", procRoot: root };
  await Bun.write(join(root, "stat"), "cpu 10 0 0 20\n");
  await mkdir(join(root, "meminfo"));
  await mkdir(join(root, String(target.pid), "status"));
  const input = { identity, target, server, waiting_heartbeat_seconds: 0, memory_profiling_enabled: false };
  const handler = createSampleHandler(config, context, () => { throw new Error("Item cells are not generic reports"); },
    { writeEvent: () => {} });
  try {
    expect((await handler(post(START_ITEM_WINDOW_PATH, { ...input, memory_profiling_enabled: true }))).status).toBe(400);
    expect((await handler(post(START_ITEM_WINDOW_PATH, { ...input, target: { ...target, start_ticks: "11" } }))).status).toBe(409);
    const body = StartItemWindowResponseSchema.parse(await (await handler(post(START_ITEM_WINDOW_PATH, input))).json());
    if (body.status !== "started") throw new Error("Expected an active item handle");
    const close = { handle: body.handle, outcome: "success" };
    expect((await handler(post(STOP_TASK_PROFILE_PATH, close))).status).toBe(404);
    // A mistakenly scheduled zero-delay poll would try to read this directory.
    await rm(join(root, "stat"));
    await mkdir(join(root, "stat"));
    await Bun.sleep(25);
    await rm(join(root, "stat"), { recursive: true });
    await Bun.write(join(root, "stat"), "cpu 30 0 0 100\n");
    await Bun.write(join(root, "loadavg"), "2.50 1.50 1.00 1/5 567\n");
    const result = StopItemWindowResponseSchema.parse(await (await handler(post(STOP_ITEM_WINDOW_PATH, close))).json());
    if (result.status !== "stopped") throw new Error("Expected item cells");
    expect(result.profile.cells).toMatchObject({
      cpu_busy_pct: 20, cpu_busy_max: 20, cpu_busy_min: 20, cpu_steal_pct: null, load_1m: 2.5,
    });
    expect(Object.entries(result.profile.cells).filter(([key]) => /^(llama|python|os)_/.test(key))
      .every(([, value]) => value === null)).toBe(true);
    expect(await (await handler(post(STOP_ITEM_WINDOW_PATH, { ...close, outcome: "error" }))).json()).toEqual(result);
  } finally { await handler.close(); }
  const disabled = createSampleHandler(await loadConfig(), context, undefined, { writeEvent: () => {} });
  try {
    expect(await (await disabled(post(START_ITEM_WINDOW_PATH, input))).json())
      .toEqual({ status: "disabled", reason: "configured_off" });
  } finally { await disabled.close(); }
});

test("a missing OS reading stays empty and a recycled server cannot supply closing status or faults", async () => {
  const root = await procRoot();
  const config = await loadConfig();
  config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true };
  await Bun.write(join(root, String(server.pid), "status"), "VmHWM: 18 kB\n");
  const handler = createSampleHandler(config, { platform: "linux", procRoot: root }, undefined, { writeEvent: () => {} });
  try {
    const body = StartItemWindowResponseSchema.parse(await (await handler(post(START_ITEM_WINDOW_PATH,
      { identity, target, server, waiting_heartbeat_seconds: 0 }))).json());
    if (body.status !== "started") throw new Error("Expected an active item handle");
    await Bun.write(join(root, String(server.pid), "stat"), stat(server.pid, "99", 10_000));
    await Bun.write(join(root, String(server.pid), "status"), "VmRSS: 72 kB\nVmHWM: 90 kB\nRssAnon: 36 kB\n");
    const result = StopItemWindowResponseSchema.parse(await (await handler(post(STOP_ITEM_WINDOW_PATH,
      { handle: body.handle, outcome: "error" }))).json());
    if (result.status !== "stopped") throw new Error("Expected item cells");
    expect(result.profile.outcome).toBe("error");
    expect(result.profile.cells).toMatchObject({
      cpu_busy_pct: null, cpu_busy_max: null, load_1m: null, os_mem_available_min_bytes: null,
      llama_rss_bytes: null, llama_rss_anon_bytes: null, llama_rss_peak_bytes: 18 * 1024, llama_major_faults: null,
    });
  } finally { await handler.close(); }
});

test.skipIf(process.platform !== "linux")("live Linux pins two real processes and observes a worker exit before close", async () => {
  const config = await loadConfig();
  config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true };
  const spawn = () => Bun.spawn([process.execPath, "-e", "await Bun.stdin.text(); process.exit(7)"],
    { stdin: "pipe", stdout: "ignore", stderr: "ignore" });
  const worker = spawn(), model = spawn();
  const handler = createSampleHandler(config, {}, undefined, { writeEvent: () => {} });
  try {
    const pin = (pid: number) => {
      const observed = readProcessIdentity(pid, config.max_proc_bytes, {});
      if (observed.value === null) throw new Error(observed.reason);
      return OwnedProcessSchema.parse({ pid, start_ticks: observed.value.start_ticks });
    };
    const input = { identity, target: pin(worker.pid), server: pin(model.pid), waiting_heartbeat_seconds: 0 };
    expect((await handler(post(START_ITEM_WINDOW_PATH, {
      ...input, target: { pid: worker.pid, start_ticks: String(BigInt(input.target.start_ticks) + 1n) },
    }))).status).toBe(409);
    const start = async () => {
      const res = await handler(post(START_ITEM_WINDOW_PATH, input));
      expect(res.status).toBe(200);
      const result = StartItemWindowResponseSchema.parse(await res.json());
      if (result.status !== "started") throw new Error("Expected a live pinned process");
      return result.handle;
    };
    const stop = async (handle: string) => {
      const res = await handler(post(STOP_ITEM_WINDOW_PATH, { handle, outcome: "success" }));
      const result = StopItemWindowResponseSchema.parse(await res.json());
      if (result.status !== "stopped") throw new Error("Expected a closed process");
      return result;
    };
    const reading = await stop(await start());
    expect(reading.end_reason).toBe("explicit_stop");
    expect(reading.profile.cells.python_rss_bytes).toBeGreaterThan(0);
    expect(reading.profile.cells.llama_rss_bytes).toBeGreaterThan(0);
    expect(reading.profile.cells.llama_major_faults).toBeGreaterThanOrEqual(0);
    expect(reading.profile.cells.os_mem_available_min_bytes).toBeGreaterThan(0);
    const interrupted = await start();
    worker.stdin.end();
    expect(await worker.exited).toBe(7);
    const unavailable = await stop(interrupted);
    expect(unavailable).toMatchObject({ end_reason: "owner_exited", profile: {
      outcome: "cancelled", cells: { python_rss_bytes: null },
    } });
  } finally {
    if (worker.exitCode === null) worker.kill();
    if (model.exitCode === null) model.kill();
    await Promise.all([worker.exited, model.exited, handler.close()]);
  }
});
