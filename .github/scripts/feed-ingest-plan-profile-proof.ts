/** Prove live RAM HTTP readings and the existing optional copy probe outside task CPU windows. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { arch, release } from "node:os";
import { randomUUID } from "node:crypto";
import { loadConfig as loadProbeConfig } from "../../services/host-probes/src/config";
import { SAMPLE_PATH, serveSamples } from "../../services/host-probes/src/api/server";
import { HostSampleSchema } from "../../services/host-probes/src/probe/sample-host";
import { collectFingerprint } from "../../services/host-fingerprints/src/collect-fingerprint";
import { loadConfig, loadSettings, SelectedSettingsSchema } from "../../services/host-fingerprints/src/config";
import { probeBufferMib } from "../../services/host-fingerprints/src/inspect/copy-bandwidth";
import { CopyResultSchema, ProfileProofIdentitySchema, ResourceProofSchema } from "./feed-ingest-plan-profile-schema";
import type { ResourceProof } from "./feed-ingest-plan-profile-schema";
import { verifyLiveCacheProfiling } from "./feed-ingest-plan-cache-proof";

export async function verifyLiveHostProfiling(
  identity: { git_sha: string; run_id: string; correlation_id: string; attempt: number }, artifactRoot: string,
) {
  if (process.platform !== "linux") throw new Error("Live resource proof requires Linux; fixture results do not certify it");
  const proof: ResourceProof = {
    ...ProfileProofIdentitySchema.parse(identity),
    scope: "live_linux_ram_http_and_separate_copy", status: "running", stage: "start",
    host: { platform: "linux", arch: arch(), release: release(), bun: Bun.version },
    sample: null, copy: null, cache: null, error: null,
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
        proof.copy.on_reason = ResourceProofSchema.shape.copy.unwrap().shape.on_reason.parse(result.unavailable.memcpy_gib_s ?? null);
        const expected = probeBufferMib(proof.copy.floor_mib, row.l3_cache_bytes, proof.copy.cache_multiple);
        if (row.memcpy_probe_mib !== expected || expected <= 0 || row.memcpy_gib_s === null || row.memcpy_gib_s <= 0) {
          throw new Error("Opt-in copy probe did not measure actual derived-buffer transfers");
        }
      } else {
        proof.copy.off = row;
        proof.copy.off_reason = ResourceProofSchema.shape.copy.unwrap().shape.off_reason.parse(result.unavailable.memcpy_gib_s ?? null);
        if (row.memcpy_probe_mib !== 0 || row.memcpy_gib_s !== null || proof.copy.off_reason !== "configured_off") {
          throw new Error("Unselected copy task did not remain off");
        }
      }
    }
    proof.stage = "cache";
    await persist();
    if (!process.env.RUNNER_TEMP) throw new Error("Cache proof requires the declared optional tool installation");
    proof.cache = await verifyLiveCacheProfiling(identity, await loadProbeConfig(), proof.copy.on!,
      await Bun.file(join(process.env.RUNNER_TEMP, "host-cache-tool-install.json")).json(),
      async cache => { proof.cache = cache; await persist(); });
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
