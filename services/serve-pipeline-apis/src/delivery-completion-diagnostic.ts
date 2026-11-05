/** Which delivery completion facts and request operation does the server event retain? */
import { z } from "zod";
import { createCloudEvent } from "@idhazh/common-contracts";
import { SafePersistHttpDiagnosticSchema } from "@idhazh/feed-ingest-plan/delivery-diagnostic";
import type { SafePersistHttpDiagnostic } from "@idhazh/feed-ingest-plan/delivery-diagnostic";
import { ServerEventDataSchema } from "./server-evidence";

export const DeliveryCompletionDiagnosticSchema = ServerEventDataSchema.pick({
  server_name: true, severity: true, duration_ms: true, exit_code: true, code: true,
}).extend({
  group: ServerEventDataSchema.shape.group.extract(["delivery"]),
  run_id: SafePersistHttpDiagnosticSchema.shape.run_number,
  attempt: SafePersistHttpDiagnosticSchema.shape.attempt,
  phase: z.literal("operation_completed"),
  status: SafePersistHttpDiagnosticSchema.shape.status,
  commit: SafePersistHttpDiagnosticSchema.shape.commit,
  files: SafePersistHttpDiagnosticSchema.shape.files,
  context: SafePersistHttpDiagnosticSchema.shape.context,
}).meta({
  version: "2026-11-05",
  readCompatibility: "current_only; completion payloads are separate from server lifecycle payloads",
  changelog: [
    { version: "2026-11-05", change: "Preserve native delivery facts and the complete request context in completion events." },
  ],
});

type CompletionAncillary = Partial<Pick<z.infer<typeof DeliveryCompletionDiagnosticSchema>,
  "severity" | "duration_ms" | "exit_code" | "code">>;

export function createDeliveryCompletionEvent(input: {
  source: string; diagnostic: SafePersistHttpDiagnostic;
} & CompletionAncillary) {
  const diagnostic = SafePersistHttpDiagnosticSchema.parse(input.diagnostic);
  return createCloudEvent({
    source: input.source, type: diagnostic.event, context: diagnostic.context,
    data: {
      server_name: "hono-server", group: "delivery", phase: "operation_completed",
      run_id: diagnostic.run_number, attempt: diagnostic.attempt,
      status: diagnostic.status, commit: diagnostic.commit, files: diagnostic.files, context: diagnostic.context,
      severity: input.severity ?? "info", duration_ms: input.duration_ms ?? null,
      exit_code: input.exit_code ?? null, code: input.code ?? null,
    },
    parseData: value => DeliveryCompletionDiagnosticSchema.parse(value),
  });
}
