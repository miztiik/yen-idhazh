/** Which exact immutable paths did the metadata publisher confirm or refuse? */
import { z } from "zod";
import { RelativePathSchema } from "../src/config/service-settings";

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
});

export function isMetadataDeliveryConfirmed(
  delivery: z.infer<typeof MetadataDeliveryResultSchema> | null, paths: readonly string[],
): boolean {
  return delivery !== null && delivery.files === paths.length
    && [...delivery.paths].sort().join("\n") === [...paths].sort().join("\n")
    && (delivery.status === "no-changes"
      || ((delivery.status === "landed" || delivery.status === "already-on-main") && delivery.commit !== null));
}
