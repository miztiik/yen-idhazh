/** Screen the complete parsed input and retain only chosen metadata, text and grouped losses. */
import { FeedHealthStateRowSchema } from "@idhazh/common-contracts";
import type { ParsedFeedBatch, PlannerRejectionCount } from "@idhazh/common-contracts";
import type { PlanInputs } from "./load-plan-inputs";
import { screenArticleCandidates } from "./screen-article-candidates/triage-gates";
import { curateArticles } from "./curate-article-portfolio/editorial-selection";
import { resolvePlanRequest } from "./api/plan-request";
import { resolvePlanningInputs } from "./resolve-planning-inputs";
import { readPublisherPublication } from "./read-ledger-history/read-publisher-publication";
import { summarizeHealth, captureHealthRows } from "./read-ledger-history/health-summary";
import type { FeedHistory } from "./read-ledger-history/read-feed-history";
import { readExclusionEvidence } from "./read-ledger-history/read-exclusion-evidence";

export async function selectArticles(batch: ParsedFeedBatch, inputs: PlanInputs, selectionStartedAt: string,
  currentHealth?: Pick<FeedHistory, "sources" | "request_report">) {
  const request = resolvePlanRequest(batch.request, inputs.harvest.config);
  const planning = resolvePlanningInputs(inputs, request);
  const healthDays = [...batch.history_days];
  for (const row of batch.work_rows) if (!healthDays.some(day => day.day === row.date)) {
    healthDays.push({ day: row.date, complete: false });
  }
  const health = currentHealth ?? summarizeHealth({
    rows: [...batch.history_rows, ...batch.work_rows], days: healthDays,
    sources: planning.sources.map(source => sourceSnapshot(inputs.harvest, source)),
    now: selectionStartedAt, policy: inputs.clock_config.collect,
    ...inputs.harvest.config.feedback,
  });
  const exclusions = await readExclusionEvidence({
    root: inputs.root, now: selectionStartedAt, publishedWindowDays: inputs.clock_config.collect.published_window_days,
    settledFailureCodes: inputs.clock_config.collect.settled_failure_codes,
    publishedRegistration: inputs.registrations.published, itemHealthRegistration: inputs.registrations.item_health,
    publishedDays: inputs.settings.inputs.published_days.filter(day => day.day <= selectionStartedAt.slice(0, 10)),
    settledFailureDays: inputs.settings.inputs.settled_failure_days.filter(day => day.day === selectionStartedAt.slice(0, 10)),
    concurrency: inputs.harvest.config.harvest.concurrency,
  });
  const screening = await screenArticleCandidates({
    candidates: batch.candidates, observations: batch.observations, seen: batch.seen, planning,
    clock_config: inputs.clock_config, run: {
      now: batch.context.now, run_id: batch.context.run_id, correlation_id: batch.context.correlation_id,
      overrides: request.freshness_hours === undefined ? {} : { freshness_hours: request.freshness_hours },
    },
    exclusions: {
      published_window_days: inputs.clock_config.collect.published_window_days,
      published_on: Object.fromEntries(exclusions.published_on), settled_failure_codes: Object.fromEntries(exclusions.settled_failure_codes),
    },
  });
  const publications = await readPublisherPublication({
    root: inputs.root, day: selectionStartedAt.slice(0, 10), published: inputs.registrations.published,
    item_health: inputs.registrations.item_health, selections: inputs.registrations.selected_articles,
    published_days: inputs.settings.inputs.published_days, health_days: inputs.settings.inputs.settled_failure_days,
  });
  const curation = curateArticles({ articles: screening.admitted, batch, inputs, health: health.sources, publications });
  const losses: PlannerRejectionCount[] = [...batch.exclusions];
  for (const rejection of screening.rejections) losses.push({
    feed_id: rejection.source_id, subject: "article", stage: "screen-article-candidates",
    reason_code: rejection.drop_reason, attribution: null, count: 1,
  });
  for (const loss of curation.losses) losses.push({
    feed_id: loss.article.candidate.source_id, subject: "article", stage: "curate-article-portfolio",
    reason_code: loss.reason, attribution: null, count: 1,
  });
  const grouped = new Map<string, PlannerRejectionCount>();
  for (const exclusion of losses) {
    const { count, ...identity } = exclusion;
    const key = JSON.stringify(identity);
    const previous = grouped.get(key);
    if (previous === undefined) grouped.set(key, { ...exclusion });
    else previous.count += count;
  }
  const healthRows = captureHealthRows(batch.work_rows, health.sources);
  const admitted = new Set(screening.admitted.map(article => article.candidate.candidate_id));
  for (const candidate of batch.candidates) {
    let row = healthRows.find(row => row.feed_id === candidate.source_id && row.date === selectionStartedAt.slice(0, 10));
    if (row === undefined) {
      const prior = batch.work_rows.find(row => row.feed_id === candidate.source_id);
      if (prior === undefined) throw new Error("Selection candidate lacks this run's actual feed work");
      row = FeedHealthStateRowSchema.parse({
        ...prior, date: selectionStartedAt.slice(0, 10), checked_at: null, outcome: null, items: null,
        feed_reads: 0, productive_reads: 0, failed_reads: 0,
        feed_requests: 0, article_requests: 0, robots_requests: 0, article_candidates: 0, articles_selected: 0,
        rejection_counts: [], counts_complete: true, permission: "unknown", status: null, last_failure_code: null,
      });
      healthRows.push(row);
    }
    if (admitted.has(candidate.candidate_id) && row.article_candidates !== null) row.article_candidates++;
  }
  for (const article of curation.articles) {
    const row = healthRows.find(row => row.feed_id === article.feed_id && row.date === selectionStartedAt.slice(0, 10))!;
    if (row.articles_selected !== null) row.articles_selected++;
  }
  for (const row of healthRows) {
    if (row.date !== selectionStartedAt.slice(0, 10)) continue;
    const losses = [...grouped.values()].filter(loss => loss.feed_id === row.feed_id && loss.stage !== "harvest-feeds");
    row.rejection_counts.push(...losses.map(({ feed_id: _feed, ...loss }) => loss));
  }
  return { articles: curation.articles, health_rows: healthRows, exclusions: [...grouped.values()], request_report: health.request_report };
}
import { sourceSnapshot } from "./harvest-feeds/load-harvest-inputs";
