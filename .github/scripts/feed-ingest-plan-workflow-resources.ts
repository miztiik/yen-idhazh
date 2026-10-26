/** Which real host and optional whole-planner process observations were collected? */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "../../packages/common-contracts/node_modules/zod";
import { HostFingerprintRowSchema } from "../../packages/common-contracts/src/index";
import { collectFingerprint } from "../../services/host-fingerprints/src/collect-fingerprint";
import { loadConfig as loadFingerprintConfig, SelectedSettingsSchema } from "../../services/host-fingerprints/src/config";
import { loadConfig as loadProbeConfig, ProbeConfigSchema } from "../../services/host-probes/src/config";
import type { ProbeConfig } from "../../services/host-probes/src/config";
import { TaskProfileSchema } from "../../services/host-probes/src/task-profile/profile-schema";
import type { TaskIdentity, TaskOutcome } from "../../services/host-probes/src/task-profile/profile-schema";
import { startTaskProfile } from "../../services/host-probes/src/task-profile/task-profiler";
import type { TaskProfileSession } from "../../services/host-probes/src/task-profile/task-profiler";
import { writeJsonLine } from "../../services/feed-ingest-plan/src/logging/structured-logger";
import { describePlanError } from "../../services/feed-ingest-plan/src/api/plan-request";

const UnrecordedSchema = z.strictObject({
  status: z.enum(["disabled", "unavailable", "failed"]), reason: z.string().min(1),
});
export const WorkflowSettingsSchema = SelectedSettingsSchema.extend({
  observability: SelectedSettingsSchema.shape.observability.extend({
    memory_profiling_enabled: z.boolean(), host_fingerprint_placement_enabled: z.boolean(),
  }),
});
export const WorkflowResourcesSchema = z.strictObject({
  profile_requested: z.boolean(),
  host: z.discriminatedUnion("status", [
    z.strictObject({ status: z.literal("recorded"), row: HostFingerprintRowSchema, unavailable: z.record(z.string(), z.string()) }),
    UnrecordedSchema,
  ]),
  profile: z.discriminatedUnion("status", [
    z.strictObject({ status: z.literal("recorded"), value: TaskProfileSchema }),
    UnrecordedSchema,
  ]),
});
export type WorkflowResources = z.infer<typeof WorkflowResourcesSchema>;

export function configureWorkflowProfiling(config: ProbeConfig, requested: boolean,
  settings: { host_telemetry_enabled: boolean; memory_profiling_enabled: boolean }): ProbeConfig {
  const enabled = requested && settings.host_telemetry_enabled;
  const memory = enabled && settings.memory_profiling_enabled;
  return ProbeConfigSchema.parse({ ...config, task_profile: {
    ...config.task_profile, enabled, memory_enabled: memory, machine_memory_enabled: memory,
  } });
}

export async function observeWorkflowResources(input: {
  root: string; directory: string; profileRequested: boolean; identity: TaskIdentity;
  gitSha: string; attempt: number;
}) {
  const settings = WorkflowSettingsSchema.parse(await Bun.file(join(input.root, "config", "idhazh.json")).json());
  const observation = settings.observability;
  const evidence: WorkflowResources = {
    profile_requested: input.profileRequested,
    host: { status: "unavailable", reason: "Host collection has not finished" },
    profile: { status: "disabled", reason: !input.profileRequested ? "profile_machine_memory=false"
      : !observation.host_telemetry_enabled ? "observability.host_telemetry_enabled=false" : "Profile has not started" },
  };
  const save = () => writeFile(join(input.directory, "resources.json"), JSON.stringify(WorkflowResourcesSchema.parse(evidence)));
  const fail = (instrument: "host" | "profile", error: unknown) => {
    const failure = describePlanError(error, input.root);
    const reason = failure.issues.map(issue => issue.message).join("; ")
      .replaceAll(input.directory.replaceAll("\\", "/"), "feed-ingest-plan");
    evidence[instrument] = { status: "failed", reason: `Collection failed (${failure.code}): ${reason}` };
    writeJsonLine({ event: "planner_resource_failed", instrument, code: failure.code, reason });
  };
  if (!observation.host_telemetry_enabled || !observation.host_fingerprint) {
    evidence.host = { status: "disabled", reason: !observation.host_telemetry_enabled
      ? "observability.host_telemetry_enabled=false" : "observability.host_fingerprint=false" };
  } else {
    try {
      const config = await loadFingerprintConfig(join(input.root, "config", "host-fingerprints.json"));
      const result = await collectFingerprint({
        date: input.identity.run_id.slice(0, 10),
        writer: { run_id: input.identity.run_id, attempt: input.attempt, job: null,
          pipeline_name: "feed-ingest-plan", task_name: "isolated-plan", shard: 0,
          producer: "telemetry.silicon", git_sha: input.gitSha },
      }, { ...config, metadata_url: observation.host_fingerprint_placement_enabled ? config.metadata_url : null },
      { ...settings, observability: { ...observation, host_fingerprint_bandwidth_jobs: [] } });
      evidence.host = { status: "recorded", ...result };
    } catch (error) { fail("host", error); }
  }
  let profile: TaskProfileSession | null = null;
  if (input.profileRequested && observation.host_telemetry_enabled) {
    evidence.profile = { status: "unavailable", reason: "The whole-planner process profile has not closed" };
    try {
      const config = configureWorkflowProfiling(await loadProbeConfig(join(input.root, "config", "host-probes.json")),
        input.profileRequested, observation);
      profile = await startTaskProfile({
        config, report: async value => { evidence.profile = { status: "recorded", value }; await save(); },
      }, input.identity);
    } catch (error) { fail("profile", error); }
  }
  await save();
  return async (outcome: TaskOutcome) => {
    try { await profile?.close(outcome); }
    catch (error) { fail("profile", error); }
    await save();
  };
}
