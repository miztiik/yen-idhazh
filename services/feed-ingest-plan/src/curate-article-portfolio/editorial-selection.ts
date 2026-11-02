/** Prepare cached numerical scores and project the sole selector's chosen identities. */
import { NumericalSelectionInputSchema, SelectedArticleContentSchema } from "@idhazh/common-contracts";
import type { ParsedFeedBatch, ScreenedCandidate } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { SourceHistoryEvidence } from "../read-ledger-history/read-feed-history";
import type { RunContext } from "../resolve-run-context";
import { freshnessCutoff } from "../article-freshness-policy";
import { websiteGroup } from "../website-group";
import { selectDiverseArticles } from "./select-diverse-articles";

export function curateArticles(input: {
  articles: readonly ScreenedCandidate[]; batch: ParsedFeedBatch; inputs: PlanInputs;
  health: ReadonlyMap<string, SourceHistoryEvidence>;
  selectionStartedAt: string; context?: RunContext;
}) {
  const context = input.context ?? input.batch.context;
  const policy = input.inputs.harvest.config.curate_articles;
  const limit = input.batch.request.article_limit ?? policy.article_limit;
  const prepared = new Map(input.articles.map(article => {
    const candidate = article.candidate;
    const authority = article.policy.curate_articles.source_authority_weight * candidate.source.weight;
    const recency = article.freshness.recency_bonus;
    const passRate = input.health.get(candidate.feed_id)?.article_pass_rate ?? null;
    const passAdjustment = !policy.source_reliability_penalty_enabled || passRate === null ? 0
      : -authority * (1 - Math.max(input.inputs.clock_config.collect.reliability_floor, passRate));
    const substance = article.freshness.substance_score;
    const base = ((authority + recency) + passAdjustment) + substance;
    return [candidate.candidate_id, { article, authority, recency, passAdjustment, substance,
      record: NumericalSelectionInputSchema.parse({
        candidate_id: candidate.candidate_id, url_key: candidate.url_key, feed_id: candidate.feed_id,
        website_group: websiteGroup(candidate.canonical_url, policy.website_grouping.include_private_suffixes),
        base_score: base,
      }),
    }] as const;
  }));
  if (prepared.size !== input.articles.length) throw new Error("Selection requires distinct candidate identities");
  const numerical = Array.from(prepared.values(), value => value.record);
  const selected = selectDiverseArticles(numerical, limit, policy.diversity);
  const cutoff = freshnessCutoff(input.batch.context.now, policy.global_age_ceiling_hours);
  const articles = selected.chosen.map((choice, index) => {
    const { article, authority, recency, passAdjustment, substance } = prepared.get(choice.record.candidate_id)!;
    const { candidate, freshness } = article;
    return SelectedArticleContentSchema.parse({
      run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      url_key: candidate.url_key, feed_id: candidate.feed_id, publisher_id: candidate.source.publisher_id,
      canonical_url: candidate.canonical_url, title: candidate.title, categories: candidate.categories,
      article_text: candidate.article_text, word_count: candidate.word_count,
      substance_word_count: freshness.substance_word_count, author: candidate.author,
      published_at: freshness.timing_source === "published_at" ? candidate.published_at : input.selectionStartedAt,
      published_at_source: freshness.timing_source === "published_at" ? "source" : "selection",
      weight: candidate.source.weight, editorial_rank: index + 1,
      estimated_work: input.batch.evidence[candidate.candidate_id]?.estimated_work ?? candidate.word_count,
      worker_assignment: null, timing_at: freshness.timing_at,
      timing_basis: freshness.timing_source === "unknown" ? "unavailable" : freshness.timing_source,
      age_hours: freshness.age_hours, freshness_cutoff_at: cutoff,
      ratings: {
        base_article_score: choice.record.base_score, marginal_score: choice.score,
        recency_score: recency, feed_authority_score: authority,
        adjustments: [
          { term: "article_pass_rate", value: passAdjustment === 0 ? 0 : passAdjustment },
          { term: "substance_quality_score", value: substance },
          { term: "domain_diversity_penalty", value: choice.domain_diversity_penalty === 0 ? 0 : choice.domain_diversity_penalty },
          { term: "feed_diversity_penalty", value: choice.feed_diversity_penalty === 0 ? 0 : choice.feed_diversity_penalty },
          { term: "novelty_bonus", value: choice.novelty_bonus },
        ],
      },
    });
  });
  const losses = selected.losses.map(loss => ({
    article: prepared.get(loss.record.candidate_id)!.article,
    reason: loss.reason, freshness_cutoff_at: cutoff,
  }));
  return { articles, losses };
}
