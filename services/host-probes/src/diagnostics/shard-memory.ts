/** How are the shard's private memory samples bounded, finished and reported? */
import { existsSync, mkdirSync, openSync, closeSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { writeAtomically } from "@idhazh/ledger-file-writer";
import type { ProbeConfig } from "../config";
import { parseShardMemory } from "../probe/memory-probe";
import { readLinuxFile, readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";
import { readProcessMemory } from "../task-profile/process-memory";
import { readPinnedProcess, verifyProcessPin } from "../task-profile/process-stat";
import type { OwnedProcess } from "../task-profile/profile-schema";
import { inspectPythonMemory } from "./inspect-python-memory";
import { readGroupMemory, selectMemoryGroup } from "./inspect-runner-cgroup";
import { ShardMemoryReceiptSchema, ShardSampleSchema, SHARD_MEMORY_VERSION } from "./shard-memory-schema";
import type { ShardMemoryReceipt } from "./shard-memory-schema";

function shardFiles(root: string) {
  const control = join(root, "backend", "var", "shard-memory");
  return {
    control, ready: join(control, "ready"), stop: join(control, "stop"), receipt: join(control, "receipt.json"),
    samples: join(root, "rss-samples.jsonl"), processes: join(root, "python-procs.jsonl"), peak: join(root, "memory-peak.txt"),
  };
}

type Destination = { root: string; context?: ProbeContext; cgroupRoot?: string };
const line = (value: unknown) => `${JSON.stringify(value)}\n`;
const encode = (text: string) => new TextEncoder().encode(text);

function maxReading(previous: number | null, sample: number | null): number | null {
  return sample === null ? previous : Math.max(previous ?? sample, sample);
}

export async function recordShardMemory(config: ProbeConfig, destination: Destination, server: OwnedProcess) {
  const { max_proc_bytes: limit, shard_memory: policy, task_profile: lifecycle } = config;
  const context = destination.context ?? {};
  verifyProcessPin(server, limit, context);
  const files = shardFiles(destination.root);
  mkdirSync(files.control); // One sampler per runner; do not adopt stale controls.
  const group = selectMemoryGroup(limit, context, destination.cgroupRoot);
  const scratch = Buffer.alloc(limit + 1);
  const end = performance.now() + lifecycle.profile_handle_ttl_ms;
  const receipt: ShardMemoryReceipt = {
    version: SHARD_MEMORY_VERSION, status: "expired", samples: 0,
    llama_peak_hwm_kb: null, python_peak_hwm_kb: null, combined_peak_rss_kb: null,
  };
  let written = 0;
  const samples = openSync(files.samples, "w", 0o600);
  try {
    const processes = openSync(files.processes, "w", 0o600);
    try {
      while (performance.now() < end) {
        if (existsSync(files.stop)) { receipt.status = "closed"; break; }
        if (readPinnedProcess(server, limit, context, scratch).reason !== null) {
          receipt.status = "server_exited";
          break;
        }
        const ts = new Date().toISOString();
        const memory = readProcessMemory(server, limit, context, scratch).memory_kb;
        const python = inspectPythonMemory(ts, context, limit, policy.max_proc_entries, scratch);
        const sample = ShardSampleSchema.parse({
          version: SHARD_MEMORY_VERSION, ts,
          llama_vmrss_kb: memory.rss, llama_vmhwm_kb: memory.hwm_lifetime,
          python_procs: python?.length ?? null,
          python_vmrss_kb: python?.reduce((sum, row) => sum + row.vmrss_kb, 0) ?? null,
          python_vmhwm_kb: python?.reduce((sum, row) => sum + (row.vmhwm_kb || row.vmrss_kb), 0) ?? null,
          ...parseShardMemory(readProcFile("meminfo", limit, context, scratch).value ?? ""),
          cgroup_current_bytes: readGroupMemory(group, "current", limit, scratch),
        });
        const sampleLine = line(sample);
        const processLines = python?.map(line).join("") ?? "";
        written += Buffer.byteLength(sampleLine) + Buffer.byteLength(processLines);
        if (written > policy.max_artifact_bytes) { receipt.status = "artifact_limit"; break; }
        writeFileSync(samples, sampleLine);
        writeFileSync(processes, processLines);
        if (receipt.samples++ === 0) writeFileSync(files.ready, "", { flag: "wx" });
        receipt.llama_peak_hwm_kb = maxReading(receipt.llama_peak_hwm_kb, sample.llama_vmhwm_kb);
        receipt.python_peak_hwm_kb = maxReading(receipt.python_peak_hwm_kb, sample.python_vmhwm_kb);
        const combined = sample.llama_vmrss_kb === null || sample.python_vmrss_kb === null
          ? null : sample.llama_vmrss_kb + sample.python_vmrss_kb;
        receipt.combined_peak_rss_kb = maxReading(receipt.combined_peak_rss_kb, combined);
        const next = Math.min(end, performance.now() + policy.poll_interval_ms);
        while (!existsSync(files.stop) && performance.now() < next) {
          await Bun.sleep(Math.min(lifecycle.poll_interval_ms, Math.max(0, next - performance.now())));
        }
      }
    } finally { closeSync(processes); }
  } finally { closeSync(samples); }
  await writeAtomically(files.receipt, encode(line(ShardMemoryReceiptSchema.parse(receipt))));
  return receipt;
}

export async function finishShardMemory(config: ProbeConfig, destination: Destination): Promise<ShardMemoryReceipt | null> {
  const files = shardFiles(destination.root);
  const limit = config.max_proc_bytes;
  // The runner group's lifetime peak is independent of the sampler and of any item.
  const group = selectMemoryGroup(limit, destination.context ?? {}, destination.cgroupRoot);
  const peak = readGroupMemory(group, "peak", limit);
  await writeAtomically(files.peak, encode(`cgroup_memory_peak_bytes=${peak ?? "unavailable"}\n`));
  if (!existsSync(files.control)) return null;
  writeFileSync(files.stop, "");
  const deadline = performance.now() + config.task_profile.lifecycle_timeout_ms;
  do {
    const receipt = readLinuxFile(files.receipt, limit);
    if (receipt.value !== null) return ShardMemoryReceiptSchema.parse(JSON.parse(receipt.value));
    if (receipt.reason !== "missing_file") throw new Error("Shard memory receipt is unreadable");
    await Bun.sleep(Math.min(config.task_profile.poll_interval_ms, Math.max(0, deadline - performance.now())));
  } while (performance.now() < deadline);
  throw new Error("Shard memory sampler did not finish in time");
}
