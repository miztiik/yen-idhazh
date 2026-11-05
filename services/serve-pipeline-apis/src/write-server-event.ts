/** Mirror brief accepted server events live without making an optional file a work deadline. */
import { appendFileSync, closeSync, openSync } from "node:fs";
import { join } from "node:path";
import type { z } from "zod";
import { createChildContext, createCloudEvent } from "@idhazh/common-contracts";
import type { CloudEvent, OperationMetadata } from "@idhazh/common-contracts";
import { SERVER_LIFECYCLE_EVENT_TYPE, ServerEventDataSchema, serverLogFilename } from "./server-evidence";
import type { ApiGroup, ServerRun } from "./server-evidence";
import { RequestFailureDiagnosticSchema, RequestFailureEventSchema } from "./create-request-failure-event";

export type ServerEventInput = Pick<z.infer<typeof ServerEventDataSchema>, "phase">
  & Partial<Pick<z.infer<typeof ServerEventDataSchema>, "severity" | "duration_ms" | "exit_code" | "code">>;
export type ApiDiagnostic<Profile, NativeData = never> =
  | { kind: "ignored" | "invalid" }
  | { kind: "event"; data: ServerEventInput }
  | { kind: "native_event"; createEvent: (source: string) => CloudEvent<NativeData> }
  | { kind: "profile"; profile: Profile; operation: Pick<OperationMetadata, "traceId" | "spanId"> };

export function createServerEventWriter<Profile, NativeData = never>(input: {
  directory: string; source: string; group: ApiGroup; run: ServerRun;
  decode: (raw: unknown) => ApiDiagnostic<Profile, NativeData>;
}) {
  const context = createChildContext(input.run.context);
  const filename = serverLogFilename(input.run);
  let descriptor: number | undefined;
  let available = true;
  const profiles = new Map<string, Profile>();
  function publish<Data>(event: CloudEvent<Data>, mirror = true) {
    const line = `${JSON.stringify(event)}\n`;
    process.stderr.write(line);
    if (mirror && available && descriptor !== undefined) {
      try { appendFileSync(descriptor, line, "utf8"); }
      catch { unavailable(); }
    }
  }
  function record(data: ServerEventInput, mirror = true) {
    const event = createCloudEvent({
      source: input.source, type: SERVER_LIFECYCLE_EVENT_TYPE, context,
      data: {
        server_name: "hono-server", group: input.group, run_id: input.run.run_id, attempt: input.run.attempt,
        severity: data.severity ?? "info",
        duration_ms: data.duration_ms ?? null, exit_code: data.exit_code ?? null, code: data.code ?? null,
        phase: data.phase,
      },
      parseData: value => ServerEventDataSchema.parse(value),
    });
    publish(event, mirror);
  }
  function unavailable() {
    if (!available) return;
    available = false;
    record({ phase: "log_unavailable", severity: "warning", code: "LOG_FILE_UNAVAILABLE" }, false);
  }
  function invalidDiagnostic() {
    record({ phase: "module_failed", severity: "warning", code: "CHILD_DIAGNOSTIC_INVALID" });
  }
  try { descriptor = openSync(join(input.directory, filename), "a"); }
  catch { unavailable(); }
  return {
    filename,
    get available() { return available; },
    get reportedProfiles(): Profile[] { return [...profiles.values()]; },
    write: record,
    acceptModuleLine(line: string) {
      if (line.trim() === "") return;
      let raw: unknown;
      try { raw = JSON.parse(line); }
      catch {
        invalidDiagnostic();
        return;
      }
      if (raw !== null && typeof raw === "object" && !Array.isArray(raw)) {
        if ("type" in raw && raw.type === "typescript_api_request_failed") {
          const event = RequestFailureEventSchema.safeParse(raw);
          if (event.success) publish(event.data);
          else invalidDiagnostic();
          return;
        }
        if ("event" in raw && raw.event === "typescript_api_request_failed") {
          const diagnostic = RequestFailureDiagnosticSchema.safeParse(raw);
          if (diagnostic.success) record({
            phase: "module_failed", severity: "error", code: diagnostic.data.code,
          });
          else invalidDiagnostic();
          return;
        }
      }
      const diagnostic = input.decode(raw);
      if (diagnostic.kind === "invalid") {
        invalidDiagnostic();
      } else if (diagnostic.kind === "profile") {
        profiles.set(`${diagnostic.operation.traceId}:${diagnostic.operation.spanId}`, diagnostic.profile);
      } else if (diagnostic.kind === "event") {
        record(diagnostic.data);
      } else if (diagnostic.kind === "native_event") {
        publish(diagnostic.createEvent(input.source));
      }
    },
    close() {
      if (descriptor === undefined) return;
      try { closeSync(descriptor); }
      catch { unavailable(); }
      finally { descriptor = undefined; }
    },
  };
}
