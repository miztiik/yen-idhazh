/** Consume completed work facts immediately without retaining an operation history. */
import { DocumentWorkFactSchema } from "@idhazh/common-contracts";
import type { DocumentWorkFact } from "@idhazh/common-contracts";

export function createIngestObservations(observe: (fact: DocumentWorkFact) => void) {
  return {
    async save(facts: readonly DocumentWorkFact[]) {
      for (const fact of facts) observe(DocumentWorkFactSchema.parse(fact));
    },
  };
}
export type IngestObservations = ReturnType<typeof createIngestObservations>;
