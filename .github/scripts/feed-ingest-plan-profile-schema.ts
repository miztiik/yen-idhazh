/** Which body-free resource evidence belongs to one isolated planning attempt? */
import { z } from "../../services/host-probes/node_modules/zod";
import {
  HostFingerprintRowSchema, PlannerObservationSchema, RequestIdSchema, RunIdSchema, Sha256Schema, WriterIdentitySchema,
} from "../../packages/common-contracts/src/index";
import { TaskProfileConfigSchema } from "../../services/host-probes/src/config";
import { TaskProfileSchema } from "../../services/host-probes/src/task-profile/profile-schema";
import { HostSampleSchema } from "../../services/host-probes/src/probe/sample-host";
import { CacheProofSchema } from "./feed-ingest-plan-cache-proof";

export const WorkflowMachineMemorySchema = z.enum(["false", "true"]).default("false")
  .transform(value => value === "true");
export const ProfileProofIdentitySchema = z.strictObject({
  git_sha: WriterIdentitySchema.shape.git_sha,
  run_id: RunIdSchema, attempt: WriterIdentitySchema.shape.attempt, correlation_id: RequestIdSchema,
});
export const DocumentProfilingSchema = z.strictObject({
  profiles: z.array(TaskProfileSchema).max(2),
  actual_work_count: z.int().nonnegative().nullable(),
  after_checks_count: z.int().nonnegative().nullable(),
});

// Read only the fields the report uses; existing HTTP proof responses remain outside this projection.
const ProfileCallSchema = z.object({
  stage: z.string(), endpoint: z.enum(["fetch", "parse"]),
  request: z.object({
    request_id: RequestIdSchema, correlation_id: RequestIdSchema,
    source_id: PlannerObservationSchema.shape.source_id.optional(),
    kind: z.enum(["feed", "article"]).optional(),
    article_id: Sha256Schema.optional(), fetch_request_id: RequestIdSchema.optional(),
  }),
  http_status: z.int().min(100).max(599), response_sha256: Sha256Schema,
  network: z.strictObject({ dns: z.int().nonnegative(), http: z.int().nonnegative() }),
});
export const StageProfileProofSchema = z.object({
  ...ProfileProofIdentitySchema.shape,
  scope: z.literal("live_configured_feed_and_selected_article"),
  status: z.enum(["running", "complete", "failed"]),
  task_profile: TaskProfileConfigSchema,
  documents: z.array(z.object({
    kind: z.enum(["feed", "article"]), status: z.enum(["running", "complete", "failed"]),
    git_sha: WriterIdentitySchema.shape.git_sha, run_id: RunIdSchema, correlation_id: RequestIdSchema,
    source_id: PlannerObservationSchema.shape.source_id.nullable(), article_id: Sha256Schema.nullable(),
    calls: z.array(ProfileCallSchema).max(7),
    profiling: DocumentProfilingSchema.optional(),
    journal_records_sha256: z.strictObject({ before_restart: Sha256Schema, after_checks: Sha256Schema }).nullable(),
  })).max(2),
});

const fields = HostFingerprintRowSchema.shape;
export const CopyResultSchema = z.object({
  memcpy_probe_mib: fields.memcpy_probe_mib, memcpy_gib_s: fields.memcpy_gib_s,
  l3_cache_bytes: fields.l3_cache_bytes, cpu_model: fields.cpu_model,
  cpu_logical_processors: fields.cpu_logical_processors, cpu_allowed_processors: fields.cpu_allowed_processors,
  cpu_quota_state: fields.cpu_quota_state, cpu_quota_cores: fields.cpu_quota_cores, fingerprint: fields.fingerprint,
}).strip();
export const ResourceProofSchema = z.strictObject({
  ...ProfileProofIdentitySchema.shape,
  scope: z.literal("live_linux_ram_http_and_separate_copy"),
  status: z.enum(["running", "complete", "failed"]),
  stage: z.enum(["start", "ram_http", "copy_off", "copy_on", "cache", "complete"]),
  host: z.strictObject({ platform: z.literal("linux"), arch: z.string(), release: z.string(), bun: z.string() }),
  sample: HostSampleSchema.nullable(),
  copy: z.strictObject({
    task_name: z.string().min(1),
    floor_mib: z.int().nonnegative(), cache_multiple: z.int().positive(), repeats: z.int().positive(),
    buffers: z.literal(2), method: z.literal("median_read_plus_write"),
    off: CopyResultSchema.nullable(), on: CopyResultSchema.nullable(),
    off_reason: z.enum(["configured_off", "allocation_unavailable", "clock_unavailable"]).nullable(),
    on_reason: z.enum(["configured_off", "allocation_unavailable", "clock_unavailable"]).nullable(),
  }).nullable(),
  cache: CacheProofSchema.nullable().default(null),
  error: z.string().nullable(),
});
export type ProfileProofIdentity = z.infer<typeof ProfileProofIdentitySchema>;
export type StageProfileProof = z.infer<typeof StageProfileProofSchema>;
export type ResourceProof = z.infer<typeof ResourceProofSchema>;
