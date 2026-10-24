/** Which validated operator command may own or close a task collector? */
import { z } from "zod";
import { CommandBodyError, readCommandBody } from "./command-body";
import { StartTaskProfileSchema, StopTaskProfileSchema } from "./task-command-schema";
import { TaskProfileCommandError } from "./task-profile-manager";
import type { TaskProfileManager } from "./task-profile-manager";

export async function postTaskProfile(
  command: "start" | "stop", request: Request, manager: TaskProfileManager, maxBytes: number,
): Promise<Response> {
  const raw = await readCommandBody(request, maxBytes);
  const result = command === "start"
    ? await manager.start(StartTaskProfileSchema.parse(raw), request.signal)
    : await manager.stop(StopTaskProfileSchema.parse(raw));
  return Response.json(result, { headers: { "Cache-Control": "no-store" } });
}

export function probeErrorResponse(error: unknown): Response {
  const headers = { "Cache-Control": "no-store" };
  if (error instanceof CommandBodyError || error instanceof TaskProfileCommandError) {
    return Response.json({ error: error.message }, { status: error.status, headers });
  }
  if (error instanceof z.ZodError || error instanceof SyntaxError) {
    return Response.json({ error: "Invalid task profile request" }, { status: 400, headers });
  }
  console.error(JSON.stringify({ event: "host_probe_failed", error: error instanceof Error ? error.name : "unknown" }));
  return Response.json({ error: "Host profiling failed" }, { status: 500, headers });
}
