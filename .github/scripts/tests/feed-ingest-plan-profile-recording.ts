/** Build bounded report inputs from real collectors over recorded Linux files and actual copy work. */
import { createHash, randomUUID } from "node:crypto";
import { copyFileSync } from "node:fs";
import { mkdir, mkdtemp } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig } from "../../../services/host-probes/src/config";
import { CollectorInputSchema } from "../../../services/host-probes/src/task-profile/profile-schema";
import { TaskCollector } from "../../../services/host-probes/src/task-profile/task-collector";
import { parseClockTicks } from "../../../services/host-probes/src/task-profile/clock-ticks";
import { sampleHost } from "../../../services/host-probes/src/probe/sample-host";
import { collectFingerprint } from "../../../services/host-fingerprints/src/collect-fingerprint";
import { fixture as hostFixture } from "../../../services/host-fingerprints/test/fixture";
import { configureDocumentProfiling } from "../feed-ingest-plan-http-proof";
import { CopyResultSchema, ResourceProofSchema, StageProfileProofSchema } from "../feed-ingest-plan-profile-schema";
import type { ProfileProofIdentity, ResourceProof, StageProfileProof } from "../feed-ingest-plan-profile-schema";

export async function recordProfileEvidence(
  root: string, identity: ProfileProofIdentity, sourceId: string,
  options: { machineMemoryEnabled: boolean; cpuWindowMs: number; withTicks?: boolean; resourceProof?: ResourceProof },
) {
  const fixtureRoot = new URL("../../../tests/fixtures/", import.meta.url);
  const directory = await mkdtemp(join(root, "profile-recording-"));
  const start = fileURLToPath(new URL("runtime/2026-08-30-probe-proc-stat-at-start.txt", fixtureRoot));
  const end = fileURLToPath(new URL("runtime/2026-08-30-probe-proc-stat-at-end.txt", fixtureRoot));
  for (const name of ["meminfo", "vmstat"]) {
    copyFileSync(fileURLToPath(new URL(`host-probes/${name}.txt`, fixtureRoot)), join(directory, name));
  }
  const processInput = await Bun.file(new URL("host-probes/process-inputs.json", fixtureRoot)).json();
  await mkdir(join(directory, String(process.pid)));
  await Bun.write(join(directory, String(process.pid), "stat"), processInput.stat.replace("4242 ", `${process.pid} `));
  await Bun.write(join(directory, String(process.pid), "status"), processInput.status);
  const config = configureDocumentProfiling(await loadConfig(), options.machineMemoryEnabled);
  config.task_profile.cpu_window_ms = options.cpuWindowMs;
  const documents: StageProfileProof["documents"] = [];
  const digest = (value: string) => createHash("sha256").update(value).digest("hex");
  for (const kind of ["feed", "article"] as const) {
    const article_id = digest(`recorded-${kind}`);
    const fetchId = randomUUID();
    const parseId = randomUUID();
    const requests = {
      fetch: { request_id: fetchId, correlation_id: identity.correlation_id, source_id: sourceId, kind },
      parse: { request_id: parseId, correlation_id: identity.correlation_id, article_id, fetch_request_id: fetchId },
    };
    const profiles = [];
    const calls: StageProfileProof["documents"][number]["calls"] = [];
    for (const operation of ["fetch", "parse"] as const) {
      copyFileSync(start, join(directory, "stat"));
      await Bun.write(join(directory, String(process.pid), "stat"), processInput.stat.replace("4242 ", `${process.pid} `));
      const collector = new TaskCollector(CollectorInputSchema.parse({
        identity: { pipeline_name: "feed-ingest-plan", task_name: operation,
          run_id: identity.run_id, correlation_id: identity.correlation_id, request_id: requests[operation].request_id },
        config: config.task_profile, max_proc_bytes: config.max_proc_bytes,
        worker_pid: process.pid, target: null, clock_ticks_per_second: parseClockTicks(processInput.clock_ticks),
        expires_after_ms: null, server: null, context: { platform: "linux", procRoot: directory },
      }));
      const input = processInput.status.repeat(128);
      for (let repeat = 0; repeat < 512; repeat++) digest(input);
      if (options.withTicks !== false) {
        copyFileSync(end, join(directory, "stat"));
        await Bun.write(join(directory, String(process.pid), "stat"),
          processInput.cpu_intervals[0].closing_stat.replace("4242 ", `${process.pid} `));
      }
      profiles.push(collector.close("success"));
      const original = { stage: operation, endpoint: operation, request: requests[operation], http_status: 200,
        response_sha256: digest(processInput.status), network: { dns: 0, http: 0 } };
      calls.push(original, { ...original, stage: `${operation}_replay_after_restart` });
    }
    for (const [stage, endpoint, request] of [
      ["changed_input_conflict", "fetch", { ...requests.fetch, correlation_id: randomUUID() }],
      ["changed_operation_conflict", "parse", { ...requests.parse, request_id: fetchId }],
      ["changed_config_conflict", "fetch", requests.fetch],
    ] as const) calls.push({ stage, endpoint, request, http_status: 409,
      response_sha256: digest("REQUEST_CONFLICT"), network: { dns: 0, http: 0 } });
    const journal = digest(JSON.stringify(requests));
    documents.push({ kind, status: "complete", git_sha: identity.git_sha,
      source_id: sourceId, article_id, run_id: identity.run_id, correlation_id: identity.correlation_id,
      calls, journal_records_sha256: { before_restart: journal, after_checks: journal },
      profiling: { profiles, actual_work_count: profiles.length, after_checks_count: profiles.length } });
  }
  const stageProof = StageProfileProofSchema.parse({ ...identity,
    scope: "live_configured_feed_and_selected_article", status: "complete", task_profile: config.task_profile, documents });
  if (options.resourceProof !== undefined) return { stageProof, resourceProof: ResourceProofSchema.parse(options.resourceProof) };
  copyFileSync(start, join(directory, "stat"));
  const pending = sampleHost({ ...config, sample_interval_ms: 1 }, { platform: "linux", procRoot: directory });
  copyFileSync(end, join(directory, "stat"));
  const sample = await pending;
  const host = await hostFixture();
  try {
    const off = await collectFingerprint(host.capture, host.config, host.settings, host.inspection);
    host.settings.observability.host_fingerprint_bandwidth_jobs = [host.capture.writer.task_name!];
    host.settings.observability.host_fingerprint_bandwidth_floor_mib = 1;
    host.settings.observability.host_fingerprint_bandwidth_cache_multiple = 1;
    const on = await collectFingerprint(host.capture, host.config, host.settings, host.inspection);
    return {
      stageProof,
      resourceProof: ResourceProofSchema.parse({ ...identity,
        scope: "live_linux_ram_http_and_separate_copy", status: "complete", stage: "complete",
        host: { platform: "linux", arch: "recorded", release: "recorded", bun: Bun.version },
        sample, copy: { task_name: host.capture.writer.task_name,
          floor_mib: host.settings.observability.host_fingerprint_bandwidth_floor_mib,
          cache_multiple: host.settings.observability.host_fingerprint_bandwidth_cache_multiple,
          repeats: host.config.copy_repeats, buffers: 2, method: "median_read_plus_write",
          off: CopyResultSchema.parse(off.row), on: CopyResultSchema.parse(on.row),
          off_reason: off.unavailable.memcpy_gib_s ?? null, on_reason: on.unavailable.memcpy_gib_s ?? null,
        }, error: null }),
    };
  } finally { await host.cleanup(); }
}
