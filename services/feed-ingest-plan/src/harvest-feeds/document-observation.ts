/** Keep article and run identity while assigning each stage observation its own cause. */
import { createUuidV5 } from "@idhazh/ledger-file-writer";
import { EVENT_NAMESPACE } from "../logging/structured-logger";

export type DocumentIdentity = {
  run_id: string; correlation_id: string; article_id: string | null; feed_id: string | null;
};
export function observeDocument(
  identity: DocumentIdentity, key: string, operation: "fetch" | "parse" | "attempt",
  caused_by_event_id: string | null, occurred_at: string,
) {
  return {
    ...identity, operation, caused_by_event_id, occurred_at,
    event_id: createUuidV5(EVENT_NAMESPACE, `document\n${identity.correlation_id}\n${key}\n${operation}`),
  };
}
