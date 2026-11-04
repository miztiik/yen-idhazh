/** Project the existing fetch and parse facts as each bounded operation completes. */
import { createChildContext, DocumentWorkFactSchema, NetworkFailureDetailsSchema, OperationMetadataSchema } from "@idhazh/common-contracts";
import type { DocumentWorkFact, ExtractionQuality, NetworkFailureDetails, FetchAttempt, OperationMetadata } from "@idhazh/common-contracts";
import { observeDocument } from "./document-observation";
import type { DocumentIdentity } from "./document-observation";
import type { HarvestContext } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { FetchResult, SourceFetcher, FetchAttemptMeasurement } from "./fetch-source";
import { ArticleExtractionError } from "./dom-extractor";
import { FeedParseError } from "./parse-feed";
import { ParserError } from "./parser-error";
import { attributeIngestOutcome } from "../attribute-ingest-outcomes";

type Result = Pick<DocumentWorkFact, "outcome" | "failure_code">;
type QualityRejection = Pick<ExtractionQuality, "failure_code" | "source_word_count" | "word_count">;
type ParseResult = Result & { quality_rejection?: QualityRejection };
type Scope = {
  document_kind: "feed" | "article"; publisher_id: string | null; candidate_id: string | null;
  observed_run_id: string; observed_attempt: number; feed_id: string;
};
type Context = OperationMetadata & Pick<HarvestContext, "progress" | "observations" | "observation_clock" | "document_activity"> & {
  on_attempt?: (observation: ReturnType<typeof observeDocument>) => void;
};

