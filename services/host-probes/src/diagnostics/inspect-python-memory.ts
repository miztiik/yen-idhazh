/** How much resident memory belongs to the Python processes visible to this runner? */
import { opendirSync } from "node:fs";
import { readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";
import { readProcessMemory } from "../task-profile/process-memory";
import { readProcessIdentity } from "../task-profile/process-stat";
import { PythonProcessSampleSchema, SHARD_MEMORY_VERSION } from "./shard-memory-schema";
import type { PythonProcessSample } from "./shard-memory-schema";

export function inspectPythonMemory(
  ts: string, context: ProbeContext, maxBytes: number, maxEntries: number, scratch: Buffer,
): PythonProcessSample[] | null {
  if ((context.platform ?? process.platform) !== "linux") return null;
  let directory: ReturnType<typeof opendirSync>;
  try { directory = opendirSync(context.procRoot ?? "/proc"); }
  catch (error) {
    const code = error instanceof Error && "code" in error ? error.code : undefined;
    if (code === "ENOENT" || code === "ENOTDIR" || code === "EACCES" || code === "EPERM") return null;
    throw error;
  }
  const rows: PythonProcessSample[] = [];
  try {
    for (let seen = 0;; seen++) {
      const entry = directory.readSync();
      if (entry === null) return rows;
      if (seen >= maxEntries) return null; // No partial process count.
      if (!/^[1-9]\d*$/.test(entry.name)) continue;
      const pid = Number(entry.name);
      if (!Number.isSafeInteger(pid)) continue;
      const pin = readProcessIdentity(pid, maxBytes, context, scratch);
      if (pin.value === null) continue;
      const comm = readProcFile(`${pid}/comm`, maxBytes, context, scratch).value?.trim();
      if (comm === undefined || !comm.startsWith("python")) continue;
      const { rss, hwm_lifetime } = readProcessMemory(pin.value, maxBytes, context, scratch).memory_kb;
      if (rss === null) continue;
      rows.push(PythonProcessSampleSchema.parse({
        version: SHARD_MEMORY_VERSION, ts, pid, comm, vmrss_kb: rss, vmhwm_kb: hwm_lifetime,
      }));
    }
  } finally { directory.closeSync(); }
}
