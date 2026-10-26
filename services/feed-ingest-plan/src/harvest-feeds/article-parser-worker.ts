/** Parse one inert HTML document with the production extractor in a native worker. */
import { z } from "zod";
import { extractArticle, ArticleExtractionError } from "./dom-extractor";
import { ExtractionControlsSchema } from "./extraction-controls";
import { UrlSchema } from "@idhazh/common-contracts";
import { isMainThread } from "node:worker_threads";

export const ArticleParserRequestSchema = z.strictObject({
  id: z.uuid(), body: z.string(), url: UrlSchema,
  config: ExtractionControlsSchema, form: z.enum(["article", "abstract"]),
});
export type ArticleParserRequest = z.infer<typeof ArticleParserRequestSchema>;
export type ArticleParserResult = ReturnType<typeof extractArticle>;
export type ArticleParserResponse =
  | { id: string; phase: "started" }
  | { id: string; phase: "completed"; ok: true; result: ArticleParserResult }
  | { id: string; phase: "completed"; ok: false; reason: ArticleExtractionError["reason"] | "parser-failed" };

declare const self: Worker;
if (!isMainThread) self.onmessage = (event: MessageEvent<unknown>) => {
  const request = ArticleParserRequestSchema.parse(event.data);
  self.postMessage({ id: request.id, phase: "started" } satisfies ArticleParserResponse);
  let response: ArticleParserResponse;
  try {
    response = {
      id: request.id, phase: "completed", ok: true,
      result: extractArticle(request.body, request.url, request.config, request.form),
    };
  } catch (error) {
    response = {
      id: request.id, phase: "completed", ok: false,
      reason: error instanceof ArticleExtractionError ? error.reason : "parser-failed",
    };
  }
  self.postMessage(response);
};
