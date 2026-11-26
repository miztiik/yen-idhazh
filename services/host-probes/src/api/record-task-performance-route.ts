/** Which bounded command files an already measured terminal task record? */
import { z } from "zod";
import { TASK_PERFORMANCE_VERSION, TaskPerformanceRowSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import { PersistedLedgerFileSchema } from "@idhazh/ledger-file-writer";
import { TaskPerformanceRequestError } from "../persist-task-performance";
import type { createTaskPerformanceRecorder, TaskPerformanceResult } from "../persist-task-performance";
import { readCommandBody } from "./command-body";
import type { ProbeRequestDiagnostics } from "./command-body";
import { createProbeCompletionEvent, createProbeFailureEvent } from "./create-probe-event";

// The release date identifies this native wire format, not the stored row's schema version.
export const RECORD_TASK_PERFORMANCE_PATH = "/api/2026-11-26/record-task-performance";

const { version: _version, date, run_id, pipeline_name, task_name, shard, ...measurement } = TaskPerformanceRowSchema.shape;
export const RecordTaskPerformanceRequestSchema = z.strictObject({
  date,
  writer: z.strictObject({
    run_id, pipeline_name, task_name, shard,
    attempt: WriterIdentitySchema.shape.attempt, git_sha: WriterIdentitySchema.shape.git_sha,
  }),
  measurement: z.strictObject(measurement),
});
export const RecordTaskPerformanceResponseSchema = z.discriminatedUnion("status", [
  z.strictObject({ status: z.literal("written"), row: TaskPerformanceRowSchema, files: z.tuple([PersistedLedgerFileSchema]) }),
  z.strictObject({ status: z.literal("disabled"), reason: z.literal("configured_off"), row: z.null(), files: z.tuple([]) }),
  z.strictObject({ status: z.literal("skipped"), reason: z.literal("ledger_not_active"), row: z.null(), files: z.tuple([]) }),
]);

export async function postRecordTaskPerformance(
  request: Request, recorder: ReturnType<typeof createTaskPerformanceRecorder> | undefined, maxBytes: number,
  diagnostics: ProbeRequestDiagnostics,
): Promise<Response> {
  const input = RecordTaskPerformanceRequestSchema.parse(await readCommandBody(request, maxBytes, diagnostics));
  const writer = input.writer;
  const row = TaskPerformanceRowSchema.parse({
    ...input.measurement, version: TASK_PERFORMANCE_VERSION, date: input.date,
    run_id: writer.run_id, pipeline_name: writer.pipeline_name, task_name: writer.task_name, shard: writer.shard,
  });
  const headers = { "Cache-Control": "no-store" };
  let result: TaskPerformanceResult;
  try {
    if (recorder === undefined) throw new TaskPerformanceRequestError(403, "Task performance requires a trusted launch context");
    result = RecordTaskPerformanceResponseSchema.parse(await recorder.record(row, writer));
  } catch (error) {
    diagnostics.writeEvent(createProbeFailureEvent({ context: diagnostics.context, type: "host_probe_failed" }));
    return error instanceof TaskPerformanceRequestError
      ? Response.json({ error: error.message }, { status: error.status, headers })
      : Response.json({ error: "Task performance persistence failed" }, { status: 500, headers });
  }
  diagnostics.writeEvent(createProbeCompletionEvent({
    context: diagnostics.context, operation: "record-task-performance", outcome: result.status,
  }));
  return Response.json(result, { headers });
}
