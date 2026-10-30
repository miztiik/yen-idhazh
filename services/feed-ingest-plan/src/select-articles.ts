/** Screen the complete parsed input and retain only chosen metadata, text and grouped losses. */
import { FeedHealthStateRowSchema, RejectedArticleRowSchema } from "@idhazh/common-contracts";
import type { ParsedFeedBatch, PlannerRejectionCount } from "@idhazh/common-contracts";
import type { PlanInputs } from "./load-plan-inputs";
import { screenArticleCandidates } from "./screen-article-candidates/triage-gates";
import { curateArticles } from "./curate-article-portfolio/editorial-selection";
import { resolvePlanRequest } from "./api/plan-request";
import { resolvePlanningInputs } from "./resolve-planning-inputs";
import { readPublisherPublication } from "./read-ledger-history/read-publisher-publication";
import { captureHealthRows } from "./read-ledger-history/health-summary";
import { prepareFeedHealthState } from "./api/feed-health-state-operation";
import type { RunContext } from "./resolve-run-context";
import { inputEndpointKey } from "./read-ledger-history/health-summary";
import { readExclusionEvidence } from "./read-ledger-history/read-exclusion-evidence";
import { freshnessCutoff } from "./article-freshness-policy";
import { readArticleIdentityHistory } from "./read-ledger-history/read-article-identity-history";

