/** Choose articles using recorded time, configured authority and measured numeric set controls. */
import { SelectedArticleContentSchema } from "@idhazh/common-contracts";
import type { ParsedFeedBatch, SelectedArticleRow } from "@idhazh/common-contracts";
import type { ScreenedCandidate } from "../screen-article-candidates/triage-gates";
import type { PlanInputs } from "../load-plan-inputs";
import type { SourceHistoryEvidence } from "../read-ledger-history/read-feed-history";
import type { PublisherPublicationHistory } from "./publisher-exposure";
import type { RunContext } from "../resolve-run-context";

export function curateArticles(input: {
  articles: readonly ScreenedCandidate[]; batch: ParsedFeedBatch; inputs: PlanInputs;
  health: ReadonlyMap<string, SourceHistoryEvidence>; publications: PublisherPublicationHistory;
  selectionStartedAt: string; context?: RunContext;
}) {
  const context = input.context ?? input.batch.context;
  const config = input.inputs.harvest.config.curate_articles;
  const sourceEvidence = input.batch.evidence;
  const score = (article: ScreenedCandidate) => {
    const recency = article.freshness.recency_bonus;
    const authority = article.policy.curate_articles.source_authority_weight
      * article.candidate.source.weight * article.candidate.source.applied_tier_weight;
    const reliability = input.health.get(article.candidate.source_id)?.reliability;
    const adjustment = reliability?.production_factor == null ? null : config.source_reliability_penalty_enabled
      ? -authority * (1 - reliability.production_factor) : 0;
    return { recency, authority, adjustment, base: recency + authority, priority: recency + authority + (adjustment ?? 0) };
  };
  const compare = (a: ScreenedCandidate, b: ScreenedCandidate) => score(b).priority - score(a).priority
    || a.candidate.candidate_id.localeCompare(b.candidate.candidate_id);
  const losses: { article: ScreenedCandidate; reason: string }[] = [];
  const urls = new Set<string>();
  const counts = new Map<string, number>();
  const allowances = new Map<string, { value: number; reasons: string[] }>();
  for (const article of input.articles) {
    const prior = allowances.get(article.candidate.source_id);
    const value = article.policy.curate_articles.base_source_allowance;
    if (prior === undefined || value > prior.value) allowances.set(article.candidate.source_id, { value, reasons: [] });
  }
  const remaining: ScreenedCandidate[] = [];
  for (const article of [...input.articles].sort(compare)) {
    const feed = article.candidate.source_id;
    if (urls.has(article.candidate.url_key)) { losses.push({ article, reason: "DUPLICATE_URL" }); continue; }
    urls.add(article.candidate.url_key);
    const used = counts.get(feed) ?? 0;
    if (used >= allowances.get(feed)!.value) { losses.push({ article, reason: "SOURCE_QUOTA_EXCEEDED" }); continue; }
    counts.set(feed, used + 1);
    remaining.push(article);
  }
  const target = Math.min(input.batch.request.article_limit ?? config.article_limit ?? remaining.length, remaining.length);
  const chosen: ScreenedCandidate[] = [];
  const articles: z.infer<typeof SelectedArticleContentSchema>[] = [];
  const relaxations: string[] = [];
  const sourceMaximum = Math.ceil(target * config.soft_caps.max_source_share);
  const websiteGroupMaximum = Math.ceil(target * config.soft_caps.max_website_group_share);
  const explorationSlots = Math.floor(target * config.exploration_slot_share);
  while (chosen.length < target && remaining.length > 0) {
    const feeds = new Set(chosen.map(article => article.candidate.source_id));
    const exploring = chosen.length >= target - explorationSlots && remaining.some(article => !feeds.has(article.candidate.source_id));
    const evaluated = remaining.map(article => {
      const candidate = article.candidate;
      const weights = article.policy.curate_articles.mmr_weights;
      const websiteGroup = sourceEvidence[candidate.candidate_id]?.website_group?.value;
      const publisher = candidate.source.publisher_id;
      const exposure = publisher === null ? null : Math.min(1,
        ((input.publications.availability === "available" ? input.publications.counts.get(publisher) ?? 0 : 0)
          + chosen.filter(previous => previous.candidate.source.publisher_id === publisher).length) / target);
      const measured = score(article);
      const adjustments: SelectedArticleRow["ratings"]["adjustments"] = [
        { term: "feed_reliability", value: measured.adjustment },
        { term: input.publications.availability === "available" ? "publisher_exposure" : "publisher_exposure_current_run",
          value: exposure === null ? null : -weights.lambda_source * exposure },
        { term: "website_group", value: websiteGroup === undefined ? null : -weights.lambda_website_group * (chosen.length === 0 ? 0
          : chosen.filter(previous => sourceEvidence[previous.candidate.candidate_id]?.website_group?.value === websiteGroup).length / chosen.length) },
      ].map(adjustment => ({ ...adjustment, value: adjustment.value === 0 ? 0 : adjustment.value }));
      const blocked: string[] = [];
      if (!relaxations.includes("distinct_sources") && feeds.size < Math.min(config.soft_caps.min_distinct_sources, target)
        && feeds.has(candidate.source_id)) blocked.push("distinct_sources");
      if (!relaxations.includes("source_share")
        && chosen.filter(previous => previous.candidate.source_id === candidate.source_id).length >= sourceMaximum) blocked.push("source_share");
      if (websiteGroup !== undefined && chosen.filter(previous =>
        sourceEvidence[previous.candidate.candidate_id]?.website_group?.value === websiteGroup).length >= websiteGroupMaximum) blocked.push("website_group_share");
      return { article, adjustments, measured, blocked, marginal: measured.base
        + adjustments.reduce((total, adjustment) => total + (adjustment.value ?? 0), 0) };
    });
    const viable = evaluated.filter(value => value.blocked.length === 0);
    const exploration = exploring ? viable.filter(value => !feeds.has(value.article.candidate.source_id)) : [];
    const available = exploration.length ? exploration : viable;
    available.sort((a, b) => b.marginal - a.marginal || compare(a.article, b.article));
    const winner = available[0];
    if (winner === undefined) {
      const next = config.soft_caps.relaxation_order.find(limit => !relaxations.includes(limit)
        && evaluated.some(value => value.blocked.includes(limit)));
      if (next === undefined) break;
      relaxations.push(next);
      continue;
    }
    const { candidate, freshness } = winner.article;
    const allowance = allowances.get(candidate.source_id)!;
    articles.push(SelectedArticleContentSchema.parse({
      run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      url_key: candidate.url_key, feed_id: candidate.source_id, publisher_id: candidate.source.publisher_id,
      canonical_url: candidate.canonical_url, title: candidate.title, categories: candidate.categories,
      article_text: candidate.article_text, author: candidate.author,
      published_at: freshness.timing_source === "published_at" ? candidate.published_at : input.selectionStartedAt,
      published_at_source: freshness.timing_source === "published_at" ? "source" : "selection",
      tier: candidate.source.tier, weight: candidate.source.weight, applied_tier_weight: candidate.source.applied_tier_weight,
      editorial_rank: articles.length + 1, estimated_work: sourceEvidence[candidate.candidate_id]?.estimated_work ?? candidate.word_count,
      worker_assignment: null, feed_allowance: allowance.value, exploration_slot: exploration.length > 0,
      cap_relaxations: [...relaxations], allowance_reasons: allowance.reasons,
      timing_at: freshness.timing_at, timing_basis: freshness.timing_source === "unknown" ? "unavailable" : freshness.timing_source,
      age_hours: freshness.age_hours, ratings: {
        base_article_score: winner.measured.base, marginal_score: winner.marginal, adjustments: winner.adjustments,
        recency_score: winner.measured.recency, feed_authority_score: winner.measured.authority,
      },
    }));
    chosen.push(winner.article);
    remaining.splice(remaining.indexOf(winner.article), 1);
  }
  losses.push(...remaining.map(article => ({ article, reason: "PORTFOLIO_CUTOFF" })));
  return { articles, losses };
}
import type { z } from "zod";
