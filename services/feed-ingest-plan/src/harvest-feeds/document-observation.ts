/** Keep article and run identity while assigning each stage observation its own cause. */
import { createUuidV5 } from "@idhazh/ledger-file-writer";
import { EVENT_NAMESPACE } from "../logging/structured-logger";
import { PlannerObservationSchema } from "../api/operation-contracts";
import type { FetchAttempt } from "../api/operation-contracts";
import type { HarvestContext } from "./harvest-types";

export type DocumentIdentity = {
  run_id: string; correlation_id: string; article_id: string; source_id: string;
};
export function observeDocument(
  identity: DocumentIdentity, key: string, operation: "fetch" | "parse" | "attempt",
  caused_by_event_id: string | null, occurred_at: string,
) {
  return PlannerObservationSchema.parse({
    ...identity, operation, caused_by_event_id, occurred_at,
    event_id: createUuidV5(EVENT_NAMESPACE, `document\n${identity.correlation_id}\n${key}\n${operation}`),
  });
}
export function emitDocumentObservations(
  context: HarvestContext, identity: DocumentIdentity, key: string, operation: "fetch" | "parse",
  cause: string | null, occurred_at: string, attempts: readonly FetchAttempt[] = [],
) {
  const observation = observeDocument(identity, key, operation, cause, occurred_at);
  context.progress?.(operation === "fetch" ? "DOCUMENT_FETCHED" : "DOCUMENT_PARSED", { document_observation: observation });
  for (const attempt of attempts) context.progress?.("FETCH_ATTEMPT_COMPLETED", {
    document_observation: observeDocument(identity, `${key}\n${attempt.sequence}`, "attempt", observation.event_id, occurred_at),
    fetch_attempt: attempt,
  });
  return observation;
}
