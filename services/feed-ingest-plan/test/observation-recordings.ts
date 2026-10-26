/** Collect the real streamed work facts at the test boundary, never in a persisted audit ledger. */
import type { DocumentWorkFact } from "@idhazh/common-contracts";
import { createIngestObservations } from "../src/ingest-observations";
import type { HarvestContext } from "../src/harvest-feeds/harvest-types";

export function recordHarvestObservations(context: HarvestContext) {
  const facts: DocumentWorkFact[] = [];
  context.observations = createIngestObservations(fact => { facts.push(fact); });
  context.observation_clock = context.clock ?? (() => new Date());
  return facts;
}
