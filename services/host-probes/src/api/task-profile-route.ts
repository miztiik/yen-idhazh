/** Which validated operator command may own or close a task collector? */
import { z } from "zod";
import { OperationMetadataSchema, readTraceContext } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { CommandBodyError, readCommandBody } from "./command-body";
import type { ProbeRequestDiagnostics } from "./command-body";
import { createProbeCompletionEvent } from "./create-probe-event";
import { StartTaskProfileSchema, StopTaskProfileSchema } from "./task-command-schema";
import { TaskProfileCommandError } from "./task-profile-manager";
import type { TaskProfileManager } from "./task-profile-manager";

function profileOperation(value: OperationMetadata): OperationMetadata {
  return OperationMetadataSchema.parse({
    traceId: value.traceId, spanId: value.spanId, links: value.links,
    ...(value.parentSpanId === undefined ? {} : { parentSpanId: value.parentSpanId }),
    ...(value.traceState === undefined ? {} : { traceState: value.traceState }),
  });
}

export async function postTaskProfile(
  command: "start" | "stop", request: Request, manager: TaskProfileManager, maxBytes: number,
  diagnostics: ProbeRequestDiagnostics, bodyTimeoutMs?: number,
): Promise<Response> {
  const raw = await readCommandBody(request, maxBytes, diagnostics, bodyTimeoutMs);
  const result = command === "start"
    ? await manager.start(StartTaskProfileSchema.parse(raw), request.signal, readTraceContext({
      traceparent: request.headers.get("traceparent") ?? undefined,
      tracestate: request.headers.get("tracestate") ?? undefined,
    }))
    : await manager.stop(StopTaskProfileSchema.parse(raw));
  const context = result.status === "started" ? profileOperation(result)
    : result.status === "stopped" ? profileOperation(result.profile) : diagnostics.context;
  diagnostics.writeEvent(createProbeCompletionEvent({
    context, operation: command === "start" ? "start-task-profile" : "stop-task-profile",
    outcome: result.status === "disabled" ? "disabled" : "handled",
  }));
  return Response.json(result, { headers: { "Cache-Control": "no-store" } });
}

export function probeErrorResponse(error: unknown): Response {
  const headers = { "Cache-Control": "no-store" };
  if (error instanceof CommandBodyError || error instanceof TaskProfileCommandError) {
    return Response.json({ error: error.message }, { status: error.status, headers });
  }
  if (error instanceof z.ZodError || error instanceof SyntaxError) {
    return Response.json({ error: "Invalid host probe request" }, { status: 400, headers });
  }
  return Response.json({ error: "Host profiling failed" }, { status: 500, headers });
}
