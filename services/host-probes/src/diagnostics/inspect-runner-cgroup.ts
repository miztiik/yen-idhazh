/** Which current and peak memory counters belong to the runner's selected cgroup? */
import { join } from "node:path";
import { readLinuxFile, readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";

type MemoryGroup = { path: string; version: 1 | 2 };

export function selectMemoryGroup(maxBytes: number, context: ProbeContext, cgroupRoot = "/sys/fs/cgroup"): MemoryGroup | null {
  const membership = readProcFile("self/cgroup", maxBytes, context).value;
  const lines = membership?.split(/\r?\n/).map(line => /^(\d+):([^:]*):(\/.*)$/.exec(line)) ?? [];
  // In a hybrid hierarchy the memory controller can belong to v1.
  const legacy = lines.find(line => line?.[2]?.split(",").includes("memory"));
  const selected = legacy ?? lines.find(line => line?.[1] === "0" && line[2] === "");
  const relative = selected?.[3];
  if (relative === undefined || /[\u0000-\u001f\\]/.test(relative)
    || relative.split("/").some(part => part === "." || part === "..")) return null;
  const base = legacy === undefined ? cgroupRoot : join(cgroupRoot, "memory");
  return { path: join(base, relative), version: legacy === undefined ? 2 : 1 };
}

export function readGroupMemory(group: MemoryGroup | null, kind: "current" | "peak", maxBytes: number, scratch?: Buffer): number | null {
  if (group === null) return null;
  const file = group.version === 2 ? `memory.${kind}`
    : kind === "current" ? "memory.usage_in_bytes" : "memory.max_usage_in_bytes";
  const text = readLinuxFile(join(group.path, file), maxBytes, scratch).value?.trim();
  if (text === undefined || !/^\d+$/.test(text)) return null;
  const bytes = Number(text);
  return Number.isSafeInteger(bytes) ? bytes : null;
}
