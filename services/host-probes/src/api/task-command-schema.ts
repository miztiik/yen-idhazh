/** Which body-free commands start and stop one transient task profile? */
import { z } from "zod";
import { OperationMetadataSchema } from "@idhazh/common-contracts/schemas/operation-metadata";
import { CacheCountersSchema, CacheCountersStartSchema } from "../cache-probe/cache-schema";
import {
  OwnedProcessSchema, TASK_PROFILE_VERSION, TaskEndReasonSchema, TaskIdentitySchema, TaskOutcomeSchema, TaskProfileSchema,
} from "../task-profile/profile-schema";

export const StartTaskProfileSchema = z.strictObject({
  identity: TaskIdentitySchema, target: OwnedProcessSchema, server: OwnedProcessSchema.optional(),
});
export const StopTaskProfileSchema = z.strictObject({ handle: z.uuid(), outcome: TaskOutcomeSchema });
const DisabledSchema = z.strictObject({ status: z.literal("disabled"), reason: z.literal("configured_off") });
export const StartTaskProfileResponseSchema = z.union([
  DisabledSchema,
  OperationMetadataSchema.safeExtend({
    status: z.literal("started"), handle: z.uuid(), expires_at: z.iso.datetime(), target: OwnedProcessSchema,
    cache_counters: CacheCountersStartSchema.nullable().default(null),
  }),
]).meta({
  version: TASK_PROFILE_VERSION,
  readCompatibility: "current_only",
  changelog: [
    { version: TASK_PROFILE_VERSION, change: "Return the allocated profile operation with its live resource handle." },
  ],
});
export const StopTaskProfileResponseSchema = z.union([
  DisabledSchema,
  z.strictObject({
    status: z.literal("stopped"), handle: z.uuid(), end_reason: TaskEndReasonSchema, profile: TaskProfileSchema,
    cache_counters: CacheCountersSchema.nullable().default(null),
  }),
]);
export type StartTaskProfile = z.infer<typeof StartTaskProfileSchema>;
export type StopTaskProfile = z.infer<typeof StopTaskProfileSchema>;
export type StartTaskProfileResponse = z.infer<typeof StartTaskProfileResponseSchema>;
export type StopTaskProfileResponse = z.infer<typeof StopTaskProfileResponseSchema>;
