/** Which captured terminal diagnostics agree with this report's article failures? */
import { isDeepStrictEqual } from "node:util";
import { ArticleFailureDiagnosticSchema, readTraceContext } from "@idhazh/common-contracts";
import type { ArticleFailureDiagnostic, RejectedArticleRow } from "@idhazh/common-contracts";

export type ReportDiagnosticIdentity = Readonly<{ run_id?: string; attempt?: number; traceId?: string }>;
export const articleFailureKey = (run_id: string, attempt: number, candidate_id: string) =>
  JSON.stringify([run_id, attempt, candidate_id]);

export function distinctArticleDiagnostics(
  input: readonly ArticleFailureDiagnostic[], expected: ReportDiagnosticIdentity = {},
): ArticleFailureDiagnostic[] {
  const candidates = new Map<string, ArticleFailureDiagnostic>();
  const occurrences = new Map<string, ArticleFailureDiagnostic>();
  for (const raw of input) {
    const event = ArticleFailureDiagnosticSchema.parse(raw);
    if ((expected.run_id !== undefined && event.data.run_id !== expected.run_id)
      || (expected.attempt !== undefined && event.data.details.attempt !== expected.attempt)
      || (expected.traceId !== undefined && readTraceContext({
        traceparent: event.traceparent, tracestate: event.tracestate,
      })?.traceId !== expected.traceId)) {
      throw new Error("Article diagnostic report belongs to another execution");
    }
    const key = articleFailureKey(event.data.run_id, event.data.details.attempt, event.data.details.candidate_id);
    for (const previous of [candidates.get(key), occurrences.get(event.id)]) {
      if (previous !== undefined && !isDeepStrictEqual(previous, event)) {
        throw new Error("Conflicting terminal article diagnostics");
      }
    }
    candidates.set(key, event);
    occurrences.set(event.id, event);
  }
  return [...candidates.values()];
}

export function checkArticleDiagnostic(article: RejectedArticleRow, event: ArticleFailureDiagnostic): void {
  const { details } = event.data;
  const same = article.run_id === event.data.run_id && article.attempt === details.attempt
    && article.candidate_id === details.candidate_id && article.feed_id === details.feed_id
    && article.url_key === details.url_key && article.stage === details.stage && article.reason_code === details.reason_code;
  if (!same || (["http_status", "fetch_failure", "error_code", "pacing_time_ms", "pacing_settings"] as const)
    .some(field => !isDeepStrictEqual(article[field], details.diagnostics[field]))) {
    throw new Error("Terminal article diagnostic disagrees with saved rejection evidence");
  }
}

export function describeArticleDiagnostic(event: ArticleFailureDiagnostic): string {
  const diagnostic = event.data.details.diagnostics;
  const cause = diagnostic.extraction_failure ?? diagnostic.quality?.failure_code
    ?? diagnostic.fetch_failure ?? diagnostic.detail ?? diagnostic.failure_code;
  const quality = diagnostic.quality;
  return [
    cause === null ? "specific cause unavailable" : cause.replace(/[-_]/g, " "),
    ...(quality === null ? [] : [
      `${quality.source_word_count} source words measured during extraction`,
      `${quality.word_count} body words measured during extraction`,
    ]),
  ].join("; ");
}

export function renderArticleDiagnostics(events: readonly ArticleFailureDiagnostic[]): string {
  if (events.length === 0) return "";
  const json = JSON.stringify(events, null, 2).replace(/[<>&`]/g,
    character => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return [
    "", "<details>", "<summary>Terminal article diagnostic details</summary>", "",
    "These are captured failures, not extra health totals. Word counts measure extraction, not every word on the source page or later API word shortening. Null means not measured; zero is a measured value.",
    "", "```json", json, "```", "", "</details>",
  ].join("\n");
}
