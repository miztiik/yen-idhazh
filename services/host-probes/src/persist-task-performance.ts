/** How does one admitted terminal task get exactly one verified receipt per attempt? */
import { resolve } from "node:path";
import { z } from "zod";
import {
  HOST_FINGERPRINT_VERSION, HostFingerprintRowSchema, TASK_PERFORMANCE_VERSION, TaskPerformanceRowSchema,
} from "@idhazh/common-contracts";
import type { TaskPerformanceRow, WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger, readPrivateRawDay } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { TaskPerformanceExecutionSchema } from "./config";
import type { TaskPerformanceExecution, TaskPerformanceSettings } from "./config";

const TASK_LEDGER = "task-performance";
const HOST_LEDGER = "host-fingerprint";
// This producer is part of the shared writer's work-unit identity.
const PRODUCER = "host-probes";
const taskContract = { schema: TaskPerformanceRowSchema, schemaVersion: TASK_PERFORMANCE_VERSION };
const hostContract = { schema: HostFingerprintRowSchema, schemaVersion: HOST_FINGERPRINT_VERSION };
const registrySchema = z.object({ families: z.array(z.object({
  name: z.string(), lifecycle_status: z.enum(["active", "paused", "retired"]),
  ledgers: z.array(z.object({ name: z.string(), grain: z.string(), prefix: z.array(z.string()).nullable() })),
})) });

export type TaskPerformanceRecordingOptions = {
  outputRoot: string;
  registryPath?: string | URL;
  execution: TaskPerformanceExecution;
  settings: TaskPerformanceSettings;
};
export type TaskPerformanceRecorded = { status: "written"; row: TaskPerformanceRow; files: [PersistedLedgerFile] };
export type TaskPerformanceResult = TaskPerformanceRecorded
  | { status: "disabled"; reason: "configured_off"; row: null; files: [] }
  | { status: "skipped"; reason: "ledger_not_active"; row: null; files: [] };
export type TaskPerformanceWriter = Pick<WriterIdentity, "run_id" | "attempt" | "shard" | "git_sha">
  & Pick<TaskPerformanceRow, "pipeline_name" | "task_name">;

export class TaskPerformanceRequestError extends Error {
  constructor(readonly status: 400 | 403 | 409 | 503, message: string) { super(message); }
}

function registration(registry: z.infer<typeof registrySchema>, name: string): LedgerRegistration {
  const families = registry.families.filter(family => family.name === name);
  const family = families[0];
  const ledgers = family?.ledgers.filter(ledger => ledger.name === name);
  const ledger = ledgers?.[0];
  if (families.length !== 1 || family === undefined || ledgers?.length !== 1 || ledger?.grain !== "raw-and-compact"
    || ledger.prefix?.length !== 1 || ledger.prefix[0] !== name) {
    throw new Error("Recording requires a uniquely registered standalone raw-and-compact family");
  }
  return { name, family: name, grain: ledger.grain, prefix: ledger.prefix, lifecycle_status: family.lifecycle_status };
}

function sameExecution(held: WriterIdentity, expected: TaskPerformanceWriter): boolean {
  return held.run_id === expected.run_id && held.pipeline_name === expected.pipeline_name
    && held.shard === expected.shard && held.attempt === expected.attempt;
}

async function findRecordedTask(
  root: string, entry: LedgerRegistration, writer: TaskPerformanceWriter, row: TaskPerformanceRow,
): Promise<TaskPerformanceRecorded | undefined> {
  let recorded: TaskPerformanceRecorded | undefined;
  for await (const file of readPrivateRawDay(root, entry, row.date, taskContract)) {
    const identity = file.envelope.identity;
    if (!sameExecution(identity, writer) || identity.task_name !== writer.task_name) continue;
    const held = file.rows[0];
    if (recorded !== undefined || file.rows.length !== 1 || held?.row.date !== row.date) {
      throw new Error("A task attempt must have exactly one recorded row");
    }
    if (identity.producer !== PRODUCER || identity.job !== null || identity.git_sha !== writer.git_sha
      || JSON.stringify(held.row) !== JSON.stringify(row)) {
      throw new TaskPerformanceRequestError(409, "Task performance was already recorded with different evidence");
    }
    recorded = { status: "written", row: held.row, files: [file.receipt] };
  }
  return recorded;
}

