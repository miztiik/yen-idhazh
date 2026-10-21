/** Which published articles and leads belong to a recorded run? */
import { deriveUrlKey, RunIdSchema, SourceRunRecordSchema } from "@idhazh/common-contracts";
import type { SourceRunRecord } from "@idhazh/common-contracts";
import {
  DigestPublicationSchema, ItemHealthPublicationSchema, PublishedRowSchema, validateEvidenceDay,
} from "./publication-evidence";
import type { DigestPublication, EvidenceDay, ItemHealthPublication, PublishedRow } from "./publication-evidence";
import { uniquePublishedArticles, uniqueRecorded } from "./fingerprint-dedup";
import type { PublishedArticle } from "./fingerprint-dedup";

export type PublicationInput = Readonly<{
  run_id: string;
  published: EvidenceDay<PublishedRow>;
  health: EvidenceDay<ItemHealthPublication>;
  digest: DigestPublication | null;
}>;
export type PublicationOutcomes = Readonly<{
  day: string; run_id: string; availability: "available" | "unavailable";
  unavailable_reason: "missing_publication" | null;
  articles: readonly PublishedArticle[]; unattributed_item_ids: readonly string[];
}>;

export function reconcilePublication(input: PublicationInput): PublicationOutcomes {
  const run = RunIdSchema.parse(input.run_id);
  const day = run.slice(0, 10);
  const published = validateEvidenceDay(input.published, PublishedRowSchema);
  const health = validateEvidenceDay(input.health, ItemHealthPublicationSchema);
  if (published.day !== day || health.day !== day) throw new Error("Publication inputs must name the run's UTC day");
  if (published.rows.some(row => row.published_on !== day) || health.rows.some(row => row.date !== day || row.run_id.slice(0, 10) !== day)) {
    throw new Error("Publication evidence contains another UTC day");
  }
  const result = (articles: readonly PublishedArticle[], missing: readonly string[], available: boolean): PublicationOutcomes => ({
    day, run_id: run, availability: available ? "available" : "unavailable",
    unavailable_reason: available ? null : "missing_publication",
    articles, unattributed_item_ids: missing,
  });
  if (published.status === "missing" || published.status === "lost" || input.digest === null) return result([], [], false);
  const digest = DigestPublicationSchema.parse(input.digest);
  if (digest.date !== day) throw new Error("Digest belongs to another UTC day");
  const recordedRun = digest.runs.find(held => held.run_id === run);
  const healthRows = uniqueRecorded(health.rows, row => JSON.stringify([row.run_id, row.item_id, row.url_key]),
    (a, b) => a.source_id === b.source_id && a.stage === b.stage && a.outcome === b.outcome);
  const rows = uniqueRecorded(published.rows, row => row.url_key,
    (a, b) => a.item_id === b.item_id && a.published_on === b.published_on);
  const articles: PublishedArticle[] = [];
  const missing: string[] = [];
  for (const row of rows) {
    const item = digest.items.find(item => item.item_id === row.item_id);
    if (item === undefined) { missing.push(row.item_id); continue; }
    if (deriveUrlKey(item.source_url) !== row.url_key) throw new Error("Published item and digest URL identities disagree");
    if (healthRows.some(held => held.item_id === item.item_id && held.url_key !== row.url_key)) {
      throw new Error("Published health and digest URL identities disagree");
    }
    const reference = digest.runs.find(held => held.n === item.introduced_by_run)!;
    const candidates = healthRows.filter(held => held.item_id === item.item_id && held.url_key === row.url_key
      && held.stage === "publish" && held.outcome === "ok");
    if (candidates.some(held => held.source_id !== item.source_id)) throw new Error("Published health and digest source identities disagree");
    const healthRuns = new Set(candidates.map(held => held.run_id));
    if (reference.run_id !== null && [...healthRuns].some(held => held !== reference.run_id)) {
      throw new Error("Published health and digest run identities disagree");
    }
    if (healthRuns.size > 1) throw new Error("Published item has ambiguous recorded run identities");
    const owner = reference.run_id ?? candidates[0]?.run_id;
    if (owner === undefined) { missing.push(row.item_id); continue; }
    if (owner !== run) continue;
    articles.push({
      date: day, run_id: owner, item_id: row.item_id, url_key: row.url_key,
      source_id: item.source_id, source_kind: item.source_kind ?? null,
      lead: digest.leads.some(lead => lead.item_id === row.item_id),
    });
  }
  // A named run with no additions is evidence of zero, not a missing publication.
  const members = recordedRun === undefined ? [] : digest.items.filter(item => item.introduced_by_run === recordedRun.n);
  for (const item of members) {
    if (!articles.some(article => article.item_id === item.item_id) && !missing.includes(item.item_id)) missing.push(item.item_id);
  }
  return result(uniquePublishedArticles(articles), missing, missing.length === 0
    && (recordedRun !== undefined || articles.length > 0));
}

export function completePublicationObservations(
  sources: readonly SourceRunRecord[], outcomes: PublicationOutcomes, observedAt: string,
): SourceRunRecord[] {
  if (outcomes.availability !== "available") throw new Error("Missing publication evidence cannot complete source observations");
  const parsed = sources.map(row => SourceRunRecordSchema.parse(row));
  if (new Set(parsed.map(row => row.source_id)).size !== parsed.length) throw new Error("Settle source retries before completing publication observations");
  for (const row of parsed) {
    if (row.run_id !== outcomes.run_id || row.date !== outcomes.day) throw new Error("Source observation belongs to another run");
    if (row.expected_source_count !== parsed.length || row.attempt !== parsed[0]!.attempt) {
      throw new Error("Publication observations require one complete settled source attempt");
    }
  }
  if (outcomes.articles.some(article => !parsed.some(row => row.source_id === article.source_id))) {
    throw new Error("Published source is absent from the recorded source snapshot");
  }
  return parsed.map(row => SourceRunRecordSchema.parse({
    ...row, observation_phase: "publication_complete", observed_at: observedAt,
    published_count: outcomes.articles.filter(article => article.source_id === row.source_id).length,
    lead_count: outcomes.articles.filter(article => article.source_id === row.source_id && article.lead).length,
  }));
}