export async function selectArticles(batch: ParsedFeedBatch, inputs: PlanInputs, selectionStartedAt: string,
  currentHealth?: Pick<Awaited<ReturnType<typeof prepareFeedHealthState>>, "sources" | "request_report">, context: RunContext = batch.context) {
  const request = resolvePlanRequest(batch.request, inputs.harvest.config);
  const planning = resolvePlanningInputs(inputs, request);
  const health = currentHealth ?? await prepareFeedHealthState(inputs, selectionStartedAt,
    { context: batch.context, rows: batch.work_rows });
  const exclusions = await readExclusionEvidence({
    root: inputs.root, now: selectionStartedAt, publishedWindowDays: inputs.clock_config.collect.published_window_days,
    settledFailureCodes: inputs.clock_config.collect.settled_failure_codes,
    publishedRegistration: inputs.registrations.published, itemHealthRegistration: inputs.registrations.item_health,
    publishedDays: inputs.settings.inputs.published_days.filter(day => day.day <= selectionStartedAt.slice(0, 10)),
    settledFailureDays: inputs.settings.inputs.settled_failure_days.filter(day => day.day === selectionStartedAt.slice(0, 10)),
    concurrency: inputs.harvest.config.harvest.concurrency,
  });
  const discoveryRows = batch.discovered.availability === "available" ? batch.discovered.rows : [];
  const identities = await readArticleIdentityHistory(inputs, selectionStartedAt, discoveryRows, exclusions.published_rows);
  for (const offer of batch.offers) if (offer.entry.link !== null) identities.remember(offer.entry.link);
  for (const candidate of batch.candidates) identities.remember(candidate.canonical_url, candidate.url_key);
  const publishedOn = new Map(exclusions.published_on);
  const failureCodes = new Map(exclusions.settled_failure_codes);
  const publishedKeys: Record<string, string> = {};
  const failureKeys: Record<string, string> = {};
  for (const candidate of batch.candidates) {
    const keys = identities.keysFor(candidate.url_key);
    const published = keys.flatMap(key => {
      const value = exclusions.published_on.get(key);
      return value === undefined ? [] : [{ key, value }];
    }).sort((a, b) => a.value.localeCompare(b.value) || a.key.localeCompare(b.key))[0];
    if (published !== undefined) {
      publishedOn.set(candidate.url_key, published.value);
      publishedKeys[candidate.url_key] = published.key;
    }
    const failure = keys.flatMap(key => {
      const value = exclusions.settled_failure_codes.get(key);
      return value === undefined ? [] : [{ key, value }];
    }).sort((a, b) => a.value.localeCompare(b.value) || a.key.localeCompare(b.key))[0];
    if (failure !== undefined) {
      failureCodes.set(candidate.url_key, failure.value);
      failureKeys[candidate.url_key] = failure.key;
    }
  }
  const screening = await screenArticleCandidates({
    candidates: batch.candidates, observations: batch.observations,
    discovered: batch.discovered.availability === "available"
      ? { availability: "available", rows: identities.discoveries(discoveryRows) } : batch.discovered, planning,
    clock_config: inputs.clock_config, run: {
      now: batch.context.now, run_id: batch.context.run_id, correlation_id: batch.context.correlation_id,
    },
    exclusions: {
      published_window_days: inputs.clock_config.collect.published_window_days,
      published_on: Object.fromEntries(publishedOn), settled_failure_codes: Object.fromEntries(failureCodes),
      matched_published_keys: publishedKeys, matched_failure_keys: failureKeys,
    },
  });
  const publications = await readPublisherPublication({
    root: inputs.root, day: selectionStartedAt.slice(0, 10), published: inputs.registrations.published,
    item_health: inputs.registrations.item_health, selections: inputs.registrations.selected_articles,
    published_days: inputs.settings.inputs.published_days, health_days: inputs.settings.inputs.settled_failure_days,
  });
  const curation = curateArticles({
    articles: screening.admitted, batch, inputs, health: health.sources, publications, context, selectionStartedAt,
  });
  const rejectedArticles = [
    ...screening.rejections.map(rejection => ({
      candidate_id: rejection.candidate_id, url_key: rejection.url_key, feed_id: rejection.feed_id,
      stage: rejection.stage, reason_code: rejection.drop_reason,
      freshness_cutoff_at: rejection.details.max_age_hours === null ? null
        : freshnessCutoff(batch.context.now, rejection.details.max_age_hours),
    })),
    ...curation.losses.map(loss => ({
      candidate_id: loss.article.candidate.candidate_id, url_key: loss.article.candidate.url_key,
      feed_id: loss.article.candidate.feed_id, stage: "curate-article-portfolio",
      reason_code: loss.reason, freshness_cutoff_at: loss.freshness_cutoff_at,
    })),
  ].map(row => RejectedArticleRowSchema.parse({
    ...row, run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
  }));
  const losses: PlannerRejectionCount[] = [...batch.exclusions];
  for (const rejection of screening.rejections) losses.push({
    feed_id: rejection.feed_id, subject: "article", stage: "screen-article-candidates",
    reason_code: rejection.drop_reason, attribution: null, count: 1,
  });
  for (const loss of curation.losses) losses.push({
    feed_id: loss.article.candidate.feed_id, subject: "article", stage: "curate-article-portfolio",
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
  const originalWork = context.run_id === batch.context.run_id && context.writer.attempt === batch.context.writer.attempt;
  const healthRows = originalWork ? captureHealthRows(batch.work_rows, health.sources) : [];
  for (const candidate of batch.candidates) {
    let row = healthRows.find(row => row.feed_id === candidate.feed_id && row.date === selectionStartedAt.slice(0, 10));
    if (row === undefined) {
      const source = planning.sources.find(source => source.id === candidate.feed_id);
      if (source === undefined) throw new Error("Selection candidate lacks its configured feed");
      row = FeedHealthStateRowSchema.parse({
        run_id: context.run_id, attempt: context.writer.attempt, feed_id: source.id,
        endpoint_key: inputEndpointKey(source.url), date: selectionStartedAt.slice(0, 10),
        checked_at: null, outcome: null, items: null,
        availability: health.sources.get(source.id)?.lifecycle ?? "unknown",
        strikes: health.sources.get(source.id)?.strikes ?? null, rested_runs: health.sources.get(source.id)?.rested_runs ?? null,
        reliability: health.sources.get(source.id)?.reliability ?? null,
        feed_reads: 0, productive_reads: 0, failed_reads: 0,
        feed_requests: 0, article_requests: 0, robots_requests: 0, article_candidates: 0, articles_selected: 0,
        rejection_counts: [], counts_complete: true, permission: "unknown", status: null, last_failure_code: null,
      });
      healthRows.push(row);
    }
  }
  for (const article of curation.articles) {
    const row = healthRows.find(row => row.feed_id === article.feed_id && row.date === selectionStartedAt.slice(0, 10))!;
    if (row.articles_selected !== null) row.articles_selected++;
  }
  for (const row of healthRows) {
    if (row.date !== selectionStartedAt.slice(0, 10)) continue;
    const losses = [...grouped.values()].filter(loss => loss.feed_id === row.feed_id
      && loss.stage !== "harvest-feeds" && loss.attribution === null);
    row.rejection_counts.push(...losses.map(({ feed_id: _feed, ...loss }) => loss));
  }
  return { articles: curation.articles, rejected_articles: rejectedArticles, health_rows: healthRows,
    exclusions: [...grouped.values()], request_report: health.request_report };
}
