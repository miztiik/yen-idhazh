/** Which body-free resource evidence belongs to one isolated planning attempt? */
import { z } from "zod";
import {
  HostFingerprintRowSchema, PlannerObservationSchema, RequestIdSchema, RunIdSchema, Sha256Schema, WriterIdentitySchema,
} from "../../../packages/common-contracts/src/index";
import { TaskProfileConfigSchema } from "../src/config";
import { OwnedProcessSchema, TaskProfileSchema } from "../src/task-profile/profile-schema";
import { HostSampleSchema } from "../src/probe/sample-host";
import { CacheProofSchema } from "./feed-ingest-plan-cache-proof";
import { CacheCountersSchema, CacheCountersStartSchema } from "../src/cache-probe/cache-schema";
import { SelectedSettingsSchema } from "../../host-fingerprints/src/config";

export const WorkflowSettingsSchema = SelectedSettingsSchema.extend({
  observability: SelectedSettingsSchema.shape.observability.extend({
    memory_profiling_enabled: z.boolean(), host_fingerprint_placement_enabled: z.boolean(),
  }),
});

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
export const ControlledWorkResultSchema = z.strictObject({
  type: z.literal("complete"), allocated_bytes: z.int().positive(),
  elapsed_ms: z.number().finite().positive(), batches: z.int().positive(), digest: z.string().regex(/^[a-f0-9]{64}$/),
});
// These identify the fixed controlled proof, not runtime task defaults.
export const CONTROLLED_TASK_NAME = "controlled-cpu-task";
export const CONTROLLED_POLL_INTERVAL_MS = 1000;
const MINIMUM_CONTROLLED_POLLS = 2;
const BYTES_PER_LINUX_KB = 1024;
export const TaskProfileProofSchema = z.strictObject({
  scope: z.literal("controlled_cpu_task"), handle: z.uuid(), expires_at: z.iso.datetime(),
  target: OwnedProcessSchema, server: OwnedProcessSchema, target_alive_at_stop: z.literal(true),
  work: ControlledWorkResultSchema, profile: TaskProfileSchema,
  cache_counters_start: CacheCountersStartSchema.nullable().default(null),
  cache_counters: CacheCountersSchema.nullable().default(null), repeat_stop_identical: z.boolean().default(false),
}).superRefine((value, context) => {
  const { profile, work, target, server } = value;
  const worker = profile.processes.worker;
  const observedServer = profile.processes.server;
  if (profile.identity.pipeline_name !== "host-probes" || profile.identity.task_name !== CONTROLLED_TASK_NAME
    || profile.outcome !== "success" || profile.end_reason !== "explicit_stop"
    || target.pid === server.pid || worker.closing.pid !== target.pid || worker.closing.start_ticks !== target.start_ticks
    || observedServer.closing.pid !== server.pid || observedServer.closing.start_ticks !== server.start_ticks
    || profile.process_clock_ticks_per_second.reason !== null
    || worker.cpu.reason !== null || worker.cpu.value.cpu_time_ms <= 0 || worker.cpu.value.percent_one_core <= 0
    || observedServer.cpu.reason !== null
    || worker.cpu_interval_ms < work.elapsed_ms || profile.elapsed_ms < work.elapsed_ms
    || profile.config.poll_interval_ms !== CONTROLLED_POLL_INTERVAL_MS
    || profile.periodic_sample_count < MINIMUM_CONTROLLED_POLLS
    || !profile.samples.some(sample => sample.phase === "poll" && sample.processes.worker.cpu_window.full_window
      && sample.processes.worker.cpu_window.cpu.value !== null
      && sample.processes.worker.cpu_window.cpu.value.cpu_time_ms > 0)
    || !profile.samples.every((sample, index) => index === 0 || sample.elapsed_ms >= profile.samples[index - 1]!.elapsed_ms)
    || !profile.config.memory_enabled || !profile.config.machine_memory_enabled
    || worker.closing.memory_kb.rss === null || worker.closing.memory_kb.rss < work.allocated_bytes / BYTES_PER_LINUX_KB
    || observedServer.closing.memory_kb.rss === null || profile.machine_available_min_kb === null) {
    context.addIssue({ code: "custom", path: ["profile"], message: "must prove actual external PID CPU, RAM, identities and full-task intervals" });
  }
});
export const ResourceProofSchema = z.strictObject({
  ...ProfileProofIdentitySchema.shape,
  scope: z.literal("live_linux_ram_http_and_separate_copy"),
  status: z.enum(["running", "complete", "failed"]),
  stage: z.enum(["start", "ram_http", "task_cpu_ram_http", "copy_off", "copy_on", "cache", "complete"]),
  host: z.strictObject({ platform: z.literal("linux"), arch: z.string(), release: z.string(), bun: z.string() }),
  sample: HostSampleSchema.nullable(),
  task_profile: TaskProfileProofSchema.nullable().default(null),
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
export type TaskProfileProof = z.infer<typeof TaskProfileProofSchema>;
