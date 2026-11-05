/** Project feed and delivery diagnostics alongside the validated native machine reports. */
import { ArticleFailureDiagnosticSchema, FeedIngestEventSchema, isArticleFailureDiagnostic, PlannerErrorResponseSchema } from "@idhazh/common-contracts";
import type { ArticleFailureDiagnostic } from "@idhazh/common-contracts";
import { z } from "zod";
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "@idhazh/host-probes/machine-diagnostics";
import type { MachineDiagnosticData } from "@idhazh/host-probes/machine-diagnostics";
import type { TaskProfile } from "@idhazh/host-probes/profile";
import {
  createDeliveryCompletionEvent, DeliveryEventSchema, SafePersistHttpDiagnosticSchema,
} from "./safe-persist-http-diagnostic";
import type { DeliveryEvent } from "./safe-persist-http-diagnostic";

type FeedDiagnosticData = ArticleFailureDiagnostic["data"] | DeliveryEvent["data"] | MachineDiagnosticData;
const LegacyDeliveryFailureSchema = PlannerErrorResponseSchema.pick({ code: true, failure: true }).extend({
  event: z.literal("safe_persist_http_failed"),
});

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
    if ("event" in raw && raw.event === "safe_persist_http_completed") {
      const diagnostic = SafePersistHttpDiagnosticSchema.safeParse(raw);
      return diagnostic.success
        ? { kind: "native_event", createEvent: source => createDeliveryCompletionEvent({
          source, runNumber: diagnostic.data.run_number, attempt: diagnostic.data.attempt,
          status: diagnostic.data.status, commit: diagnostic.data.commit, files: diagnostic.data.files,
          context: diagnostic.data.context,
        }) }
        : { kind: "invalid" };
    }
    if ("event" in raw && raw.event === "safe_persist_http_failed") {
      const failure = LegacyDeliveryFailureSchema.safeParse(raw);
      return failure.success
        ? { kind: "event", data: { phase: "module_failed", severity: "error", code: failure.data.code } }
        : { kind: "invalid" };
    }
  }
  return readMachineApiDiagnostic(raw);
}
