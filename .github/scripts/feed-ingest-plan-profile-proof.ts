/** Prove live RAM HTTP readings and the existing optional copy probe outside task CPU windows. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { arch, release } from "node:os";
import { randomUUID } from "node:crypto";
import { z } from "../../services/host-probes/node_modules/zod";
import { HostFingerprintRowSchema } from "../../packages/common-contracts/src/index";
import { loadConfig as loadProbeConfig } from "../../services/host-probes/src/config";
import { SAMPLE_PATH, serveSamples } from "../../services/host-probes/src/api/server";
import { HostSampleSchema } from "../../services/host-probes/src/probe/sample-host";
import { collectFingerprint } from "../../services/host-fingerprints/src/collect-fingerprint";
import { loadConfig, loadSettings, SelectedSettingsSchema } from "../../services/host-fingerprints/src/config";
import { probeBufferMib } from "../../services/host-fingerprints/src/inspect/copy-bandwidth";

const fields = HostFingerprintRowSchema.shape;
export const CopyResultSchema = z.object({
  memcpy_probe_mib: fields.memcpy_probe_mib, memcpy_gib_s: fields.memcpy_gib_s,
  l3_cache_bytes: fields.l3_cache_bytes, cpu_model: fields.cpu_model,
  cpu_logical_processors: fields.cpu_logical_processors, cpu_allowed_processors: fields.cpu_allowed_processors,
  cpu_quota_state: fields.cpu_quota_state, cpu_quota_cores: fields.cpu_quota_cores, fingerprint: fields.fingerprint,
}).strip();
const ResourceProofSchema = z.strictObject({
  scope: z.literal("live_linux_ram_http_and_separate_copy"),
  status: z.enum(["running", "complete", "failed"]),
  stage: z.enum(["start", "ram_http", "copy_off", "copy_on", "complete"]),
  git_sha: z.string().regex(/^[a-f0-9]{40}$/), run_id: z.string().min(1), correlation_id: z.uuid(),
  host: z.strictObject({ platform: z.literal("linux"), arch: z.string(), release: z.string(), bun: z.string() }),
  sample: HostSampleSchema.nullable(),
  copy: z.strictObject({
    task_name: z.string().min(1),
    floor_mib: z.int().nonnegative(), cache_multiple: z.int().positive(), repeats: z.int().positive(),
    buffers: z.literal(2), method: z.literal("median_read_plus_write"),
    off: CopyResultSchema.nullable(), on: CopyResultSchema.nullable(),
    off_reason: z.string().nullable(), on_reason: z.string().nullable(),
  }).nullable(),
  error: z.string().nullable(),
});

export async function verifyLiveHostProfiling(
  identity: { git_sha: string; run_id: string; correlation_id: string; attempt: number }, artifactRoot: string,
) {
  if (process.platform !== "linux") throw new Error("Live resource proof requires Linux; fixture results do not certify it");
  const proof: z.infer<typeof ResourceProofSchema> = {
    scope: "live_linux_ram_http_and_separate_copy", status: "running", stage: "start",
    git_sha: identity.git_sha, run_id: identity.run_id, correlation_id: identity.correlation_id,
    host: { platform: "linux", arch: arch(), release: release(), bun: Bun.version },
    sample: null, copy: null, error: null,
  };
  const persist = () => writeFile(join(artifactRoot, "resource-proof.json"), JSON.stringify(ResourceProofSchema.parse(proof)));
  await persist();
  let server: ReturnType<typeof serveSamples> | undefined;
  try {
    proof.stage = "ram_http";
    await persist();
    server = serveSamples(await loadProbeConfig());
    const response = await fetch(new URL(SAMPLE_PATH, server.url), { timeout: false });
    if (response.status !== 200 || response.headers.get("cache-control") !== "no-store") {
      throw new Error("RAM sample HTTP endpoint did not return an uncached sample");
    }
    proof.sample = HostSampleSchema.parse(await response.json());
    const memory = proof.sample.memory_kb;
    if (proof.sample.cpu === null || memory.total === null || memory.total <= 0
      || memory.free === null || memory.available === null
      || memory.free > memory.total || memory.available > memory.total) {
      throw new Error("Actual Linux CPU or total/free/available RAM readings are unavailable");
    }
    await server.stop(true);
    server = undefined;
    const config = await loadConfig();
    const settings = await loadSettings();
    if (!settings.observability.host_telemetry_enabled || !settings.observability.host_fingerprint) {
      throw new Error("Host instrument is configured off; live resource proof is unavailable");
    }
    // Only this isolated invocation selects copy work. No shared setting or host row is written.
    const task_name = "isolated-copy-proof";
    const capture = { date: new Date().toISOString().slice(0, 10), writer: {
      run_id: identity.run_id, attempt: identity.attempt, job: null,
      pipeline_name: "feed-ingest-plan", task_name, shard: 0, producer: "telemetry.silicon", git_sha: identity.git_sha,
    } };
    proof.copy = {
      task_name, floor_mib: settings.observability.host_fingerprint_bandwidth_floor_mib,
      cache_multiple: settings.observability.host_fingerprint_bandwidth_cache_multiple,
      repeats: config.copy_repeats, buffers: 2, method: "median_read_plus_write",
      off: null, on: null, off_reason: null, on_reason: null,
    };
    for (const enabled of [false, true]) {
      proof.stage = enabled ? "copy_on" : "copy_off";
      await persist();
      const selected = SelectedSettingsSchema.parse({ ...settings, observability: {
        ...settings.observability, host_fingerprint_bandwidth_jobs: enabled ? [task_name] : [],
      } });
      const result = await collectFingerprint(capture, config, selected);
      const row = CopyResultSchema.parse(result.row);
      if (enabled) {
        proof.copy.on = row;
        proof.copy.on_reason = result.unavailable.memcpy_gib_s ?? null;
        const expected = probeBufferMib(proof.copy.floor_mib, row.l3_cache_bytes, proof.copy.cache_multiple);
        if (row.memcpy_probe_mib !== expected || expected <= 0 || row.memcpy_gib_s === null || row.memcpy_gib_s <= 0) {
          throw new Error("Opt-in copy probe did not measure actual derived-buffer transfers");
        }
      } else {
        proof.copy.off = row;
        proof.copy.off_reason = result.unavailable.memcpy_gib_s ?? null;
        if (row.memcpy_probe_mib !== 0 || row.memcpy_gib_s !== null || proof.copy.off_reason !== "configured_off") {
          throw new Error("Unselected copy task did not remain off");
        }
      }
    }
    proof.stage = "complete";
    proof.status = "complete";
  } catch {
    proof.status = "failed";
    proof.error = `Live resource proof failed at ${proof.stage}; unavailable measurements are not success`;
    throw new Error(proof.error);
  } finally {
    try { if (server) await server.stop(true); }
    finally { await persist(); }
  }
  return ResourceProofSchema.parse(proof);
}

if (import.meta.main) {
  const { GITHUB_SHA, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = process.env;
  if (!GITHUB_SHA || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) {
    throw new Error("Hosted resource proof requires the revision and run identity");
  }
  // The CI artifact belongs to the existing test-report tree, never the published tree.
  const root = join("test-results", "host-probes");
  await mkdir(root, { recursive: true });
  const proof = await verifyLiveHostProfiling({
    git_sha: GITHUB_SHA, run_id: `${new Date().toISOString().slice(0, 10)}-${GITHUB_RUN_ID}`,
    correlation_id: randomUUID(), attempt: Number(GITHUB_RUN_ATTEMPT),
  }, root);
  console.log(JSON.stringify({ event: "live_resource_proof", ...proof }));
}
