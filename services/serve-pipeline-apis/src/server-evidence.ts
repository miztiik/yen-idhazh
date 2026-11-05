/** Which server outcomes were observed during this task, separately from its API result? */
import { z } from "zod";
import { DateStampSchema, OperationMetadataSchema, PositiveCountSchema } from "@idhazh/common-contracts";

export const ApiGroupSchema = z.enum(["planning", "machine", "delivery"]);
export type ApiGroup = z.infer<typeof ApiGroupSchema>;
export const ServerRunSchema = z.strictObject({
  run_id: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_-]*$/),
  attempt: PositiveCountSchema,
  started_at: z.iso.datetime(),
  context: OperationMetadataSchema,
});
export type ServerRun = z.infer<typeof ServerRunSchema>;
export const ServerLogFilenameSchema = z.string().regex(
  /^hono-server_\d{4}_\d{2}_\d{2}_[A-Za-z0-9][A-Za-z0-9_-]*_[1-9]\d*\.log$/,
);
export function serverLogFilename(run: Pick<ServerRun, "run_id" | "attempt" | "started_at">): string {
  const date = DateStampSchema.parse(run.started_at.slice(0, 10)).replaceAll("-", "_");
  return ServerLogFilenameSchema.parse(`hono-server_${date}_${run.run_id}_${run.attempt}.log`);
}

export function createServerEvidenceSchema<Profile>(profile: z.ZodType<Profile>) {
  return z.strictObject({
  version: z.literal("2026-11-04"),
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
  log_filename: ServerLogFilenameSchema,
  log_available: z.boolean(),
  error_code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  cleanup_error_code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  reported_profiles: z.array(profile).default([]).describe(
    "Native task-profile reports captured before task exit; no reports does not prove no profiles ran.",
  ),
}).refine(value => value.log_filename === serverLogFilename(value), {
  path: ["log_filename"], message: "Log filename must match the UTC run-start day, run and attempt",
}).meta({
  version: "2026-11-04",
  readCompatibility: "current_only; earlier same-day evidence has no captured profile reports",
  changelog: [
    { version: "2026-11-04", change: "Retain native task-profile reports when their owning server stops." },
    { version: "2026-11-04", change: "Record actual task-owned TypeScript server outcomes without changing committed ledgers." },
  ],
  });
}
export type ServerEvidence<Profile> = z.infer<ReturnType<typeof createServerEvidenceSchema<Profile>>>;
export const ServerEventDataSchema = z.strictObject({
  server_name: z.literal("hono-server"),
  group: ApiGroupSchema,
  run_id: ServerRunSchema.shape.run_id,
  attempt: PositiveCountSchema,
  severity: z.enum(["info", "warning", "error"]),
  phase: z.enum(["starting", "ready", "stopping", "stopped", "forced", "failed", "log_unavailable", "module_failed", "operation_completed"]),
  duration_ms: z.number().finite().nonnegative().nullable(),
  exit_code: z.int().nullable(),
  code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
}).meta({
  version: "2026-11-04",
  readCompatibility: "current_only; diagnostic payloads omit process IDs",
  changelog: [
    { version: "2026-11-04", change: "Omit process IDs from server diagnostic payloads." },
  ],
});
export function serverEvidenceFilename(group: ApiGroup): string {
  return `hono-server-${ApiGroupSchema.parse(group)}.json`;
}