async function verifyHostCapture(
  root: string, entry: LedgerRegistration, execution: TaskPerformanceExecution,
  writer: TaskPerformanceWriter, unitId: string,
): Promise<void> {
  const opening = execution.legacy_opening_writer;
  for (const day of execution.accounting_days) {
    for await (const file of readPrivateRawDay(root, entry, day, hostContract)) {
      if (file.envelope.unit_id !== unitId || file.rows.length !== 1) continue;
      const held = file.envelope.identity;
      const row = file.rows[0]?.row;
      if (row?.date !== day || held.git_sha !== writer.git_sha) continue;
      if (sameExecution(held, writer)) return;
      if (opening !== undefined && held.job === opening.job && held.producer === opening.producer
        && held.pipeline_name === null && held.task_name === null && held.run_id === opening.run_id
        && held.attempt === opening.attempt && held.shard === opening.shard
        && row.job === opening.job && row.job_seconds === null && row.model_load_ms === null
        && row.server_prompt_seconds === null && row.server_prompt_tokens === null) return;
    }
  }
  throw new TaskPerformanceRequestError(400, "Host capture does not match the launched execution");
}

export function createTaskPerformanceRecorder(options: TaskPerformanceRecordingOptions) {
  const execution = TaskPerformanceExecutionSchema.parse(options.execution);
  const outputRoot = resolve(z.string().min(1).parse(options.outputRoot));
  const registryPath = options.registryPath ?? new URL("../../../config/ledgers.json", import.meta.url);
  const { observability, ledger: ledgerSettings } = options.settings;
  const pending = new Map<string, Promise<void>>();
  let closing = false;

  async function persist(row: TaskPerformanceRow, writer: TaskPerformanceWriter): Promise<TaskPerformanceResult> {
    const registry = registrySchema.parse(await Bun.file(registryPath).json());
    const registryEntry = registration(registry, TASK_LEDGER);
    if (registryEntry.lifecycle_status !== "active") {
      return { status: "skipped", reason: "ledger_not_active", row: null, files: [] };
    }
    const recorded = await findRecordedTask(outputRoot, registryEntry, writer, row);
    if (recorded !== undefined) return recorded;
    if (row.host_unit_id !== null) {
      await verifyHostCapture(outputRoot, registration(registry, HOST_LEDGER), execution, writer, row.host_unit_id);
    }
    const result = await persistLedger({
      ledger: TASK_LEDGER, rowContract: taskContract, outputRoot, registryEntry, ledgerSettings,
      writerContext: { ...writer, job: null, producer: PRODUCER },
      period: { tier: "raw", covers: row.date }, rows: [row],
    });
    const receipt = result.files[0];
    if (result.status !== "written" || result.files.length !== 1 || receipt === undefined) {
      throw new Error("Shared writer did not complete one Task Performance file");
    }
    return { status: "written", row, files: [receipt] };
  }

  return {
    async record(row: TaskPerformanceRow, writer: TaskPerformanceWriter): Promise<TaskPerformanceResult> {
      if (closing) throw new TaskPerformanceRequestError(503, "Task performance recorder is closing");
      if (execution.run_id !== writer.run_id || execution.attempt !== writer.attempt
        || execution.pipeline_name !== writer.pipeline_name || execution.shard !== writer.shard
        || execution.git_sha !== writer.git_sha || !execution.accounting_days.includes(row.date)) {
        throw new TaskPerformanceRequestError(403, "Task performance does not match the launched execution");
      }
      if (!observability.host_telemetry_enabled) {
        return { status: "disabled", reason: "configured_off", row: null, files: [] };
      }
      if (!observability.memory_profiling_enabled
        && (row.machine_memory_available_min_kib !== null || row.worker_rss_peak_kib !== null)) {
        throw new TaskPerformanceRequestError(400, "Task performance memory profiling is configured off");
      }
      const key = JSON.stringify([row.date, row.run_id, row.pipeline_name, row.task_name, row.shard, writer.attempt]);
      const result = (pending.get(key) ?? Promise.resolve()).then(() => persist(row, writer));
      // The request reports a failed write; it must not poison the next retry.
      const tail = result.then(() => {}, () => {});
      pending.set(key, tail);
      try { return await result; }
      finally { if (pending.get(key) === tail) pending.delete(key); }
    },
    async close(): Promise<void> {
      closing = true;
      await Promise.all(pending.values());
    },
  };
}
