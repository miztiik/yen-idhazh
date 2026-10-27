/** Which settled discovery belongs to a candidate's canonical URL key? */
import { z } from "zod";
import { DiscoveredArticleRowSchema } from "@idhazh/common-contracts";

export const DiscoveredRowSchema = DiscoveredArticleRowSchema;
export const DiscoveredEvidenceSchema = z.discriminatedUnion("availability", [
  z.strictObject({ availability: z.literal("available"), rows: z.array(DiscoveredRowSchema) }),
  z.strictObject({ availability: z.literal("unavailable") }),
]);
export type DiscoveredEvidence = z.infer<typeof DiscoveredEvidenceSchema>;
export type DiscoveredRow = z.infer<typeof DiscoveredRowSchema>;

export function indexDiscoveredEvidence(evidence: DiscoveredEvidence): ReadonlyMap<string, DiscoveredRow> {
  const parsed = DiscoveredEvidenceSchema.parse(evidence);
  const indexed = new Map<string, DiscoveredRow>();
  if (parsed.availability === "unavailable") return indexed;
  for (const row of parsed.rows) {
    const previous = indexed.get(row.url_key);
    if (previous && previous.first_seen_at !== row.first_seen_at) {
      throw new Error(`discovered.rows.${row.url_key}: conflicting settled first sight`);
    }
    indexed.set(row.url_key, row);
  }
  return indexed;
}
