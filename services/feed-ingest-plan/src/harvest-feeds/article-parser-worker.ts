/** Parse one inert feed or HTML document in a native worker. */
import { z } from "zod";
import { extractArticle, ArticleExtractionError } from "./dom-extractor";
import { ExtractionControlsSchema } from "./extraction-controls";
import { ArticleContentEvidenceSchema, CountSchema, ExtractionQualitySchema, HarvestDiagnosticsSchema, PlannerFeedEntrySchema, UrlSchema } from "@idhazh/common-contracts";
import { isMainThread } from "node:worker_threads";
import { FeedParseError, parseFeed } from "./parse-feed";

export const ArticleParserRequestSchema = z.discriminatedUnion("kind", [
  z.strictObject({ id: z.uuid(), kind: z.literal("article"), body: z.string(), url: UrlSchema, config: ExtractionControlsSchema }),
  z.strictObject({ id: z.uuid(), kind: z.literal("feed"), body: z.string() }),
]);
export type ArticleParserRequest = z.infer<typeof ArticleParserRequestSchema>;
export type ArticleParserResult = Awaited<ReturnType<typeof extractArticle>>;
export type FeedParserResult = Awaited<ReturnType<typeof parseFeed>>;
export type ArticleParserResponse =
  | { id: string; phase: "started" }
  | { id: string; phase: "completed"; ok: true; kind: "article"; result: ArticleParserResult }
  | { id: string; phase: "completed"; ok: true; kind: "feed"; result: FeedParserResult }
  | { id: string; phase: "completed"; ok: false; reason: ArticleExtractionError["reason"] | "malformed-feed" | "parser-failed" };
export const ArticleParserResponseSchema = z.union([
  z.strictObject({ id: z.uuid(), phase: z.literal("started") }),
  z.strictObject({
    id: z.uuid(), phase: z.literal("completed"), ok: z.literal(true), kind: z.literal("article"), result: z.strictObject({
      article_text: z.string(), word_count: CountSchema, author: z.string().nullable(), page_title: z.string().nullable(),
      paywall: z.boolean().nullable(), paywall_evidence: z.enum(["json-ld", "configured-marker", "none", "not-observed"]),
      warnings: HarvestDiagnosticsSchema.shape.warnings, quality: ExtractionQualitySchema.nullable(),
      content_evidence: ArticleContentEvidenceSchema.nullable(),
    }),
  }),
  z.strictObject({
    id: z.uuid(), phase: z.literal("completed"), ok: z.literal(true), kind: z.literal("feed"),
    result: z.array(PlannerFeedEntrySchema.extend({ link: z.string().nullable() })),
  }),
  z.strictObject({ id: z.uuid(), phase: z.literal("completed"), ok: z.literal(false),
    reason: z.enum(["missing-document-root", "dom-depth-exceeded", "malformed-feed", "parser-failed"]) }),
]);

declare const self: Worker;
if (!isMainThread) self.onmessage = async (event: MessageEvent<unknown>) => {
  const request = ArticleParserRequestSchema.parse(event.data);
  self.postMessage({ id: request.id, phase: "started" } satisfies ArticleParserResponse);
  let response: ArticleParserResponse;
  try {
    response = request.kind === "feed"
      ? { id: request.id, phase: "completed", ok: true, kind: "feed", result: await parseFeed(request.body) }
      : { id: request.id, phase: "completed", ok: true, kind: "article",
        result: await extractArticle(request.body, request.url, request.config) };
  } catch (error) {
    response = {
      id: request.id, phase: "completed", ok: false,
      reason: error instanceof ArticleExtractionError ? error.reason : error instanceof FeedParseError ? "malformed-feed" : "parser-failed",
    };
  }
  self.postMessage(ArticleParserResponseSchema.parse(response));
};
