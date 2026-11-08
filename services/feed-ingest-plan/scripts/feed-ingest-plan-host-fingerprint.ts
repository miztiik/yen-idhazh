/** Which actual host fingerprint belongs to one planner API run? */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import {
  FingerprintRequestSchema, SelectedSettingsSchema, loadConfig as loadFingerprintConfig,
} from "../../host-fingerprints/src/config";
import { FingerprintWrittenSchema } from "../../host-fingerprints/src/api/fingerprint-response";
import { requestFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";
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

function hostRequest(identity: ExecutionIdentity) {
  const captured = ExecutionIdentitySchema.parse(identity);
  return FingerprintRequestSchema.parse({
    date: captured.run_id.slice(0, 10), writer: hostWriter(captured),
  });
}

function writeHostEvidence(directory: string, evidence: WorkflowHostFingerprint) {
  return writeFile(join(directory, "host-fingerprint.json"), JSON.stringify(WorkflowHostFingerprintSchema.parse(evidence)));
}

function failedHostEvidence(input: { root: string; directory: string }, error: unknown) {
  const failure = describePlanError(error, input.root);
  const reason = failure.issues.map(issue => issue.message).join("; ")
    .replaceAll(input.directory.replaceAll("\\", "/"), "feed-ingest-plan");
  writeJsonLine({ event: "planner_host_fingerprint_failed", code: failure.code, reason });
  return UnrecordedSchema.parse({ status: "failed", reason: `Collection failed (${failure.code}): ${reason}` });
}

export async function retainWorkflowHostFailure(
  input: { root: string; directory: string; identity: ExecutionIdentity }, error: unknown,
) {
  const request = hostRequest(input.identity);
  const file = Bun.file(join(input.directory, "host-fingerprint.json"));
  if (await file.exists()) {
    const previous = WorkflowHostFingerprintSchema.parse(await file.json());
    if (JSON.stringify(previous.host_request) !== JSON.stringify(request)) {
      throw new Error("Fingerprint evidence belongs to another invocation");
    }
    return;
  }
  await writeHostEvidence(input.directory, { host_request: request, host: failedHostEvidence(input, error) });
}

export async function captureWorkflowHostFingerprint(input: {
  root: string; directory: string; stateRoot: string;
  identity: ExecutionIdentity; registrations: MetadataRegistrations;
  origin?: string; signal?: AbortSignal;
}) {
  const identity = ExecutionIdentitySchema.parse(input.identity);
  const settings = SelectedSettingsSchema.parse(await Bun.file(join(input.root, "config", "idhazh.json")).json());
  const request = hostRequest(identity);
  const evidence: WorkflowHostFingerprint = {
    host_request: request,
    host: { status: "unavailable", reason: "Host collection has not finished" },
  };
  if (!settings.observability.host_telemetry_enabled || !settings.observability.host_fingerprint) {
    evidence.host = {
      status: "disabled",
      reason: !settings.observability.host_telemetry_enabled
        ? "observability.host_telemetry_enabled=false" : "observability.host_fingerprint=false",
    };
  } else {
    try {
      if (input.origin === undefined) throw new Error("Enabled fingerprint capture requires its owned listener");
      const config = await loadFingerprintConfig(join(input.root, "config", "host-fingerprints.json"));
      const result = await requestFingerprint(input.origin, request, config, settings, input.signal);
      if (result.status !== "written") throw new Error("Enabled host instrument did not persist a fingerprint");
      await verifyHostFingerprint(input.stateRoot, result, input.registrations, identity);
      evidence.host = { ...result, status: "recorded" };
    } catch (error) {
      evidence.host = failedHostEvidence(input, error);
    }
  }
  await writeHostEvidence(input.directory, evidence);
  return WorkflowHostFingerprintSchema.parse(evidence);
}
