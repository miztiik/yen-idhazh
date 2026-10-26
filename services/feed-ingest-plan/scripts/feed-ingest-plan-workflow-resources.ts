/** Which real host and optional whole-planner process observations were collected? */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { FingerprintRequestSchema, loadConfig as loadFingerprintConfig } from "../../host-fingerprints/src/config";
import { FingerprintWrittenSchema } from "../../host-fingerprints/src/api/fingerprint-response";
import { captureLocalFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";
import { loadConfig as loadProbeConfig, ProbeConfigSchema } from "../../host-probes/src/config";
import type { ProbeConfig } from "../../host-probes/src/config";
import { TaskProfileSchema } from "../../host-probes/src/task-profile/profile-schema";
import type { TaskIdentity, TaskOutcome } from "../../host-probes/src/task-profile/profile-schema";
import { startTaskProfile } from "../../host-probes/src/task-profile/task-profiler";
import type { TaskProfileSession } from "../../host-probes/src/task-profile/task-profiler";
import { writeJsonLine } from "../src/logging/structured-logger";
import { describePlanError } from "../src/api/plan-request";
import { WorkflowSettingsSchema } from "../../host-probes/scripts/feed-ingest-plan-profile-schema";
import { hostWriter, readMetadataRegistrations } from "./feed-ingest-plan-metadata";
import { verifyHostFingerprint } from "./feed-ingest-plan-host-verification";
export { WorkflowSettingsSchema } from "../../host-probes/scripts/feed-ingest-plan-profile-schema";

const UnrecordedSchema = z.strictObject({
  status: z.enum(["disabled", "unavailable", "failed"]), reason: z.string().min(1),
});
export const WorkflowResourcesSchema = z.strictObject({
  profile_requested: z.boolean(),
  host_request: FingerprintRequestSchema,
  host: z.discriminatedUnion("status", [
    FingerprintWrittenSchema.omit({ status: true }).extend({ status: z.literal("recorded") }),
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
  root: string; directory: string; stateRoot: string; profileRequested: boolean; identity: TaskIdentity;
  gitSha: string; attempt: number; registryPath?: string;
}) {
  const settings = WorkflowSettingsSchema.parse(await Bun.file(join(input.root, "config", "idhazh.json")).json());
  const observation = settings.observability;
  const identity = { run_id: input.identity.run_id, attempt: input.attempt, git_sha: input.gitSha };
  const request = FingerprintRequestSchema.parse({ date: identity.run_id.slice(0, 10), writer: hostWriter(identity) });
  const evidence: WorkflowResources = {
    profile_requested: input.profileRequested,
    host_request: request,
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
      const registryPath = input.registryPath ?? join(input.root, "config", "ledgers.json");
      const registrations = await readMetadataRegistrations(registryPath);
      const result = await captureLocalFingerprint(request, config, settings, { outputRoot: input.stateRoot, registryPath });
      if (result.status !== "written") throw new Error("Enabled host instrument did not persist a fingerprint");
      await verifyHostFingerprint(input.stateRoot, result, registrations, identity);
      evidence.host = { ...result, status: "recorded" };
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
  return {
    evidence,
    async close(outcome: TaskOutcome) {
      try { await profile?.close(outcome); }
      catch (error) { fail("profile", error); }
      await save();
    },
  };
}
