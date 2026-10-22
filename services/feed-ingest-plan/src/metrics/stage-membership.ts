/** Which candidate instances and first terminal losses belong to this exact attempt? */
import { isDeepStrictEqual } from "node:util";
import {
  CandidateRejectionRecordSchema, FeedIngestCandidateSchema, FeedIngestEventSchema,
  FeedOutcomePayloadSchema, SourceSnapshotSchema, WriterIdentitySchema, EditorialSelectionRowSchema,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, FeedIngestCandidate, SourceSnapshot } from "@idhazh/common-contracts";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { measureArticle } from "../curate-article-portfolio/quality-decoupler";
import type { FeedPlanResult } from "../run-feed-plan";

export function requireSame(actual: unknown, expected: unknown, field: string): void {
  if (!isDeepStrictEqual(actual, expected)) throw new Error(`${field}: evidence does not match this attempt`);
}

function indexCandidates(candidates: readonly FeedIngestCandidate[], field: string) {
  const indexed = new Map<string, FeedIngestCandidate>();
  for (const raw of candidates) {
    const candidate = FeedIngestCandidateSchema.parse(raw);
    if (indexed.has(candidate.candidate_id)) throw new Error(`${field}.${candidate.candidate_id}: repeated candidate instance`);
    indexed.set(candidate.candidate_id, candidate);
  }
  return indexed;
}

function partition(
  input: readonly FeedIngestCandidate[], output: readonly FeedIngestCandidate[],
  rejected: readonly CandidateRejectionRecord[], field: string,
) {
  const remaining = indexCandidates(input, `${field}.input`);
  indexCandidates(output, `${field}.output`);
  for (const candidate of output) {
    requireSame(candidate, remaining.get(candidate.candidate_id), `${field}.${candidate.candidate_id}`);
    remaining.delete(candidate.candidate_id);
  }
  for (const rejection of rejected) {
    const candidate = rejection.candidate_id === null ? undefined : remaining.get(rejection.candidate_id);
    if (candidate === undefined) throw new Error(`${field}.${rejection.candidate_id}: rejection is not a first terminal loss`);
    requireSame([rejection.source_id, rejection.url_key], [candidate.source_id, candidate.url_key], `${field}.rejection`);
    remaining.delete(candidate.candidate_id);
  }
  if (remaining.size !== 0) throw new Error(`${field}: input does not equal output plus terminal losses`);
}

