/** Compose captured operation context with the document's run and work facts. */
import { OperationMetadataSchema } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";

export type DocumentIdentity = {
  run_id: string; article_id: string | null; feed_id: string | null; candidate_id: string | null;
};
export function observeDocument(
  identity: DocumentIdentity, context: OperationMetadata, operation: "fetch" | "parse" | "attempt", occurred_at: string,
) {
  return { ...identity, ...OperationMetadataSchema.parse(context), operation, occurred_at };
}
