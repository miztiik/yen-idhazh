/** Does an owned native benchmark verify its CPU when its caller has a restricted allowed set? */
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { loadConfig, ProbeConfigSchema } from "../src/config";
import type { ProbeConfig } from "../src/config";
import { readProcFile } from "../src/probe/proc-reader";
import { measureWorkingSetLatency } from "../src/cache-probe/working-set-latency";
import { startBoundedTool } from "../src/cache-probe/bounded-tool";
import { loadConfig as loadFingerprintConfig } from "../../host-fingerprints/src/config";
import { parseCpuIds } from "../../host-fingerprints/src/inspect/cpu-topology";

const cpus = z.array(z.int().nonnegative()).min(1);
const AffinityResultSchema = z.strictObject({
  inherited_allowed_cpus: cpus, measured_cpus: cpus, working_set_bytes: z.array(z.int().positive()).min(2),
});
export const CacheAffinityProofSchema = z.strictObject({
  status: z.enum(["verified", "unavailable"]),
  reason: z.enum(["affinity_unavailable", "insufficient_allowed_cpus"]).nullable(),
  parent_allowed_cpus: cpus.nullable(), restricted_allowed_cpus: cpus.nullable(),
  measured_cpu: z.int().nonnegative().nullable(), discontiguous_tested: z.boolean(),
});

async function readAllowedCpus(config: ProbeConfig) {
  const status = readProcFile(`${process.pid}/status`, config.max_proc_bytes, {});
  const text = status.reason === null ? /^Cpus_allowed_list:\s*(.+)$/m.exec(status.value)?.[1] : undefined;
  return parseCpuIds(text ?? null, (await loadFingerprintConfig()).max_online_processors);
}

export async function verifyCacheAffinity(config: ProbeConfig) {
  const parent = await readAllowedCpus(config);
  const candidates = parent?.filter(cpu => cpu !== parent[0]) ?? [];
  if (parent === null || candidates.length === 0) return CacheAffinityProofSchema.parse({
    status: "unavailable", reason: parent === null ? "affinity_unavailable" : "insufficient_allowed_cpus",
    parent_allowed_cpus: parent, restricted_allowed_cpus: null, measured_cpu: null, discontiguous_tested: false,
  });
  const selected = candidates.length >= 3 ? [candidates[0]!, candidates[2]!]
    : candidates.length === 2 && candidates[1]! - candidates[0]! > 1 ? candidates : [candidates[0]!];
  const tool = startBoundedTool("taskset", [
    "--cpu-list", selected.join(","), process.execPath, fileURLToPath(import.meta.url), "--verify-affinity",
  ], { max_output_bytes: config.cache_probe.max_output_bytes, timeout_ms: config.cache_probe.latency.timeout_ms });
  const output = await tool.finished;
  if (output.reason !== null || output.code !== 0 || output.stderr !== "") {
    throw new Error(`Controlled affinity proof did not run: ${output.reason ?? "tool_failed"}`);
  }
  const result = AffinityResultSchema.parse(JSON.parse(output.stdout));
  if (JSON.stringify(result.inherited_allowed_cpus) !== JSON.stringify(selected)
    || result.measured_cpus.some(cpu => cpu !== selected[0]) || selected[0] === 0
    || result.measured_cpus.length !== result.working_set_bytes.length) {
    throw new Error("Native benchmark did not verify its actual nonzero allowed CPU");
  }
  return CacheAffinityProofSchema.parse({
    status: "verified", reason: null, parent_allowed_cpus: parent, restricted_allowed_cpus: selected,
    measured_cpu: selected[0], discontiguous_tested: selected.length > 1,
  });
}

if (import.meta.main) {
  if (process.argv.slice(2).join() !== "--verify-affinity") throw new Error("Unknown owned affinity-proof command");
  const defaults = await loadConfig();
  const config = ProbeConfigSchema.parse({
    ...defaults, cache_probe: { ...defaults.cache_probe, latency: {
      ...defaults.cache_probe.latency, enabled: true,
      working_set_bytes: defaults.cache_probe.latency.working_set_bytes.slice(0, 2),
    } },
  });
  const inherited = await readAllowedCpus(config);
  const latency = await measureWorkingSetLatency(config.cache_probe, config.max_proc_bytes);
  if (inherited === null || latency.status !== "measured") {
    throw new Error(`Owned affinity benchmark was not measured: ${latency.reason}`);
  }
  console.log(JSON.stringify(AffinityResultSchema.parse({
    inherited_allowed_cpus: inherited, measured_cpus: latency.points.map(point => point.allowed_cpu),
    working_set_bytes: latency.points.map(point => point.working_set_bytes),
  })));
}
