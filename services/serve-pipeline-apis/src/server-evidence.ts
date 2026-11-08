/** Which server outcomes were observed during this task, separately from its API result? */
import { z } from "zod";
import { DateStampSchema, OperationMetadataSchema, PositiveCountSchema } from "@idhazh/common-contracts";
import { ApiGroupSchema, ApiReadySchema } from "./declare-api-identity";
import type { ApiGroup } from "./declare-api-identity";
import { ListenerAddressSchema } from "./load-settings";
export { ApiGroupSchema } from "./declare-api-identity";
export type { ApiGroup } from "./declare-api-identity";

// Saved lifecycle envelopes retain this protocol type across listener changes.
export const SERVER_LIFECYCLE_EVENT_TYPE = "hono.server";

export const SERVER_EVIDENCE_VERSION = "2026-11-07";
const serverContract = {
  version: SERVER_EVIDENCE_VERSION,
  readCompatibility: "read 2026-11-04 evidence with its original version and no invented listener or readiness",
  changelog: [
    { version: SERVER_EVIDENCE_VERSION, change: "Retain independent server identity and group-qualified logs." },
    { version: "2026-11-04", change: "Record owned server outcomes and captured native profiles." },
  ],
};
export const ServerRunSchema = z.strictObject({
  run_id: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_-]*$/),
  attempt: PositiveCountSchema,
  started_at: z.iso.datetime(),
  context: OperationMetadataSchema,
});
export type ServerRun = z.infer<typeof ServerRunSchema>;
const LegacyServerLogFilenameSchema = z.string().regex(
  /^hono-server_\d{4}_\d{2}_\d{2}_[A-Za-z0-9][A-Za-z0-9_-]*_[1-9]\d*\.log$/,
);
type LogRun = Pick<ServerRun, "run_id" | "attempt" | "started_at">;
export const ServerLogFilenameSchema = z.string().regex(new RegExp(
  `^hono-server_(${ApiGroupSchema.options.join("|")})_\\d{4}_\\d{2}_\\d{2}_[A-Za-z0-9][A-Za-z0-9_-]*_[1-9]\\d*\\.log$`,
));
function legacyServerLogFilename(run: LogRun): string {
  const date = DateStampSchema.parse(run.started_at.slice(0, 10)).replaceAll("-", "_");
  return LegacyServerLogFilenameSchema.parse(`hono-server_${date}_${run.run_id}_${run.attempt}.log`);
}
export function serverLogFilename(group: ApiGroup, run: LogRun): string {
  const date = DateStampSchema.parse(run.started_at.slice(0, 10)).replaceAll("-", "_");
  return ServerLogFilenameSchema.parse(`hono-server_${ApiGroupSchema.parse(group)}_${date}_${run.run_id}_${run.attempt}.log`);
}

function evidenceFields() {
  return {
  server_name: z.literal("hono-server"),
  group: ApiGroupSchema,
  run_id: ServerRunSchema.shape.run_id,
  attempt: PositiveCountSchema,
  started_at: z.iso.datetime(),
  pid: PositiveCountSchema.nullable(),
  startup: z.enum(["not_started", "ready", "failed"]),
  startup_ms: z.number().finite().nonnegative().nullable(),
  shutdown: z.enum(["not_started", "stopped", "forced", "failed"]),
  exit_code: z.int().nullable(),
  log_available: z.boolean(),
  error_code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  cleanup_error_code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  };
}
export function createCurrentServerEvidenceSchema<Profile>(profile: z.ZodType<Profile>) {
  return z.strictObject({
  version: z.literal(SERVER_EVIDENCE_VERSION),
  ...evidenceFields(),
  log_filename: ServerLogFilenameSchema,
  listener: ListenerAddressSchema,
  identity: ApiReadySchema.nullable(),
  reported_profiles: z.array(profile).describe(
    "Native task-profile reports captured before task exit; no reports does not prove no profiles ran.",
  ),
}).refine(value => value.log_filename === serverLogFilename(value.group, value), {
  path: ["log_filename"], message: "Log filename must match the UTC run-start day, run and attempt",
}).refine(value => value.identity === null ? value.startup !== "ready"
  : value.startup === "ready" && value.identity.pid === value.pid
    && value.identity.group === value.group && value.identity.port === value.listener.port && value.identity.enabled, {
  path: ["identity"], message: "Readiness must identify the observed child and selected listener",
}).meta(serverContract);
}
export function createServerEvidenceSchema<Profile>(profile: z.ZodType<Profile>) {
  const legacy = z.strictObject({
    version: z.literal("2026-11-04"), ...evidenceFields(),
    log_filename: LegacyServerLogFilenameSchema,
    reported_profiles: z.array(profile).default([]),
  }).refine(value => value.log_filename === legacyServerLogFilename(value), {
    path: ["log_filename"], message: "Legacy log filename must match the UTC run-start day, run and attempt",
  });
  return z.discriminatedUnion("version", [createCurrentServerEvidenceSchema(profile), legacy]).meta(serverContract);
}
export type ServerEvidence<Profile> = z.infer<ReturnType<typeof createServerEvidenceSchema<Profile>>>;
export type CurrentServerEvidence<Profile> = z.infer<ReturnType<typeof createCurrentServerEvidenceSchema<Profile>>>;
export const ServerEventDataSchema = z.strictObject({
  server_name: z.literal("hono-server"),
  group: ApiGroupSchema,
  run_id: ServerRunSchema.shape.run_id,
  attempt: PositiveCountSchema,
  severity: z.enum(["info", "warning", "error"]),
  phase: z.enum(["starting", "ready", "stopping", "stopped", "forced", "failed", "log_unavailable", "module_failed"]),
  duration_ms: z.number().finite().nonnegative().nullable(),
  exit_code: z.int().nullable(),
  code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
}).meta({
  version: "2026-11-05",
  readCompatibility: "current_only; delivery completion uses its own request-context payload",
  changelog: [
    { version: "2026-11-05", change: "Separate delivery completion from server lifecycle diagnostics." },
    { version: "2026-11-04", change: "Omit process IDs from server diagnostic payloads." },
  ],
});
export function serverEvidenceFilename(group: ApiGroup): string {
  return `hono-server-${ApiGroupSchema.parse(group)}.json`;
}
