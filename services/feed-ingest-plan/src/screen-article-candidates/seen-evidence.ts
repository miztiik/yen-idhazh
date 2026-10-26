/** Which settled first sight belongs to a candidate's canonical URL key? */
import { z } from "zod";
import { DiscoveredArticleRowSchema, TimestampSchema } from "@idhazh/common-contracts";

export const UtcInstantSchema = TimestampSchema.refine(value => {
  const instant = Date.parse(value);
  return Number.isFinite(instant) && new Date(instant).toISOString().replace(".000Z", "Z") === value;
}, "must be a valid UTC instant");

// Read copy of backend/idhazh/contracts/seen.py, held in step by seen-evidence.json.
export const SeenRowSchema = DiscoveredArticleRowSchema;
export const SeenEvidenceSchema = z.discriminatedUnion("availability", [
  z.strictObject({ availability: z.literal("available"), rows: z.array(SeenRowSchema) }),
  z.strictObject({ availability: z.literal("unavailable") }),
]);
export type SeenEvidence = z.infer<typeof SeenEvidenceSchema>;
export type SeenRow = z.infer<typeof SeenRowSchema>;

export function indexSeenEvidence(evidence: SeenEvidence): ReadonlyMap<string, SeenRow> {
  const parsed = SeenEvidenceSchema.parse(evidence);
  const indexed = new Map<string, SeenRow>();
  if (parsed.availability === "unavailable") return indexed;
  for (const row of parsed.rows) {
    const previous = indexed.get(row.url_key);
    if (previous && previous.first_seen_at !== row.first_seen_at) {
      throw new Error(`seen.rows.${row.url_key}: conflicting settled first sight`);
    }
    indexed.set(row.url_key, row);
  }
  return indexed;
}
