/** Which recorded publication fields can be joined without guessing an article or a run? */
import { z } from "zod";
import {
  DateStampSchema, PositiveCountSchema, RunIdSchema, SchemaVersionSchema,
  Sha256Schema, SlugSchema, UrlSchema, deriveUrlKey,
} from "@idhazh/common-contracts";
import { UtcInstantSchema } from "../screen-article-candidates/seen-evidence";

// Read copies of contracts/seen.py, item_health.py and digest_day.py.
// Projections strip unrelated columns; they are not contracts for writing those payloads.
export const ItemIdSchema = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})$/);
export const PUBLISHED_ROW_SCHEMA_VERSION = "2026-09-12T18:40" as const;
export const PublishedRowSchema = z.object({
  version: SchemaVersionSchema, url_key: Sha256Schema,
  published_on: DateStampSchema, item_id: ItemIdSchema,
});
export const ItemHealthPublicationSchema = z.object({
  date: DateStampSchema, run_id: RunIdSchema, item_id: ItemIdSchema,
  url_key: Sha256Schema, source_id: SlugSchema,
  stage: z.enum(["plan", "fetch", "extract", "summarize", "publish"]),
  outcome: z.enum(["ok", "failed"]),
});
export const DigestPublicationSchema = z.object({
  date: DateStampSchema, generated_at: UtcInstantSchema,
  runs: z.array(z.object({
    n: PositiveCountSchema, run_id: RunIdSchema.nullable().default(null),
    items_added: z.int().nonnegative(),
  })).min(1),
  items: z.array(z.object({
    item_id: ItemIdSchema, source_id: SlugSchema, source_url: UrlSchema,
    source_kind: SlugSchema.optional(), introduced_by_run: PositiveCountSchema,
    title: z.string().min(1).optional(), source_name: z.string().min(1).optional(),
  })),
  leads: z.array(z.object({ item_id: ItemIdSchema })).default([]),
}).superRefine((day, ctx) => {
  const reject = (message: string) => ctx.addIssue({ code: "custom", message });
  if (new Set(day.items.map(item => item.item_id)).size !== day.items.length) reject("digest item identities must be distinct");
  if (new Set(day.runs.map(run => run.n)).size !== day.runs.length) reject("digest run ordinals must be distinct");
  const named = day.runs.flatMap(run => run.run_id === null ? [] : [run.run_id]);
  if (new Set(named).size !== named.length) reject("digest run identities must be distinct");
  for (const run of day.runs) {
    if (run.run_id !== null && run.run_id.slice(0, 10) !== day.date) reject("digest run belongs to another day");
    if (day.items.filter(item => item.introduced_by_run === run.n).length !== run.items_added) reject("digest run item count differs from membership");
  }
  for (const item of day.items) {
    if (!day.runs.some(run => run.n === item.introduced_by_run)) reject("digest item names an absent run ordinal");
  }
  if (new Set(day.leads.map(lead => lead.item_id)).size !== day.leads.length) reject("digest lead identities must be distinct");
  if (day.leads.some(lead => !day.items.some(item => item.item_id === lead.item_id))) reject("digest lead names an absent item");
});
export type PublishedRow = z.infer<typeof PublishedRowSchema>;
export type ItemHealthPublication = z.infer<typeof ItemHealthPublicationSchema>;
export type DigestPublication = z.infer<typeof DigestPublicationSchema>;
export const DigestEventItemSchema = z.object({
  item_id: ItemIdSchema, source_url: UrlSchema,
  title: z.string().min(1), source_name: z.string().min(1),
});
// Existing StorySimilarityPair fields only; the observer never writes a pair.
export const RecordedEventPairSchema = z.object({
  version: SchemaVersionSchema,
  pair_key: Sha256Schema, left_url_key: Sha256Schema, right_url_key: Sha256Schema,
  scorer_model: SlugSchema, cosine_weight: z.number().finite().min(0).max(1),
  verdict: z.enum(["YES", "NO", "UNCLEAR"]).nullable(),
  verdict_swapped: z.enum(["YES", "NO", "UNCLEAR"]).nullable(), usable: z.boolean(),
  judge_model: SlugSchema.nullable(),
  prompt_digest: Sha256Schema.nullable(), grammar_digest: Sha256Schema.nullable(),
  judge_id: z.literal("content-similarity-judge"),
  judge_temperature: z.number().finite().nonnegative().nullable(), grammar_applied: z.boolean().nullable(),
}).superRefine((pair, ctx) => {
  const reject = (message: string) => ctx.addIssue({ code: "custom", message });
  if (pair.left_url_key >= pair.right_url_key || deriveUrlKey(pair.left_url_key + pair.right_url_key) !== pair.pair_key) {
    reject("recorded pair must have sorted URL keys and their recomputed pair identity");
  }
  const judge = [pair.judge_model, pair.prompt_digest, pair.grammar_digest];
  if (judge.some(value => value !== null) && judge.some(value => value === null)) reject("judge stamps must be present together");
  if (pair.verdict !== null && pair.judge_model === null) reject("a recorded verdict names its judge");
  if (pair.usable && (pair.verdict === null || pair.verdict !== pair.verdict_swapped)) reject("a usable recorded pair agrees in both orders");
});
export type RecordedEventPair = z.infer<typeof RecordedEventPairSchema>;
export type RecordedEventEvidence = Readonly<{
  pairs: readonly RecordedEventPair[];
  items: readonly z.infer<typeof DigestEventItemSchema>[];
}>;
export type EvidenceDay<T> = Readonly<{
  day: string; status: "rows" | "empty" | "missing" | "lost"; rows: readonly T[];
}>;

export function validateEvidenceDay<T>(input: EvidenceDay<T>, schema: z.ZodType<T>): EvidenceDay<T> {
  const day = DateStampSchema.parse(input.day);
  if (new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) throw new Error("Evidence day is not a UTC calendar date");
  if (!["rows", "empty", "missing", "lost"].includes(input.status)) throw new Error("Unknown evidence day status");
  const rows = input.rows.map(row => schema.parse(row));
  if ((input.status === "rows") !== (rows.length > 0)) throw new Error("Evidence day status differs from its row membership");
  return { day, status: input.status, rows };
}
