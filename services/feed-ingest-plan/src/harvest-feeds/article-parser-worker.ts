/** Parse one inert HTML document with the production extractor in a native worker. */
import { z } from "zod";
import { extractArticle, ArticleExtractionError } from "./dom-extractor";
import { ExtractionControlsSchema } from "./extraction-controls";
import { ArticleContentEvidenceSchema, CountSchema, ExtractionQualitySchema, HarvestDiagnosticsSchema, UrlSchema } from "@idhazh/common-contracts";
import { isMainThread } from "node:worker_threads";

export const ArticleParserRequestSchema = z.strictObject({
  id: z.uuid(), body: z.string(), url: UrlSchema,
  config: ExtractionControlsSchema,
});
export type ArticleParserRequest = z.infer<typeof ArticleParserRequestSchema>;
export type ArticleParserResult = Awaited<ReturnType<typeof extractArticle>>;
export type ArticleParserResponse =
  | { id: string; phase: "started" }
  | { id: string; phase: "completed"; ok: true; result: ArticleParserResult }
  | { id: string; phase: "completed"; ok: false; reason: ArticleExtractionError["reason"] | "parser-failed" };
export const ArticleParserResponseSchema = z.union([
  z.strictObject({ id: z.uuid(), phase: z.literal("started") }),
  z.strictObject({
    id: z.uuid(), phase: z.literal("completed"), ok: z.literal(true), result: z.strictObject({
      article_text: z.string(), word_count: CountSchema, author: z.string().nullable(), page_title: z.string().nullable(),
      paywall: z.boolean().nullable(), paywall_evidence: z.enum(["json-ld", "configured-marker", "none", "not-observed"]),
      warnings: HarvestDiagnosticsSchema.shape.warnings, quality: ExtractionQualitySchema.nullable(),
      content_evidence: ArticleContentEvidenceSchema.nullable(),
    }),
  }),
  z.strictObject({ id: z.uuid(), phase: z.literal("completed"), ok: z.literal(false),
    reason: z.enum(["missing-document-root", "dom-depth-exceeded", "parser-failed"]) }),
]);

declare const self: Worker;
if (!isMainThread) self.onmessage = async (event: MessageEvent<unknown>) => {
  const request = ArticleParserRequestSchema.parse(event.data);
  self.postMessage({ id: request.id, phase: "started" } satisfies ArticleParserResponse);
  let response: ArticleParserResponse;
  try {
    response = {
      id: request.id, phase: "completed", ok: true,
      result: await extractArticle(request.body, request.url, request.config),
    };
  } catch (error) {
    response = {
      id: request.id, phase: "completed", ok: false,
      reason: error instanceof ArticleExtractionError ? error.reason : "parser-failed",
    };
  }
  self.postMessage(ArticleParserResponseSchema.parse(response));
};
