/** Which authored settings bound the operator listener and its named input files? */
import { z } from "zod";
import { DateStampSchema, NonEmptySchema, PositiveCountSchema } from "@idhazh/common-contracts";

export const RelativePathSchema = NonEmptySchema.refine(
  value => !value.includes("\\") && !value.includes(":") && !value.startsWith("/")
    && value.split("/").every(part => part !== "" && part !== "." && part !== ".."),
  "must be a relative POSIX path without parent traversal",
);
export const SeenDayInputSchema = z.strictObject({
  day: DateStampSchema,
  indexes: z.strictObject({
    yearly: RelativePathSchema.optional(), monthly: RelativePathSchema.optional(),
    daily: RelativePathSchema.optional(),
  }).optional(),
  raw_files: z.array(RelativePathSchema).optional(),
  raw_index: RelativePathSchema.optional(),
}).refine(value => value.raw_files === undefined || value.raw_index === undefined, {
  message: "name raw_files or raw_index, not both",
});
export type SeenDayInput = z.infer<typeof SeenDayInputSchema>;
export const ServiceSettingsSchema = z.strictObject({
  enabled: z.boolean().default(false).describe(
    "Remove when complete-attempt audit writes and verification are integrated and approved.",
  ),
  removal_condition: NonEmptySchema,
  listener: z.strictObject({
    hostname: NonEmptySchema, port: PositiveCountSchema.max(65535),
    idle_timeout_seconds: PositiveCountSchema.max(255),
    max_body_bytes: PositiveCountSchema,
  }),
  inputs: z.strictObject({
    planning: RelativePathSchema, taxonomy: RelativePathSchema, sources: RelativePathSchema,
    watchlist: RelativePathSchema,
    extraction: RelativePathSchema, registrations: RelativePathSchema,
    output_root: RelativePathSchema, seen_files: z.array(RelativePathSchema),
    seen_days: z.array(SeenDayInputSchema).default([]),
    published_days: z.array(SeenDayInputSchema).default([]),
    settled_failure_days: z.array(SeenDayInputSchema).default([]),
    feed_health_days: z.array(SeenDayInputSchema).default([]),
    document_observation_days: z.array(SeenDayInputSchema).default([]),
  }),
  run: z.strictObject({ attempt: PositiveCountSchema, producer: NonEmptySchema }),
});
export type ServiceSettings = z.infer<typeof ServiceSettingsSchema>;
