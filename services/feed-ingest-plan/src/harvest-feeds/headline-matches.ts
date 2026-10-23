/** Which configured phrases occur in the original sanitized feed headline? */
import type { ArticleLabels } from "@idhazh/common-contracts";
import type { HarvestInputs } from "./load-harvest-inputs";

// Protocol identity for the ASCII whole-word rule shared with backend/idhazh/tag.py.
const MATCHER_VERSION = "headline-ascii-whole-phrase-v1";
const ORIGIN = "sanitized-feed-headline";
function normalize(text: string): string {
  return ` ${(text.toLowerCase().match(/[a-z0-9]+/g) ?? []).join(" ")} `;
}
function matches(headline: string, terms: readonly string[]): boolean {
  return terms.some(phrase => {
    const term = normalize(phrase);
    return term !== "  " && headline.includes(term);
  });
}

export function matchHeadline(title: string | null, inputs: HarvestInputs) {
  const headline = title === null ? null : normalize(title);
  const lenses = inputs.registry.lenses?.filter(lens => lens.status !== "retired");
  const entities = inputs.watchlist?.entities.filter(entity => entity.status !== "retired");
  const matchedLenses = headline === null || lenses === undefined ? null
    : lenses.filter(lens => matches(headline, lens.keywords)).map(lens => lens.id).sort();
  const matchedEntities = headline === null || entities === undefined ? null
    : entities.filter(entity => matches(headline, entity.aliases)).map(entity => entity.id).sort();
  const weighted = (lenses ?? []).filter(lens => matchedLenses?.includes(lens.id) && lens.weight > 0)
    .sort((a, b) => b.weight - a.weight || (a.id < b.id ? 1 : a.id > b.id ? -1 : 0));
  const best = weighted[0];
  const known = matchedLenses !== null || matchedEntities !== null;
  const labels: ArticleLabels = {
    assigned_desk: null, lenses: matchedLenses, event_types: null, event_cluster_id: null,
    entities: matchedEntities, origin: known ? ORIGIN : null, matcher_version: known ? MATCHER_VERSION : null,
  };
  return {
    labels, feed_headline: title,
    best_weighted_lens: best === undefined ? null : { id: best.id, weight: best.weight },
    watchlist_match: matchedEntities === null ? null : matchedEntities.length > 0,
  };
}
