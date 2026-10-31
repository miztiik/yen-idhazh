/** Choose each permitted tier/window winner against the full selected set. */
import { SelectedArticleContentSchema } from "@idhazh/common-contracts";
import type { DropReason, ParsedFeedBatch, SelectedArticleRow } from "@idhazh/common-contracts";
import type { z } from "zod";
import type { ScreenedCandidate } from "../screen-article-candidates/triage-gates";
import type { PlanInputs } from "../load-plan-inputs";
import type { SourceHistoryEvidence } from "../read-ledger-history/read-feed-history";
import type { PublisherPublicationHistory } from "./publisher-exposure";
import type { RunContext } from "../resolve-run-context";
import {
  allocateSourceBasedQualityBucketBudgets, freshnessCutoff, resolveSourceBasedQualityBucketWindows,
} from "../article-freshness-policy";

export function curateArticles(input: {
  articles: readonly ScreenedCandidate[]; batch: ParsedFeedBatch; inputs: PlanInputs;
  health: ReadonlyMap<string, SourceHistoryEvidence>; publications: PublisherPublicationHistory;
  selectionStartedAt: string; context?: RunContext;
}) {
  const context = input.context ?? input.batch.context;
  const config = input.inputs.harvest.config;
  const policy = config.curate_articles;
  const limit = input.batch.request.article_limit ?? policy.article_limit;
  const budgets = allocateSourceBasedQualityBucketBudgets(config, limit).map(budget => ({
    ...budget, windows: resolveSourceBasedQualityBucketWindows(budget.rule),
    opened: new Set<number>(),
  }));
  for (const article of input.articles) {
    if (!budgets.some(budget => budget.rule.source_tier_id === article.candidate.source.tier)) {
      throw new Error(`curate_articles.source_based_quality_buckets: missing source tier ${article.candidate.source.tier}`);
    }
  }
  const remaining = [...input.articles];
  const chosen: ScreenedCandidate[] = [];
  const articles: z.infer<typeof SelectedArticleContentSchema>[] = [];
  const relaxations: string[] = [];
  const urls = new Set<string>();
  const counts = new Map<number, number>();
  const feedLimit = Math.ceil(limit * policy.soft_caps.max_source_share);
  const domainLimit = Math.ceil(limit * policy.soft_caps.max_website_group_share);
  const explorationSlots = Math.floor(limit * policy.exploration_slot_share);
  const sourceEvidence = input.batch.evidence;
  const website = (article: ScreenedCandidate) => sourceEvidence[article.candidate.candidate_id]?.website_group?.value;
  const tierCount = (tier: number) => counts.get(tier) ?? 0;
  function evaluate(article: ScreenedCandidate) {
    const candidate = article.candidate;
    const weights = article.policy.curate_articles.mmr_weights;
    const recency = article.freshness.recency_bonus;
    const authority = article.policy.curate_articles.source_authority_weight
      * candidate.source.weight * candidate.source.applied_tier_weight;
    const rate = input.health.get(candidate.feed_id)?.article_pass_rate ?? null;
    const adjustment = !policy.source_reliability_penalty_enabled ? 0 : rate === null ? null
      : -authority * (1 - Math.max(input.inputs.clock_config.collect.reliability_floor, rate));
    const group = website(article);
    const publisher = candidate.source.publisher_id;
    const exposure = publisher === null ? null : Math.min(1,
      ((input.publications.availability === "available" ? input.publications.counts.get(publisher) ?? 0 : 0)
        + chosen.filter(previous => previous.candidate.source.publisher_id === publisher).length) / limit);
    const adjustments: SelectedArticleRow["ratings"]["adjustments"] = [
      { term: "article_pass_rate", value: adjustment },
      { term: input.publications.availability === "available" ? "publisher_exposure" : "publisher_exposure_current_run",
        value: exposure === null ? null : -weights.lambda_source * exposure },
      { term: "website_group", value: group === undefined ? null : -weights.lambda_website_group * (chosen.length === 0 ? 0
        : chosen.filter(previous => website(previous) === group).length / chosen.length) },
    ].map(term => ({ ...term, value: term.value === 0 ? 0 : term.value }));
    const feeds = new Set(chosen.map(previous => previous.candidate.feed_id));
    const blocked: string[] = [];
    if (!relaxations.includes("distinct_sources")
      && feeds.size < Math.min(policy.soft_caps.min_distinct_sources, limit) && feeds.has(candidate.feed_id)) blocked.push("distinct_sources");
    if (!relaxations.includes("source_share")
      && chosen.filter(previous => previous.candidate.feed_id === candidate.feed_id).length >= feedLimit) blocked.push("source_share");
    if (group !== undefined && chosen.filter(previous => website(previous) === group).length >= domainLimit) blocked.push("website_group_share");
    return { article, recency, authority, adjustments, blocked,
      marginal: recency + authority + adjustments.reduce((sum, term) => sum + (term.value ?? 0), 0) };
  }
  type Evaluation = ReturnType<typeof evaluate>;
  function phase(older: boolean, buffer: boolean): { winner: Evaluation; hours: number; exploring: boolean } | "relaxed" | undefined {
    const blocked: Evaluation[] = [];
    for (const budget of budgets) {
      const count = tierCount(budget.rule.source_tier_id);
      if (count >= (buffer ? budget.ceiling : budget.target)) continue;
      const steps = older ? budget.windows.steps.slice(1) : budget.windows.steps.slice(0, 1);
      for (const hours of steps) {
        const pool = remaining.filter(article => article.candidate.source.tier === budget.rule.source_tier_id
          && !urls.has(article.candidate.url_key)
          && (article.freshness.age_hours === null ? !older : article.freshness.age_hours <= hours
            && (!older || article.freshness.age_hours > budget.windows.steps[0]!)));
        if (older) budget.opened.add(hours);
        const evaluated = pool.map(evaluate);
        blocked.push(...evaluated);
        const viable = evaluated.filter(value => value.blocked.length === 0);
        const feeds = new Set(chosen.map(previous => previous.candidate.feed_id));
        const exploration = chosen.length >= limit - explorationSlots
          ? viable.filter(value => !feeds.has(value.article.candidate.feed_id)) : [];
        const available = exploration.length ? exploration : viable;
        available.sort((a, b) => b.marginal - a.marginal
          || a.article.candidate.candidate_id.localeCompare(b.article.candidate.candidate_id));
        if (available[0] !== undefined) return { winner: available[0], hours, exploring: exploration.length > 0 };
      }
    }
    const next = policy.soft_caps.relaxation_order.find(name =>
      !relaxations.includes(name) && blocked.some(value => value.blocked.includes(name)));
    if (next !== undefined) {
      relaxations.push(next);
      return "relaxed";
    }
    return undefined;
  }
  while (chosen.length < limit) {
    const choice = phase(false, false) ?? phase(false, true) ?? phase(true, false);
    if (choice === undefined) break;
    if (choice === "relaxed") continue;
    const { winner, hours, exploring } = choice;
    const { candidate, freshness } = winner.article;
    articles.push(SelectedArticleContentSchema.parse({
      run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      url_key: candidate.url_key, feed_id: candidate.feed_id, publisher_id: candidate.source.publisher_id,
      canonical_url: candidate.canonical_url, title: candidate.title, categories: candidate.categories,
      article_text: candidate.article_text, author: candidate.author,
      published_at: freshness.timing_source === "published_at" ? candidate.published_at : input.selectionStartedAt,
      published_at_source: freshness.timing_source === "published_at" ? "source" : "selection",
      tier: candidate.source.tier, weight: candidate.source.weight, applied_tier_weight: candidate.source.applied_tier_weight,
      editorial_rank: articles.length + 1, estimated_work: sourceEvidence[candidate.candidate_id]?.estimated_work ?? candidate.word_count,
      worker_assignment: null, feed_limit: feedLimit, exploration_slot: exploring, cap_relaxations: [...relaxations],
      timing_at: freshness.timing_at, timing_basis: freshness.timing_source === "unknown" ? "unavailable" : freshness.timing_source,
      age_hours: freshness.age_hours,
      freshness_cutoff_at: freshness.age_hours === null ? null : freshnessCutoff(input.batch.context.now, hours),
      ratings: { base_article_score: winner.recency + winner.authority, marginal_score: winner.marginal,
        adjustments: winner.adjustments, recency_score: winner.recency, feed_authority_score: winner.authority },
    }));
    chosen.push(winner.article);
    urls.add(candidate.url_key);
    counts.set(candidate.source.tier, tierCount(candidate.source.tier) + 1);
    remaining.splice(remaining.indexOf(winner.article), 1);
  }
  const losses = remaining.map(article => {
    const budget = budgets.find(budget => budget.rule.source_tier_id === article.candidate.source.tier)!;
    const age = article.freshness.age_hours;
    const step = age === null ? budget.windows.steps[0] : budget.windows.steps.find(hours => age <= hours);
    if (step === undefined) throw new Error("Article selection requires candidates inside their screened tier age envelope");
    const older = step !== undefined && step !== budget.windows.steps[0];
    let reason: DropReason;
    let cutoff: string | null = null;
    if (urls.has(article.candidate.url_key)) reason = "REJECTED_DUPLICATE_CANONICAL_CARRIER";
    else if (older && !budget.opened.has(step) && tierCount(budget.rule.source_tier_id) >= budget.target) reason = "REJECTED_LADDER_WINDOW_NOT_ACTIVATED";
    else if (older && tierCount(budget.rule.source_tier_id) >= budget.target) reason = "REJECTED_SLACK_DEFICIT_FULFILLED";
    else if (chosen.length >= limit) reason = "REJECTED_GLOBAL_CAPACITY_REACHED";
    else {
      const blocked = evaluate(article).blocked;
      reason = blocked.includes("distinct_sources") ? "REJECTED_DISTINCT_SOURCE_REQUIREMENT_UNMET"
        : blocked.includes("source_share") ? "REJECTED_SOURCE_SHARE_LIMIT_REACHED"
        : blocked.includes("website_group_share") ? "REJECTED_DOMAIN_SHARE_LIMIT_REACHED"
        : "REJECTED_TIER_BUFFER_CEILING_REACHED";
    }
    if (!older && age !== null) cutoff = freshnessCutoff(input.batch.context.now, budget.windows.steps[0]!);
    else if (older && budget.opened.has(step!)) cutoff = freshnessCutoff(input.batch.context.now, step!);
    return { article, reason, freshness_cutoff_at: cutoff };
  });
  return { articles, losses };
}
