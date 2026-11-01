/** Which completed metadata can cross the safe-persist HTTP boundary and be confirmed? */
import { z } from "zod";
import { WriterIdentitySchema } from "@idhazh/common-contracts";
import { PlannerReadySchema, PlannerStartupSchema, PlannerStartupFailureSchema } from "../src/config/planner-startup";
import { RelativePathSchema } from "../src/config/service-settings";

export const SafePersistHttpRequestSchema = z.strictObject({
  runNumber: z.string().regex(/^\d+$/),
  attempt: WriterIdentitySchema.shape.attempt,
  paths: z.array(RelativePathSchema).refine(paths => new Set(paths).size === paths.length,
    "Completed output paths must be unique"),
}).meta({
  version: "2026-10-31",
  changelog: [{ version: "2026-10-31", change: "Identify completed metadata for the existing safe-persist adapter over HTTP." }],
});
export type SafePersistHttpRequest = z.infer<typeof SafePersistHttpRequestSchema>;

// Startup controls use the existing private pipe protocol, never the HTTP request.
export const SafePersistHttpStartupSchema = PlannerStartupSchema.pick({
  nonce: true, settings: true, output_root: true,
});
export const SafePersistHttpReadySchema = PlannerReadySchema.pick({
  nonce: true, pid: true, port: true,
}).extend({ event: z.literal("safe_persist_ready") });
export const SafePersistHttpStartupFailureSchema = PlannerStartupFailureSchema.extend({
  event: z.literal("safe_persist_startup_failed"),
});

export const MetadataDeliveryResultSchema = z.strictObject({
  status: z.enum(["landed", "already-on-main", "no-changes", "failed"]),
  commit: z.string().regex(/^[a-f0-9]{40,64}$/).nullable(),
  files: z.int().nonnegative(), paths: z.array(RelativePathSchema),
}).superRefine((value, context) => {
  if (value.files !== value.paths.length || new Set(value.paths).size !== value.files
    || ((value.status === "landed" || value.status === "already-on-main") !== (value.commit !== null))
    || (value.status === "no-changes" && value.files !== 0)
    || ((value.status === "landed" || value.status === "already-on-main") && value.files === 0)) {
    context.addIssue({ code: "custom", message: "Commit status, identity and exact file paths must agree" });
  }
}).meta({
  version: "2026-10-31",
  changelog: [{ version: "2026-10-31", change: "Expose the unchanged exact metadata delivery receipt over HTTP." }],
});

export function isMetadataDeliveryConfirmed(
  delivery: z.infer<typeof MetadataDeliveryResultSchema> | null, paths: readonly string[],
): boolean {
  return delivery !== null && delivery.files === paths.length
    && [...delivery.paths].sort().join("\n") === [...paths].sort().join("\n")
    && (delivery.status === "no-changes"
      || ((delivery.status === "landed" || delivery.status === "already-on-main") && delivery.commit !== null));
}
