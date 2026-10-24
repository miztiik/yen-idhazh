/** How much confirmed publisher exposure has this UTC-day choice already received? */
import { CountSchema, DateStampSchema, PublisherIdSchema, PublisherExposurePenaltySchema } from "@idhazh/common-contracts";
import type { PortfolioArticle } from "./portfolio-input";

export type PublisherPublicationHistory = Readonly<{
  day: string;
  availability: "available" | "unavailable";
  counts: ReadonlyMap<string, number>;
}>;

export function validatePublisherHistory(history: PublisherPublicationHistory, observedAt: string): void {
  DateStampSchema.parse(history.day);
  if (history.day !== observedAt.slice(0, 10)) throw new Error("Publisher history must name the selection UTC day");
  for (const [publisher, count] of history.counts) {
    PublisherIdSchema.parse(publisher);
    CountSchema.parse(count);
  }
}

export function measurePublisherExposure(
  article: PortfolioArticle, selected: readonly PortfolioArticle[], plannedSlots: number,
  history: PublisherPublicationHistory,
) {
  const publisher = article.candidate.source.publisher_id;
  const published = publisher !== null && history.availability === "available" ? history.counts.get(publisher) ?? 0 : null;
  const selectedCount = publisher === null ? 0
    : selected.filter(prior => prior.candidate.source.publisher_id === publisher).length;
  const exposure = publisher === null ? null : Math.min(1, ((published ?? 0) + selectedCount) / plannedSlots);
  const coefficient = article.policy.curate.mmr_weights.lambda_source;
  return PublisherExposurePenaltySchema.parse({
    day: history.day, publisher_id: publisher, history_status: history.availability,
    published_today: published, selected_so_far: selectedCount, planned_slots: plannedSlots,
    coefficient, exposure, value: exposure === null ? null : coefficient * exposure,
  });
}
