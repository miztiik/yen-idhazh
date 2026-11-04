/** Mirror brief accepted server events live without making an optional file a work deadline. */
import { appendFileSync, closeSync, openSync } from "node:fs";
import { join } from "node:path";
import type { z } from "zod";
import {
  createChildContext, createCloudEvent, FeedIngestEventDataSchema, readCloudEvent,
} from "@idhazh/common-contracts";
import { ServerEventDataSchema, serverLogFilename } from "./server-evidence";
import type { ApiGroup, ServerRun } from "./server-evidence";

type EventInput = Pick<z.infer<typeof ServerEventDataSchema>, "phase">
  & Partial<Pick<z.infer<typeof ServerEventDataSchema>, "severity" | "pid" | "duration_ms" | "exit_code" | "code">>;

export function createServerEventWriter(input: { directory: string; source: string; group: ApiGroup; run: ServerRun }) {
  const context = createChildContext(input.run.context);
  const filename = serverLogFilename(input.run);
  let descriptor: number | undefined;
  let available = true;
  function record(data: EventInput, mirror = true, type = "hono.server") {
    const event = createCloudEvent({
      source: input.source, type, context,
      data: {
        server_name: "hono-server", group: input.group, run_id: input.run.run_id, attempt: input.run.attempt,
        severity: data.severity ?? "info", pid: data.pid ?? null,
        duration_ms: data.duration_ms ?? null, exit_code: data.exit_code ?? null, code: data.code ?? null,
        phase: data.phase,
      },
      parseData: value => ServerEventDataSchema.parse(value),
    });
    const line = `${JSON.stringify(event)}\n`;
    process.stderr.write(line);
    if (mirror && available && descriptor !== undefined) {
      try { appendFileSync(descriptor, line, "utf8"); }
      catch { unavailable(); }
    }
  }
  function unavailable() {
    if (!available) return;
    available = false;
    record({ phase: "log_unavailable", severity: "warning", code: "LOG_FILE_UNAVAILABLE" }, false);
  }
  try { descriptor = openSync(join(input.directory, filename), "a"); }
  catch { unavailable(); }
  return {
    filename,
    get available() { return available; },
    write: record,
    acceptModuleLine(line: string) {
      if (line.trim() === "") return;
      let raw: unknown;
      try { raw = JSON.parse(line); }
      catch {
        record({ phase: "module_failed", severity: "warning", code: "CHILD_DIAGNOSTIC_INVALID" });
        return;
      }
      if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
        record({ phase: "module_failed", severity: "warning", code: "CHILD_DIAGNOSTIC_INVALID" });
        return;
      }
      if ("specversion" in raw) {
        try {
          const event = readCloudEvent(raw, value => FeedIngestEventDataSchema.parse(value));
          if (event.data.phase === "failed") record({ phase: "module_failed", severity: "error", code: "API_OPERATION_FAILED" });
        } catch {
          record({ phase: "module_failed", severity: "warning", code: "CHILD_DIAGNOSTIC_INVALID" });
        }
        return;
      }
      if ("event" in raw && raw.event === "safe_persist_http_completed") {
        record({ phase: "operation_completed" }, true, "safe_persist_http_completed");
        return;
      }
      const code = "code" in raw && typeof raw.code === "string" && /^[A-Z][A-Z0-9_]*$/.test(raw.code)
        ? raw.code : "API_OPERATION_FAILED";
      record({ phase: "module_failed", severity: "error", code });
    },
    close() {
      if (descriptor === undefined) return;
      try { closeSync(descriptor); }
      catch { unavailable(); }
      finally { descriptor = undefined; }
    },
  };
}