export function documentWork(context: Context, identity: DocumentIdentity, operationContext: OperationMetadata, scope: Scope, initialFetch?: FetchResult) {
  const operation = OperationMetadataSchema.parse(operationContext);
  const enclosing = OperationMetadataSchema.parse({
    traceId: context.traceId, spanId: context.spanId, links: context.links,
    ...(context.parentSpanId === undefined ? {} : { parentSpanId: context.parentSpanId }),
    ...(context.traceState === undefined ? {} : { traceState: context.traceState }),
  });
  const publish = (operation: "fetch" | "parse" | "quality", phase: "started" | "completed" | "failed",
    metadata: OperationMetadata, duration_ms: number | null, url?: string, failure_code?: string | null,
    quality_rejection?: QualityRejection,
    fetched?: FetchResult) => context.document_activity?.(
    operation, phase, {
      scope: "document",
      article_id: identity.article_id, document_kind: scope.document_kind,
      feed_id: scope.feed_id, publisher_id: scope.publisher_id, duration_ms,
      ...(failure_code == null ? {} : { failure_code }),
      ...(quality_rejection === undefined ? {} : { quality_rejection }),
      ...(phase === "failed" && fetched?.body_limit != null ? {
        body_limit: fetched.body_limit,
      } : {}),
    }, phase === "failed" && scope.document_kind === "article" ? url : undefined,
    phase === "failed" && scope.document_kind === "feed" && url !== undefined
      ? { requested: url, final_attempted: fetched?.final_attempted_url ?? null } : undefined,
    phase === "failed" && fetched !== undefined && operation !== "quality"
      ? failureDetails(fetched, url, operation === "parse") : undefined,
    metadata,
  );
  let fetchedUrl: string | undefined;
  let finalAttemptedUrl: string | null = initialFetch?.final_attempted_url ?? null;
  let capturedFetch: FetchResult | undefined = initialFetch;
  function failureDetails(fetched: FetchResult, url: string | undefined, parsing = false, attempt: FetchAttempt | null = null): NetworkFailureDetails {
    const last = attempt ?? fetched.attempts?.filter(value => value.phase === "target" && value.request_profile !== null).at(-1);
    return NetworkFailureDetailsSchema.parse({
      requested_url: fetched.requested_url ?? url ?? null, final_attempted_url: fetched.final_attempted_url ?? null,
      failed_url: parsing ? null : attempt?.request_url ?? fetched.failed_url ?? null,
      http_status: attempt === null ? fetched.http_status : attempt.http_status,
      request_profile: attempt?.request_profile ?? fetched.response_evidence?.request_profile ?? last?.request_profile ?? null,
      response_evidence: attempt?.response_evidence ?? fetched.response_evidence ?? null,
      pacing_time_ms: attempt === null ? fetched.pacing_time_ms ?? null : attempt.pacing_wait_ms ?? 0,
      pacing_settings: fetched.pacing_settings ?? null,
      attempt,
    });
  }
  const timestamp = () => utcTimestamp(context.observation_clock);
  const event = (operation: "fetch" | "parse" | "attempt", metadata: OperationMetadata, occurred_at = timestamp()) =>
    observeDocument(identity, metadata, operation, occurred_at);
  const skippedParse = () => createChildContext(enclosing, { links: [{ traceId: operation.traceId, spanId: operation.spanId }] });
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
      publish("fetch", "started", operation, null);
      publish("fetch", "failed", operation, 0, url, failure_code);
    },
    async fetch(fetcher: Pick<SourceFetcher, "fetch">, url: string, signal?: AbortSignal) {
      const started = performance.now();
      fetchedUrl = url;
      publish("fetch", "started", operation, null);
      {
        let fetched: FetchResult;
        try {
          fetched = await fetcher.fetch(url, async measurement => {
            const attemptContext = createChildContext(operation);
            const observation = event("attempt", attemptContext, measurement.occurred_at);
            context.on_attempt?.(observation);
            if (measurement.outcome === "failed" && measurement.dispatched_request_count > 0) {
              context.document_activity?.("request-attempt", "failed", {
                scope: "request", article_id: identity.article_id,
                document_kind: scope.document_kind, feed_id: scope.feed_id, publisher_id: scope.publisher_id,
                duration_ms: measurement.attempt.duration_ms,
              }, undefined, undefined, failureDetails({
                body: null, http_status: measurement.attempt.http_status, failure: measurement.attempt.failure,
                final_attempted_url: measurement.final_attempted_url,
                pacing_time_ms: measurement.attempt.pacing_wait_ms ?? 0,
                pacing_settings: measurement.pacing_settings,
              }, url, false, measurement.attempt), attemptContext);
            }
            await save(observation, {
              outcome: measurement.outcome,
              failure_code: measurement.attempt.failure,
            }, measurement.attempt.duration_ms, measurement.attempt.http_status, measurement);
          }, scope.document_kind, signal, scope.publisher_id);
        } catch (error) {
          publish("fetch", "failed", operation, Math.round(performance.now() - started), url, "FETCH_FAILED");
          await save(event("fetch", operation), { outcome: "failed", failure_code: null },
            Math.round(performance.now() - started), null);
          throw error;
        }
        finalAttemptedUrl = fetched.final_attempted_url ?? null;
        capturedFetch = fetched;
        const observation = event("fetch", operation);
        publish("fetch", fetched.failure !== null || fetched.body === null ? "failed" : "completed",
          operation, Math.round(performance.now() - started), url, fetched.failure, undefined, fetched);
        await save(observation, {
          outcome: fetched.failure !== null ? "failed" : fetched.body === null ? "unavailable" : "success",
          failure_code: fetched.failure,
        }, Math.round(performance.now() - started), fetched.http_status);
        return { fetched, observation };
      }
    },
    async parse<T>(execute: (context: OperationMetadata) => Promise<T>, parseContext: OperationMetadata, describe: (parsed: T) => ParseResult, url = fetchedUrl) {
      const metadata = OperationMetadataSchema.parse(parseContext);
      const started = performance.now();
      publish("parse", "started", metadata, null);
      let parsed: T | null = null;
      let failure: "malformed-feed" | ArticleExtractionError["reason"] | ParserError["reason"] | null = null;
      let result: ParseResult;
      try {
        parsed = await execute(metadata);
        result = describe(parsed);
      } catch (error) {
        const observation = event("parse", metadata);
        failure = error instanceof ArticleExtractionError || error instanceof ParserError ? error.reason
          : error instanceof FeedParseError ? "malformed-feed" : null;
        publish("parse", "failed", metadata, Math.round(performance.now() - started), url, failure ?? "PARSE_FAILED", undefined, {
          ...(capturedFetch ?? { body: null, http_status: null, failure: null }),
          final_attempted_url: finalAttemptedUrl,
        });
        await save(observation, { outcome: "failed", failure_code: failure }, Math.round(performance.now() - started), null);
        if (failure === null) throw error;
        return { parsed, failure, observation };
      }
      const observation = event("parse", metadata);
      const { quality_rejection, ...workResult } = result;
      publish("parse", workResult.outcome === "failed" ? "failed" : "completed",
        metadata, Math.round(performance.now() - started), url, workResult.failure_code, undefined, {
          ...(capturedFetch ?? { body: null, http_status: null, failure: null }),
          final_attempted_url: finalAttemptedUrl,
        });
      await save(observation, workResult, Math.round(performance.now() - started), null);
      if (quality_rejection !== undefined) publish("quality", "failed", metadata, null, url, null, quality_rejection);
      return { parsed, failure, observation };
    },
    async skip() {
      const fetched = event("fetch", operation);
      await save(fetched, { outcome: "not_attempted", failure_code: null }, 0, null);
      await save(event("parse", skippedParse()), { outcome: "not_attempted", failure_code: null }, 0, null);
    },
    async skipParse(parseContext: OperationMetadata = skippedParse()) {
      await save(event("parse", parseContext), { outcome: "not_attempted", failure_code: null }, 0, null);
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
