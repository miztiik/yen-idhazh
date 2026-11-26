import { expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadConfig } from "../src/config";
import { inspectPythonMemory } from "../src/diagnostics/inspect-python-memory";
import { finishShardMemory, recordShardMemory } from "../src/diagnostics/shard-memory";
import { runShardMemory } from "../src/diagnostics/shard-memory-cli";
import { PythonProcessSampleSchema, ShardSampleSchema } from "../src/diagnostics/shard-memory-schema";
import { readProcessIdentity } from "../src/task-profile/process-stat";

test("the private shard receipt seals the named artifacts with counts and one selected group's readings", async () => {
  const root = await mkdtemp(join(tmpdir(), "idhazh-shard-memory-"));
  const config = await loadConfig();
  config.task_profile.poll_interval_ms = 10;
  config.task_profile.profile_handle_ttl_ms = 5000;
  config.shard_memory.poll_interval_ms = 60_000;
  const procRoot = join(root, "proc"), cgroupRoot = join(root, "cgroup");
  const context = { platform: "linux", procRoot };
  const pin = { pid: 7, start_ticks: "12" };
  try {
    for (const name of ["proc/7", "proc/8", "proc/9", "proc/self", "cgroup/test.slice", "backend/var"]) {
      await mkdir(join(root, name), { recursive: true });
    }
    const put = (name: string, value: string) => Bun.write(join(root, name), value);
    await Promise.all([
      put("proc/self/cgroup", "0::/test.slice\n"),
      put("cgroup/memory.current", "999\n"),
      put("cgroup/test.slice/memory.current", "123400\n"),
      put("cgroup/test.slice/memory.peak", "234500\n"),
      put("proc/meminfo", "MemTotal: 16000 kB\nMemAvailable: 6000 kB\nCommitted_AS: 9500 kB\n"),
      ...[7, 8, 9].map(pid => put(`proc/${pid}/stat`, `${pid} (recorded) S 1 1 1 0 -1 0 0 0 0 0 100 200 0 0 20 0 1 0 12\n`)),
      put("proc/7/comm", "llama-server\n"),
      put("proc/7/status", "VmRSS: 4096 kB\nVmHWM: 8192 kB\n"),
      put("proc/8/comm", "python3\n"),
      put("proc/8/status", "VmRSS: 64 kB\nVmHWM: 96 kB\n"),
      put("proc/9/comm", "python\n"),
      put("proc/9/status", "VmRSS: 32 kB\n"),
    ]);
    const destination = { root, context, cgroupRoot };
    const recording = recordShardMemory(config, destination, pin);
    try {
      const sealed = await finishShardMemory(config, destination);
      if (sealed === null) throw new Error("Expected the owned sampler's closing receipt");
      expect(sealed).toMatchObject({
        status: "closed", samples: 1, llama_peak_hwm_kb: 8192, python_peak_hwm_kb: 128, combined_peak_rss_kb: 4192,
      });
      expect(await recording).toEqual(sealed);
      const aggregate = ShardSampleSchema.parse(await Bun.file(join(root, "rss-samples.jsonl")).json());
      expect(aggregate).toMatchObject({
        llama_vmrss_kb: 4096, llama_vmhwm_kb: 8192, python_procs: 2, python_vmrss_kb: 96, python_vmhwm_kb: 128,
        mem_total_kb: 16000, mem_available_kb: 6000, committed_as_kb: 9500, cgroup_current_bytes: 123400,
      });
      expect(inspectPythonMemory(aggregate.ts, context, config.max_proc_bytes, 1,
        Buffer.alloc(config.max_proc_bytes + 1))).toBeNull();
      const processes = (await Bun.file(join(root, "python-procs.jsonl")).text()).trim().split("\n")
        .map(row => PythonProcessSampleSchema.parse(JSON.parse(row))).sort((a, b) => a.pid - b.pid);
      expect(processes).toEqual([
        { version: aggregate.version, ts: aggregate.ts, pid: 8, comm: "python3", vmrss_kb: 64, vmhwm_kb: 96 },
        { version: aggregate.version, ts: aggregate.ts, pid: 9, comm: "python", vmrss_kb: 32, vmhwm_kb: null },
      ]);
      expect(await Bun.file(join(root, "memory-peak.txt")).text()).toBe("cgroup_memory_peak_bytes=234500\n");
    } finally { await recording; }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("the native command does not create shard artifacts when memory or telemetry is off", async () => {
  const root = await mkdtemp(join(tmpdir(), "idhazh-shard-memory-off-"));
  const config = await loadConfig();
  try {
    for (const [mode, memory] of [["typescript", "off"], ["off", "on"]]) {
      const environment = { IDHAZH_HOST_TELEMETRY_MODE: mode, MEMORY_PROFILING: memory };
      await runShardMemory("sample", config, root, environment);
      await runShardMemory("finish", config, root, environment);
      for (const name of ["rss-samples.jsonl", "python-procs.jsonl", "memory-peak.txt"]) {
        expect(await Bun.file(join(root, name)).exists()).toBe(false);
      }
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test.skipIf(process.platform !== "linux")("live Linux shard records its pinned process and finishes named evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "idhazh-shard-memory-live-"));
  const config = await loadConfig();
  try {
    await mkdir(join(root, "backend", "var"), { recursive: true });
    const observed = readProcessIdentity(process.pid, config.max_proc_bytes, {});
    if (observed.value === null) throw new Error(observed.reason);
    const { pid, start_ticks } = observed.value;
    config.task_profile.poll_interval_ms = 10;
    config.task_profile.profile_handle_ttl_ms = 5_000;
    const recording = recordShardMemory(config, { root }, { pid, start_ticks });
    try {
      expect(await finishShardMemory(config, { root })).toMatchObject({ status: "closed", samples: 1 });
      const sample = ShardSampleSchema.parse(await Bun.file(join(root, "rss-samples.jsonl")).json());
      expect(sample.llama_vmrss_kb).toBeGreaterThan(0);
      expect(sample.committed_as_kb).toBeGreaterThan(0);
      expect(await Bun.file(join(root, "memory-peak.txt")).text()).toMatch(/^cgroup_memory_peak_bytes=(\d+|unavailable)\n$/);
    } finally { await recording; }
  } finally { await rm(root, { recursive: true, force: true }); }
});
