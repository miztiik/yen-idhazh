/** Project feed and delivery diagnostics alongside the validated native machine reports. */
import { ArticleFailureDiagnosticSchema, FeedIngestEventDataSchema, isArticleFailureDiagnostic, readCloudEvent } from "@idhazh/common-contracts";
import type { ArticleFailureDiagnostic } from "@idhazh/common-contracts";
import type { z } from "zod";
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "@idhazh/host-probes/machine-diagnostics";
import type { TaskProfile } from "@idhazh/host-probes/profile";
import {
  createDeliveryCompletionEvent, DeliveryCompletionDiagnosticSchema, SafePersistHttpDiagnosticSchema,
} from "./safe-persist-http-diagnostic";

type FeedDiagnosticData = ArticleFailureDiagnostic["data"] | z.infer<typeof DeliveryCompletionDiagnosticSchema>;

export function readFeedApiDiagnostic(raw: unknown): ApiDiagnostic<TaskProfile, FeedDiagnosticData> {
  if (raw !== null && typeof raw === "object" && !Array.isArray(raw)) {
    if ("specversion" in raw) {
      if (isArticleFailureDiagnostic(raw)) {
        const event = ArticleFailureDiagnosticSchema.safeParse(raw);
        return event.success
          ? { kind: "native_event", createEvent: () => event.data }
          : { kind: "invalid" };
      }
      try {
        const event = readCloudEvent(raw, value => FeedIngestEventDataSchema.parse(value));
        return event.data.phase === "failed"
          ? { kind: "event", data: { phase: "module_failed", severity: "error", code: "API_OPERATION_FAILED" } }
          : { kind: "ignored" };
      } catch { return { kind: "invalid" }; }
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
  }
  return readMachineApiDiagnostic(raw);
}
