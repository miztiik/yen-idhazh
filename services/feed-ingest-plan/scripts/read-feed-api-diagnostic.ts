/** Project feed and delivery diagnostics alongside the validated native machine reports. */
import { FeedIngestEventDataSchema, readCloudEvent } from "@idhazh/common-contracts";
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "@idhazh/host-probes/machine-diagnostics";
import type { TaskProfile } from "@idhazh/host-probes/profile";

export function readFeedApiDiagnostic(raw: unknown): ApiDiagnostic<TaskProfile> {
  if (raw !== null && typeof raw === "object" && !Array.isArray(raw)) {
    if ("specversion" in raw) {
      try {
        const event = readCloudEvent(raw, value => FeedIngestEventDataSchema.parse(value));
        return event.data.phase === "failed"
          ? { kind: "event", data: { phase: "module_failed", severity: "error", code: "API_OPERATION_FAILED" } }
          : { kind: "ignored" };
      } catch { return { kind: "invalid" }; }
    }
    if ("event" in raw && raw.event === "safe_persist_http_completed") {
      return { kind: "event", data: { phase: "operation_completed" }, type: "safe_persist_http_completed" };
    }
  }
  return readMachineApiDiagnostic(raw);
}
