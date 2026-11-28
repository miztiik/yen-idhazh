/** Project feed and delivery diagnostics alongside the validated native machine reports. */
import {
  ArticleFailureDiagnosticSchema, FeedIngestEventSchema, isArticleFailureDiagnostic,
  PLANNER_WORKFLOW_FAILURE_TYPE, PlannerWorkflowFailureSchema,
} from "@idhazh/common-contracts";
import type { ArticleFailureDiagnostic, PlannerWorkflowFailure } from "@idhazh/common-contracts";
import type { ApiGroup, ServerRun } from "@idhazh/serve-pipeline-apis/evidence";
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "@idhazh/host-probes/machine-diagnostics";
import type { MachineDiagnosticData } from "@idhazh/host-probes/machine-diagnostics";
import type { TaskProfile } from "@idhazh/host-probes/profile";
import { PLANNER_EVENT_SOURCE } from "../src/declare-event-source";
import { DeliveryEventSchema } from "./safe-persist-http-diagnostic";
import type { DeliveryEvent } from "./safe-persist-http-diagnostic";

type FeedDiagnosticData = ArticleFailureDiagnostic["data"] | PlannerWorkflowFailure["data"] | DeliveryEvent["data"] | MachineDiagnosticData;

export function readFeedApiDiagnostic(raw: unknown, task: {
  group: ApiGroup; run: ServerRun;
}): ApiDiagnostic<TaskProfile, FeedDiagnosticData> {
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
      const { data: progress, ...envelope } = event.data;
      if (progress.phase !== "failed") {
        return { kind: Object.hasOwn(progress.details, "workflow_failure") ? "invalid" : "ignored" };
      }
      if (task.group !== "planning" || envelope.source !== PLANNER_EVENT_SOURCE) return { kind: "invalid" };
      const failure = PlannerWorkflowFailureSchema.safeParse({
        ...envelope, type: PLANNER_WORKFLOW_FAILURE_TYPE, data: progress.details.workflow_failure,
      });
      const runId = `${task.run.started_at.slice(0, 10)}-${task.run.run_id}`;
      if (!failure.success || progress.run_id !== runId || failure.data.data.run_id !== runId
        || failure.data.data.attempt !== task.run.attempt || failure.data.data.operation !== progress.operation) {
        return { kind: "invalid" };
      }
      return { kind: "native_event", createEvent: () => failure.data };
    }
  }
  return readMachineApiDiagnostic(raw);
}
