/** Summarize completed selection from its validated metadata without changing chosen articles. */
import { SelectedArticleMetadataSchema } from "@idhazh/common-contracts";
import type { PlanRunRow, SelectedArticleMetadata } from "@idhazh/common-contracts";
import { websiteGroup } from "./website-group";

export function summarizeSelectionMetrics(
  articles: readonly SelectedArticleMetadata[], includePrivateSuffixes: boolean,
): NonNullable<PlanRunRow["selection_metrics"]> {
  const websites = new Set<string>();
  const feeds = new Set<string>();
  let substance = 0;
  for (const article of articles) {
    const metadata = SelectedArticleMetadataSchema.strip().parse(article);
    websites.add(websiteGroup(metadata.canonical_url, includePrivateSuffixes));
    feeds.add(metadata.feed_id);
    const score = metadata.ratings.adjustments.find(adjustment => adjustment.term === "substance_quality_score")!;
    substance += score.value;
    if (!Number.isFinite(substance)) throw new Error("Selected substance score sum exceeds the numeric range");
  }
  return {
    selected_website_groups: websites.size, selected_feeds: feeds.size,
    mean_substance_score: articles.length === 0 ? null : substance / articles.length,
  };
}
