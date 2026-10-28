/** Which actual host fingerprint belongs to one planner API run? */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import {
  FingerprintRequestSchema, SelectedSettingsSchema, loadConfig as loadFingerprintConfig,
} from "../../host-fingerprints/src/config";
import { FingerprintWrittenSchema } from "../../host-fingerprints/src/api/fingerprint-response";
import { captureLocalFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";
import { writeJsonLine } from "../src/logging/structured-logger";
import { describePlanError } from "../src/api/plan-request";
import { ExecutionIdentitySchema, hostWriter } from "./feed-ingest-plan-metadata";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";
import { verifyHostFingerprint } from "./feed-ingest-plan-host-verification";

const UnrecordedSchema = z.strictObject({
  status: z.enum(["disabled", "unavailable", "failed"]), reason: z.string().min(1),
});
export const WorkflowHostFingerprintSchema = z.strictObject({
  host_request: FingerprintRequestSchema,
  host: z.discriminatedUnion("status", [
    FingerprintWrittenSchema.omit({ status: true }).extend({ status: z.literal("recorded") }),
    UnrecordedSchema,
  ]),
});
export type WorkflowHostFingerprint = z.infer<typeof WorkflowHostFingerprintSchema>;

export async function captureWorkflowHostFingerprint(input: {
  root: string; directory: string; stateRoot: string; registryPath: string;
  identity: ExecutionIdentity; registrations: MetadataRegistrations;
}) {
  const identity = ExecutionIdentitySchema.parse(input.identity);
  const settings = SelectedSettingsSchema.parse(await Bun.file(join(input.root, "config", "idhazh.json")).json());
  const request = FingerprintRequestSchema.parse({
    date: identity.run_id.slice(0, 10), writer: hostWriter(identity),
  });
  const evidence: WorkflowHostFingerprint = {
    host_request: request,
    host: { status: "unavailable", reason: "Host collection has not finished" },
  };
  const save = () => writeFile(join(input.directory, "host-fingerprint.json"),
    JSON.stringify(WorkflowHostFingerprintSchema.parse(evidence)));
  const fail = (error: unknown) => {
    const failure = describePlanError(error, input.root);
    const reason = failure.issues.map(issue => issue.message).join("; ")
      .replaceAll(input.directory.replaceAll("\\", "/"), "feed-ingest-plan");
    evidence.host = { status: "failed", reason: `Collection failed (${failure.code}): ${reason}` };
    writeJsonLine({ event: "planner_host_fingerprint_failed", code: failure.code, reason });
  };
  if (!settings.observability.host_telemetry_enabled || !settings.observability.host_fingerprint) {
    evidence.host = {
      status: "disabled",
      reason: !settings.observability.host_telemetry_enabled
        ? "observability.host_telemetry_enabled=false" : "observability.host_fingerprint=false",
    };
  } else {
    try {
      const config = await loadFingerprintConfig(join(input.root, "config", "host-fingerprints.json"));
      const result = await captureLocalFingerprint(request, config, settings, {
        outputRoot: input.stateRoot, registryPath: input.registryPath,
      });
      if (result.status !== "written") throw new Error("Enabled host instrument did not persist a fingerprint");
      await verifyHostFingerprint(input.stateRoot, result, input.registrations, identity);
      evidence.host = { ...result, status: "recorded" };
    } catch (error) {
      fail(error);
    }
  }
  await save();
  return WorkflowHostFingerprintSchema.parse(evidence);
}
