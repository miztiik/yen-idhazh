/** Project the existing fetch and parse facts as each bounded operation completes. */
import { DocumentObservationRecordSchema } from "@idhazh/common-contracts";
import type { DocumentObservationRecord } from "@idhazh/common-contracts";
import { observeDocument } from "./document-observation";
import type { DocumentIdentity } from "./document-observation";
import type { HarvestContext } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { FetchResult, PermittedFetcher } from "./robots-policy";
import type { FetchAttemptMeasurement } from "./robots-policy";
import { ArticleExtractionError } from "./dom-extractor";
import { FeedParseError } from "./parse-feed";
import { PlannerObservationSchema } from "../api/operation-contracts";

type Result = Pick<DocumentObservationRecord, "outcome" | "failure_code">;
type Scope = Pick<DocumentObservationRecord,
  "document_kind" | "publisher_id" | "candidate_id" | "observed_run_id" | "observed_attempt" | "source_id">;
type Context = Pick<HarvestContext, "progress" | "observations" | "observation_clock">;

export function documentWork(context: Context, identity: DocumentIdentity, key: string, scope: Scope) {
  const timestamp = () => utcTimestamp(context.observation_clock);
  const event = (operation: "fetch" | "parse" | "attempt", cause: string | null, occurred_at = timestamp(), suffix = key) =>
    observeDocument(identity, suffix, operation, cause, occurred_at);
  async function save(
    observation: ReturnType<typeof observeDocument>, result: Result, duration_ms: number, http_status: number | null,
    measurement?: FetchAttemptMeasurement, batch?: DocumentObservationRecord[],
  ) {
    const row = DocumentObservationRecordSchema.parse({
      ...scope, event_id: observation.event_id, caused_by_event_id: observation.caused_by_event_id,
      corrects_event_id: null, correction_revision: null,
      correlation_id: observation.correlation_id, article_id: observation.article_id,
      operation: observation.operation, occurred_at: observation.occurred_at,
      ...result, attribution: result.outcome === "failed" ? "unresolved" : null, duration_ms, http_status,
      request_phase: measurement?.attempt.phase ?? null, request_sequence: measurement?.attempt.sequence ?? null,
      retry: measurement?.attempt.retry ?? null,
      dispatched_request_count: measurement?.dispatched_request_count ?? null,
      request_coverage: measurement?.request_coverage ?? null,
    });
    if (batch !== undefined) batch.push(row);
    else await context.observations?.save([row]);
    if (result.outcome !== "not_attempted" && observation.source_id !== null && observation.article_id !== null) {
      context.progress?.(observation.operation === "fetch" ? "DOCUMENT_FETCHED"
        : observation.operation === "parse" ? "DOCUMENT_PARSED" : "FETCH_ATTEMPT_COMPLETED", {
        document_observation: PlannerObservationSchema.parse(observation),
        ...(measurement === undefined ? {} : { fetch_attempt: measurement.attempt }),
      });
    }
  }
  return {
    async fetch(fetcher: Pick<PermittedFetcher, "fetch">, url: string, cause: string | null = null) {
      const started = performance.now();
      const fetchId = event("fetch", cause).event_id;
      const attempt_observations: ReturnType<typeof observeDocument>[] = [];
      const rows: DocumentObservationRecord[] = [];
      try {
        let fetched: FetchResult;
        try {
          fetched = await fetcher.fetch(url, async measurement => {
            const observation = event("attempt", fetchId, measurement.occurred_at, `${key}\n${measurement.attempt.sequence}`);
            attempt_observations.push(observation);
            await save(observation, {
              outcome: measurement.outcome,
              failure_code: measurement.attempt.failure,
            }, measurement.attempt.duration_ms, measurement.attempt.http_status, measurement, rows);
          });
        } catch (error) {
          await save(event("fetch", cause), { outcome: "failed", failure_code: null },
            Math.round(performance.now() - started), null, undefined, rows);
          throw error;
        }
        const observation = event("fetch", cause);
        await save(observation, {
          outcome: fetched.failure !== null ? "failed" : fetched.body === null ? "unavailable" : "success",
          failure_code: fetched.failure,
        }, Math.round(performance.now() - started), fetched.http_status, undefined, rows);
        return { fetched, observation, attempt_observations };
      } finally {
        await context.observations?.save(rows);
      }
    },
    async parse<T>(execute: () => Promise<T>, cause: string, describe: (parsed: T) => Result) {
      const started = performance.now();
      let parsed: T | null = null;
      let failure: "malformed-feed" | ArticleExtractionError["reason"] | null = null;
      let result: Result;
      try {
        parsed = await execute();
        result = describe(parsed);
      } catch (error) {
        const observation = event("parse", cause);
        failure = error instanceof ArticleExtractionError ? error.reason : error instanceof FeedParseError ? "malformed-feed" : null;
        await save(observation, { outcome: "failed", failure_code: failure }, Math.round(performance.now() - started), null);
        if (failure === null) throw error;
        return { parsed, failure, observation };
      }
      const observation = event("parse", cause);
      await save(observation, result, Math.round(performance.now() - started), null);
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

export function describeArticleParse(parsed: { article_text: string }): Result {
  return parsed.article_text ? { outcome: "success", failure_code: null }
    : { outcome: "failed", failure_code: "empty-content" };
}
export function describeFeedParse(parsed: readonly unknown[]): Result {
  return { outcome: parsed.length ? "success" : "empty", failure_code: null };
}
