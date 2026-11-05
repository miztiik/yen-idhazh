/** Which complete safe native diagnostic explains one terminal article rejection? */
import { z } from "zod";
import { FeedIngestEventDataSchema, FeedIngestEventSchema, PLANNER_PROGRESS_DETAIL_LIMITS } from "./event.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import {
  CandidateIdSchema, PositiveCountSchema, RejectionStageSchema, Sha256Schema, SlugSchema, reject,
} from "./primitives";
import { DropReasonSchema, HarvestArticleFailureReasonSchema } from "./rejection.schema";

export const ARTICLE_FAILURE_DIAGNOSTIC_VERSION = "2026-11-05";
// MIME tokens exclude parameters and other response header values.
const MEDIA_TYPE_PATTERN = /^[A-Za-z0-9!#$%&'*+.^_`|~-]+\/[A-Za-z0-9!#$%&'*+.^_`|~-]+$/;
export function articleDiagnosticContentType(value: string | null): string | null {
  const mediaType = value?.split(";", 1)[0]?.trim() ?? null;
  return mediaType !== null && MEDIA_TYPE_PATTERN.test(mediaType) ? mediaType : null;
}

function withinDetailBounds(value: unknown): boolean {
  let entries = 0;
  function visit(item: unknown, depth: number): boolean {
    if (typeof item === "string") {
      return item.length <= PLANNER_PROGRESS_DETAIL_LIMITS.stringLength && !/https?:\/\//i.test(item);
    }
    if (item === null || typeof item !== "object") return true;
    if (depth >= PLANNER_PROGRESS_DETAIL_LIMITS.depth) return false;
    const children = Object.values(item);
    entries += children.length;
    return entries <= PLANNER_PROGRESS_DETAIL_LIMITS.entries && children.every(child => visit(child, depth + 1));
  }
  return visit(value, 0) && Buffer.byteLength(JSON.stringify(value), "utf8") <= PLANNER_PROGRESS_DETAIL_LIMITS.bytes;
}

const CompleteHarvestDiagnosticsSchema = z.preprocess((value, ctx) => {
  if (value !== null && typeof value === "object") {
    for (const field of Object.keys(HarvestDiagnosticsSchema.shape)) {
      if (!Object.hasOwn(value, field) || Reflect.get(value, field) === undefined) {
        reject(ctx, "terminal diagnostics require every native field", [field]);
      }
    }
  }
  return value;
}, HarvestDiagnosticsSchema);

export const ArticleFailureDiagnosticDetailsSchema = z.strictObject({
  attempt: PositiveCountSchema, feed_id: SlugSchema, candidate_id: CandidateIdSchema, url_key: Sha256Schema,
  stage: RejectionStageSchema.extract(["harvest-feeds"]),
  reason_code: DropReasonSchema.extract([...HarvestArticleFailureReasonSchema.options, "MISSING_REQUIRED_FIELDS"]),
  diagnostics: CompleteHarvestDiagnosticsSchema,
}).superRefine((value, ctx) => {
  const response = value.diagnostics.response_evidence;
  if (response !== null && (Object.keys(response.selected_headers).length !== 0
    || response.headers_truncated.length !== 0
    || (response.content_type !== null && !MEDIA_TYPE_PATTERN.test(response.content_type)))) {
    reject(ctx, "article diagnostics retain only MIME type and safe response counts", ["diagnostics", "response_evidence"]);
  }
  if (!withinDetailBounds(value)) reject(ctx, "article diagnostics exceed progress detail safety limits");
});
export const ArticleFailureDiagnosticDataSchema = FeedIngestEventDataSchema.extend({
  operation: FeedIngestEventDataSchema.shape.operation.extract(["fetch", "parse", "quality"]),
  phase: z.literal("failed"), details: ArticleFailureDiagnosticDetailsSchema,
}).superRefine((value, ctx) => {
  const { reason_code, diagnostics } = value.details;
  const fetch = reason_code === "FETCH_FAILED" || reason_code === "FETCH_FAILED_HTTP" || reason_code === "FETCH_TIMEOUT";
  if (fetch !== (value.operation === "fetch")) reject(ctx, "terminal reason must match the captured operation", ["operation"]);
  if (value.operation === "quality" && (reason_code !== "EXTRACT_FAILED" || diagnostics.quality?.rejected !== true)) {
    reject(ctx, "quality diagnostics require the native measured rejection", ["operation"]);
  }
  if (diagnostics.quality?.rejected === true && value.operation !== "quality") {
    reject(ctx, "a measured quality rejection uses the quality operation", ["operation"]);
  }
  if (reason_code === "MISSING_REQUIRED_FIELDS"
    && (value.operation !== "parse" || diagnostics.extraction_failure !== "missing-title")) {
    reject(ctx, "only a post-parse missing title is a terminal diagnostic", ["details", "reason_code"]);
  }
});
export const ArticleFailureDiagnosticSchema = FeedIngestEventSchema.and(z.object({
  data: ArticleFailureDiagnosticDataSchema,
})).meta({
  version: ARTICLE_FAILURE_DIAGNOSTIC_VERSION,
  readCompatibility: "current_only; diagnostic readers and writers change together",
  changelog: [
    { version: ARTICLE_FAILURE_DIAGNOSTIC_VERSION, change: "Retain complete safe native terminal article failure diagnostics." },
  ],
});
export type ArticleFailureDiagnostic = z.infer<typeof ArticleFailureDiagnosticSchema>;

export function isArticleFailureDiagnostic(value: unknown): boolean {
  if (value === null || typeof value !== "object" || !("data" in value)) return false;
  const data = value.data;
  if (data === null || typeof data !== "object" || !("details" in data)) return false;
  const details = data.details;
  return details !== null && typeof details === "object"
    && (("stage" in details && details.stage === "harvest-feeds")
      || ("reason_code" in details && "diagnostics" in details));
}
