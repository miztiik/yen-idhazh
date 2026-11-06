/** Project feed and delivery diagnostics alongside the validated native machine reports. */
import { ArticleFailureDiagnosticSchema, FeedIngestEventSchema, isArticleFailureDiagnostic } from "@idhazh/common-contracts";
import type { ArticleFailureDiagnostic } from "@idhazh/common-contracts";
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "@idhazh/host-probes/machine-diagnostics";
import type { MachineDiagnosticData } from "@idhazh/host-probes/machine-diagnostics";
import type { TaskProfile } from "@idhazh/host-probes/profile";
import { DeliveryEventSchema } from "./safe-persist-http-diagnostic";
import type { DeliveryEvent } from "./safe-persist-http-diagnostic";

type FeedDiagnosticData = ArticleFailureDiagnostic["data"] | DeliveryEvent["data"] | MachineDiagnosticData;

export function readFeedApiDiagnostic(raw: unknown): ApiDiagnostic<TaskProfile, FeedDiagnosticData> {
  if (raw !== null && typeof raw === "object" && !Array.isArray(raw)) {
    if ("specversion" in raw) {
      if ("type" in raw && (raw.type === "safe_persist_http_completed" || raw.type === "safe_persist_http_failed")) {
        const event = DeliveryEventSchema.safeParse(raw);
        return event.success ? { kind: "native_event", createEvent: () => event.data } : { kind: "invalid" };
      }
      if (!("type" in raw) || raw.type !== "planner.progress") return readMachineApiDiagnostic(raw);
      if (isArticleFailureDiagnostic(raw)) {
        const event = ArticleFailureDiagnosticSchema.safeParse(raw);
        return event.success
          ? { kind: "native_event", createEvent: () => event.data }
          : { kind: "invalid" };
      }
      const event = FeedIngestEventSchema.safeParse(raw);
      if (!event.success) return { kind: "invalid" };
      return event.data.data.phase === "failed"
        ? { kind: "event", data: { phase: "module_failed", severity: "error", code: "API_OPERATION_FAILED" } }
        : { kind: "ignored" };
    }
  }
  return readMachineApiDiagnostic(raw);
}