export function reconcileStageMembership(result: FeedPlanResult) {
  const { harvest, screening, curation, partition: dispatch } = result.evidence;
  const { context } = result;
  WriterIdentitySchema.parse(context.writer);
  requireSame(context.run_id, context.writer.run_id, "context.writer.run_id");
  const sources = harvest.inputs.sources.map(source => SourceSnapshotSchema.parse(sourceSnapshot(harvest.inputs, source)));
  const bySource = new Map<string, SourceSnapshot>();
  for (const source of sources) {
    if (bySource.has(source.source_id)) throw new Error(`sources.${source.source_id}: repeated source`);
    bySource.set(source.source_id, source);
  }
  const candidates = indexCandidates(harvest.candidates, "harvest.candidates");
  const articles = new Set<string>();
  for (const article of harvest.articles) {
    const item = article.candidate ?? article.rejection;
    if (item === null || item.candidate_id === null || articles.has(item.candidate_id)) {
      throw new Error("harvest.articles: each entry requires one distinct candidate instance");
    }
    articles.add(item.candidate_id);
    requireSame(article.observation.candidate_id, item.candidate_id, "harvest.observation.candidate_id");
    const earlyStale = article.rejection?.drop_reason === "STALE_MAX_AGE_EXCEEDED";
    requireSame(article.observation.preflight_freshness !== undefined, earlyStale, "harvest.preflight_freshness");
    if (earlyStale) requireSame([
      article.observation.extraction, article.observation.http_status, article.observation.robots,
      article.observation.paywall, article.observation.paywall_evidence, article.observation.fetch_failure,
    ], ["not-attempted", null, null, null, "not-observed", null], "harvest.preflight_observation");
    if (article.candidate !== null) requireSame(article.candidate, candidates.get(item.candidate_id), "harvest.article");
    else if (!harvest.rejections.some(row => isDeepStrictEqual(row, article.rejection))) {
      throw new Error("harvest.articles: terminal rejection is missing");
    }
  }
  for (const candidate of candidates.values()) {
    requireSame([candidate.run_id, candidate.correlation_id], [context.run_id, context.correlation_id], `candidate.${candidate.candidate_id}.run`);
    requireSame(candidate.source, bySource.get(candidate.source_id), `candidate.${candidate.candidate_id}.source`);
    requireSame([candidate.date, candidate.fetched_at], [context.date, context.now], `candidate.${candidate.candidate_id}.time`);
    if (!articles.has(candidate.candidate_id)) throw new Error("harvest.candidates: missing original entry");
  }
  requireSame(harvest.articles.flatMap(article => article.rejection === null ? [] : [article.rejection]),
    harvest.rejections.filter(row => row.subject === "article"), "harvest.article_rejections");
  const rejections = [...harvest.rejections, ...screening.rejections, ...curation.rejections];
  for (const raw of rejections) {
    const rejection = CandidateRejectionRecordSchema.parse(raw);
    if (!bySource.has(rejection.source_id)) throw new Error(`rejections.${rejection.source_id}: unknown source`);
    requireSame([rejection.date, rejection.correlation_id, rejection.rejected_at],
      [context.date, context.correlation_id, context.now], "rejections.run");
  }
  const outcomes = new Set<string>();
  for (const raw of harvest.feed_outcomes) {
    const outcome = FeedOutcomePayloadSchema.parse(raw);
    const id = outcome.source.source_id;
    if (outcomes.has(id)) throw new Error(`feed_outcomes.${id}: repeated outcome`);
    outcomes.add(id);
    requireSame(outcome.source, bySource.get(id), `feed_outcomes.${id}.source`);
    const offered = harvest.articles.filter(article => (article.candidate ?? article.rejection)!.source_id === id);
    if (outcome.fetch_status === "not_requested" ? outcome.fetch_duration_ms !== null : outcome.fetch_duration_ms === null) {
      throw new Error(`feed_outcomes.${id}.fetch_duration_ms: must match whether a fetch was attempted`);
    }
    if (outcome.fetch_status !== "success" && outcome.parse_status !== "not_attempted") {
      throw new Error(`feed_outcomes.${id}.parse_status: a failed or unrequested fetch cannot be parsed`);
    }
    if (outcome.parse_status === "not_attempted") {
      requireSame([outcome.parse_duration_ms, outcome.parsed_count, outcome.harvested_count, offered.length],
        [null, null, null, 0], `feed_outcomes.${id}.unattempted_parse`);
    } else {
      if (outcome.parse_duration_ms === null) throw new Error(`feed_outcomes.${id}.parse_duration_ms: attempted parse needs a duration`);
      if (outcome.parse_status === "failure") requireSame([outcome.parsed_count, outcome.harvested_count, offered.length],
        [null, null, 0], `feed_outcomes.${id}.failed_parse`);
      else if (outcome.parsed_count === null || outcome.harvested_count === null
        || (outcome.parse_status === "empty") !== (outcome.parsed_count === 0)) {
        throw new Error(`feed_outcomes.${id}.parsed_count: successful parse must retain its nonempty or empty count`);
      }
    }
    if (outcome.parsed_count !== null) requireSame(offered.length, outcome.parsed_count, `feed_outcomes.${id}.parsed_count`);
    if (outcome.harvested_count !== null) requireSame(outcome.harvested_count,
      harvest.candidates.filter(candidate => candidate.source_id === id).length, `feed_outcomes.${id}.harvested_count`);
    const feedDrops = harvest.rejections.filter(row => row.source_id === id && row.subject === "feed");
    requireSame(feedDrops.map(row => row.drop_reason), outcome.rejection_reason === null ? [] : [outcome.rejection_reason], `feed_outcomes.${id}.rejection`);
  }
  requireSame([...outcomes].sort(), [...bySource.keys()].sort(), "feed_outcomes.sources");
  const eligible = screening.admitted.map(article => article.candidate);
  partition(harvest.candidates, eligible, screening.rejections, "screening");
  requireSame(curation.input.map(article => article.candidate), eligible, "curation.input");
  for (const [index, article] of curation.input.entries()) {
    const { evidence: _evidence, ...screened } = article;
    requireSame(screened, screening.admitted[index], `curation.input.${article.candidate.candidate_id}.screening`);
  }
  requireSame(curation.quality, curation.input.map(article => ({
    candidate_id: article.candidate.candidate_id, ...measureArticle(article),
  })), "curation.quality");
  const representatives = curation.carriers.representatives.map(article => article.candidate);
  const suppressedIds = new Set(curation.carriers.suppressed.map(row => row.article.candidate.candidate_id));
  partition(eligible, representatives, curation.rejections.filter(row => row.candidate_id !== null && suppressedIds.has(row.candidate_id)), "deduplication");
  const normalized = curation.normalization.admitted.map(article => article.candidate);
  const normalizedDrops = new Set(curation.normalization.rejected.map(row => row.article.candidate.candidate_id));
  partition(representatives, normalized, curation.rejections.filter(row => row.candidate_id !== null && normalizedDrops.has(row.candidate_id)), "normalization");
  const selected = curation.selected.map(article => article.candidate);
  partition(eligible, selected, curation.rejections, "curation");
  partition(normalized, selected, curation.rejections.filter(row =>
    row.candidate_id !== null && !suppressedIds.has(row.candidate_id) && !normalizedDrops.has(row.candidate_id)), "selection");
  requireSame(curation.rows.map(row => row.candidate_id), selected.map(candidate => candidate.candidate_id), "curation.rows");
  for (const raw of curation.rows) {
    const row = EditorialSelectionRowSchema.parse(raw);
    const candidate = candidates.get(row.candidate_id)!;
    requireSame([row.source, row.url_key, row.policy, row.labels, row.correlation_id, row.date],
      [candidate.source, candidate.url_key, candidate.policy, candidate.labels, context.correlation_id, context.date], "curation.selection");
    requireSame(row.ratings, curation.choices.find(choice => choice.candidate_id === row.candidate_id)?.scores, "curation.selection.ratings");
  }
  if (new Set(selected.map(candidate => candidate.url_key)).size !== selected.length) {
    throw new Error("selection.url_key: selected articles must be unique");
  }
  requireSame(dispatch.dispatches.map(row => row.content.candidate_id).sort(),
    selected.map(candidate => candidate.candidate_id).sort(), "partition.dispatches");
  const eventIds = new Set<string>();
  const decisions = new Map<string, FeedIngestCandidate[]>();
  decisions.set("harvest-feeds", harvest.candidates);
  decisions.set("screen-article-candidates", eligible);
  decisions.set("curate-article-portfolio", selected);
  const completion = new Map([
    ["harvest-feeds", [harvest.candidates.length + harvest.rejections.length, harvest.candidates.length, harvest.rejections.length]],
    ["screen-article-candidates", [harvest.candidates.length, eligible.length, screening.rejections.length]],
    ["curate-article-portfolio", [eligible.length, selected.length, curation.rejections.length]],
    ["partition-article-shards", [selected.length, dispatch.dispatches.length, 0]],
    ["seal-article-ledger", [dispatch.dispatches.length, dispatch.dispatches.length, 0]],
  ]);
  const completed = new Set<string>();
  const eventOutcomes: typeof harvest.feed_outcomes = [];
  const eventDecisions = new Set<string>();
  const choices: typeof curation.choices = [];
  const stageOrder = [...completion.keys()];
  let previousStage = 0;
  for (const [index, raw] of result.events.entries()) {
    const event = FeedIngestEventSchema.parse(raw);
    requireSame([event.run_id, event.attempt, event.correlation_id, event.occurred_at],
      [context.run_id, context.writer.attempt, context.correlation_id, context.now], "events.run");
    if (eventIds.has(event.event_id)) throw new Error("events.event_id: repeated observation");
    eventIds.add(event.event_id);
    requireSame(event.sequence, index, "events.sequence");
    const stageIndex = stageOrder.indexOf(event.stage);
    if (stageIndex < previousStage) throw new Error("events.stage: stage observations are out of order");
    previousStage = stageIndex;
    if (completed.has(event.stage)) throw new Error(`events.${event.stage}: observation follows stage completion`);
    const payload = event.payload;
    if (payload.kind === "feed_outcome") eventOutcomes.push(payload);
    if (payload.kind === "portfolio_choice") choices.push(payload);
    if (payload.kind === "stage_completion") {
      if (completed.has(event.stage)) throw new Error(`events.${event.stage}: repeated completion`);
      completed.add(event.stage);
      requireSame([payload.input_count, payload.output_count, payload.terminal_rejection_count], completion.get(event.stage), `events.${event.stage}.counts`);
    }
    if (payload.kind === "candidate_decision") {
      const row = payload.assessment;
      const key = `${row.stage}:${row.candidate_id}`;
      if (eventDecisions.has(key)) throw new Error(`events.${key}: repeated decision`);
      eventDecisions.add(key);
      requireSame([row.correlation_id, row.date, row.observed_at], [context.correlation_id, context.date, context.now], `events.${key}.identity`);
      requireSame(row.source, bySource.get(row.source_id), `events.${key}.source`);
      const rejection = rejections.find(item => item.stage === row.stage && item.candidate_id === row.candidate_id);
      const accepted = decisions.get(row.stage)?.find(item => item.candidate_id === row.candidate_id);
      if ((accepted === undefined) === (rejection === undefined)) throw new Error(`events.${key}: no single actual decision`);
      requireSame([row.decision, row.reason], rejection !== undefined ? ["rejected", rejection.drop_reason]
        : [row.stage === "curate-article-portfolio" ? "selected" : "admitted", null], `events.${key}.decision`);
    }
  }
  requireSame([...completed].sort(), [...completion.keys()].sort(), "events.stage_completions");
  requireSame(eventOutcomes, harvest.feed_outcomes, "events.feed_outcomes");
  requireSame(choices, curation.choices, "events.portfolio_choices");
  const expectedDecisions = [
    ...harvest.articles.map(article => `harvest-feeds:${article.observation.candidate_id}`),
    ...harvest.candidates.map(candidate => `screen-article-candidates:${candidate.candidate_id}`),
    ...eligible.map(candidate => `curate-article-portfolio:${candidate.candidate_id}`),
  ];
  requireSame([...eventDecisions].sort(), expectedDecisions.sort(), "events.candidate_membership");
  const stale = new Set(screening.rejections.filter(row => row.drop_reason === "STALE_MAX_AGE_EXCEEDED").map(row => row.candidate_id));
  const earlyStale = harvest.articles.filter(article => article.rejection?.drop_reason === "STALE_MAX_AGE_EXCEEDED")
    .map(article => ({
      candidate_id: article.observation.candidate_id, source_id: article.rejection!.source_id,
    }));
  return {
    sources, harvested: harvest.candidates,
    freshness_input: [...harvest.candidates, ...earlyStale],
    freshness: harvest.candidates.filter(candidate => !stale.has(candidate.candidate_id)),
    eligible, representatives, normalized, selected, rejections,
    carrier_groups: curation.carriers.groups, normalization: curation.normalization,
    trace: curation.trace, quality: curation.quality,
  };
}
export type StageMembership = ReturnType<typeof reconcileStageMembership>;
