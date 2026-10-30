/** Project the existing fetch and parse facts as each bounded operation completes. */
import { DocumentWorkFactSchema } from "@idhazh/common-contracts";
import type { DocumentWorkFact, ExtractionQuality } from "@idhazh/common-contracts";
import { observeDocument } from "./document-observation";
import type { DocumentIdentity } from "./document-observation";
import type { HarvestContext } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { FetchResult, PermittedFetcher } from "./robots-policy";
import type { FetchAttemptMeasurement } from "./robots-policy";
import { ArticleExtractionError } from "./dom-extractor";
import { FeedParseError } from "./parse-feed";
import { attributeIngestOutcome } from "../attribute-ingest-outcomes";

type Result = Pick<DocumentWorkFact, "outcome" | "failure_code">;
type QualityRejection = Pick<ExtractionQuality, "failure_code" | "source_word_count" | "word_count">;
type ParseResult = Result & { quality_rejection?: QualityRejection };
type Scope = {
  document_kind: "feed" | "article"; publisher_id: string | null; candidate_id: string | null;
  observed_run_id: string; observed_attempt: number; feed_id: string;
};
type Context = Pick<HarvestContext, "progress" | "observations" | "observation_clock" | "document_activity"> & {
  on_attempt?: (observation: ReturnType<typeof observeDocument>) => void;
};

export function documentWork(context: Context, identity: DocumentIdentity, key: string, scope: Scope) {
  const publish = (operation: "fetch" | "parse" | "quality", phase: "started" | "completed" | "failed",
    duration_ms: number | null, url?: string, failure_code?: string | null,
    quality_rejection?: QualityRejection) => context.document_activity?.(
    operation, phase, {
      scope: "document",
      request_id: key, article_id: identity.article_id, document_kind: scope.document_kind,
      feed_id: scope.feed_id, publisher_id: scope.publisher_id, duration_ms,
      ...(failure_code == null ? {} : { failure_code }),
      ...(quality_rejection === undefined ? {} : { quality_rejection }),
    }, scope.document_kind === "article" && phase === "failed" ? url : undefined,
  );
  let fetchedUrl: string | undefined;
  const timestamp = () => utcTimestamp(context.observation_clock);
  const event = (operation: "fetch" | "parse" | "attempt", cause: string | null, occurred_at = timestamp(), suffix = key) =>
    observeDocument(identity, suffix, operation, cause, occurred_at);
  async function save(
    observation: ReturnType<typeof observeDocument>, result: Result, duration_ms: number, http_status: number | null,
    measurement?: FetchAttemptMeasurement,
  ) {
    const candidate = {
      document_kind: scope.document_kind, feed_id: scope.feed_id,
      run_id: scope.observed_run_id, attempt: scope.observed_attempt,
      operation: observation.operation, occurred_at: observation.occurred_at,
      ...result, duration_ms, http_status,
      request_phase: measurement?.attempt.phase ?? null,
      dispatched_request_count: measurement?.dispatched_request_count ?? null,
      request_coverage: measurement?.request_coverage ?? null,
    };
    const row = DocumentWorkFactSchema.parse({
      ...candidate, attribution: attributeIngestOutcome(candidate),
    });
    await context.observations?.save([row]);
  }
  return {
    rejectFetch(url: string, failure_code: string) {
      publish("fetch", "started", null);
      publish("fetch", "failed", 0, url, failure_code);
    },
    async fetch(fetcher: Pick<PermittedFetcher, "fetch">, url: string, cause: string | null = null) {
      const started = performance.now();
      fetchedUrl = url;
      publish("fetch", "started", null);
      const fetchId = event("fetch", cause).event_id;
      {
        let fetched: FetchResult;
        try {
          fetched = await fetcher.fetch(url, async measurement => {
            const observation = event("attempt", fetchId, measurement.occurred_at, `${key}\n${measurement.attempt.sequence}`);
            context.on_attempt?.(observation);
            await save(observation, {
              outcome: measurement.outcome,
              failure_code: measurement.attempt.failure,
            }, measurement.attempt.duration_ms, measurement.attempt.http_status, measurement);
          }, scope.document_kind);
        } catch (error) {
          publish("fetch", "failed", Math.round(performance.now() - started), url, "FETCH_FAILED");
          await save(event("fetch", cause), { outcome: "failed", failure_code: null },
            Math.round(performance.now() - started), null);
          throw error;
        }
        const observation = event("fetch", cause);
        publish("fetch", fetched.failure !== null || fetched.body === null ? "failed" : "completed",
          Math.round(performance.now() - started), url, fetched.failure);
        await save(observation, {
          outcome: fetched.failure !== null ? "failed" : fetched.body === null ? "unavailable" : "success",
          failure_code: fetched.failure,
        }, Math.round(performance.now() - started), fetched.http_status);
        return { fetched, observation };
      }
    },
    async parse<T>(execute: () => Promise<T>, cause: string, describe: (parsed: T) => ParseResult, url = fetchedUrl) {
      const started = performance.now();
      publish("parse", "started", null);
      let parsed: T | null = null;
      let failure: "malformed-feed" | ArticleExtractionError["reason"] | null = null;
      let result: ParseResult;
      try {
        parsed = await execute();
        result = describe(parsed);
      } catch (error) {
        const observation = event("parse", cause);
        failure = error instanceof ArticleExtractionError ? error.reason : error instanceof FeedParseError ? "malformed-feed" : null;
        publish("parse", "failed", Math.round(performance.now() - started), url, failure ?? "PARSE_FAILED");
        await save(observation, { outcome: "failed", failure_code: failure }, Math.round(performance.now() - started), null);
        if (failure === null) throw error;
        return { parsed, failure, observation };
      }
      const observation = event("parse", cause);
      const { quality_rejection, ...workResult } = result;
      publish("parse", workResult.outcome === "failed" ? "failed" : "completed",
        Math.round(performance.now() - started), url, workResult.failure_code);
      await save(observation, workResult, Math.round(performance.now() - started), null);
      if (quality_rejection !== undefined) publish("quality", "failed", null, url, null, quality_rejection);
      return { parsed, failure, observation };
    },
    async skip() {
      const fetched = event("fetch", null);
      await save(fetched, { outcome: "not_attempted", failure_code: null }, 0, null);
      await save(event("parse", fetched.event_id), { outcome: "not_attempted", failure_code: null }, 0, null);
    },
    async skipParse(cause: string) {
      await save(event("parse", cause), { outcome: "not_attempted", failure_code: null }, 0, null);
    },
  };
}

export function describeArticleParse(parsed: { article_text: string; quality?: ExtractionQuality | null }): ParseResult {
  const quality = parsed.quality;
  const quality_rejection = quality?.rejected && quality.failure_code !== null ? {
    failure_code: quality.failure_code, source_word_count: quality.source_word_count, word_count: quality.word_count,
  } : undefined;
  return parsed.article_text
    ? { outcome: "success", failure_code: null, ...(quality_rejection === undefined ? {} : { quality_rejection }) }
    : { outcome: "failed", failure_code: "empty-content", ...(quality_rejection === undefined ? {} : { quality_rejection }) };
}
export function describeFeedParse(parsed: readonly unknown[]): Result {
  return { outcome: parsed.length ? "success" : "empty", failure_code: null };
}
