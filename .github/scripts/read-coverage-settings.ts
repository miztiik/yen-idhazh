/** Which bounded caller settings come from the evaluator's actual named configuration files? */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "../../packages/common-contracts/node_modules/zod/index.js";

// These small consumer projections are bound to the native Python models in the coverage tests.
export const CoverageListenerSchema = z.object({
  host: z.enum(["127.0.0.1", "::1"]),
  port: z.number().int().min(1).max(65535),
  max_body_bytes: z.number().int().positive(),
  body_read_timeout_ms: z.number().int().positive(),
});
export const CoverageApiSettingsSchema = z.object({
  listener: CoverageListenerSchema,
}).passthrough();
export const CoverageScorerSettingsSchema = z.object({
  evaluation: z.object({ timeout_ms: z.number().int().positive() }),
  queue: z.object({ wait_timeout_ms: z.number().int().positive() }).passthrough(),
  worker: z.object({
    shutdown_timeout_ms: z.number().int().positive(),
    max_reply_bytes: z.number().int().positive(),
  }).passthrough(),
}).passthrough();

// First-party route dates identify the protocol rather than the independently versioned payloads.
export const COVERAGE_EVALUATION_PATH = "/api/2026-11-05/evaluate-summary-coverage";

export function readCoverageSettings(
  root = fileURLToPath(new URL("../../", import.meta.url)),
) {
  const api = CoverageApiSettingsSchema.parse(JSON.parse(
    readFileSync(join(root, "config", "summary-evals", "api.json"), "utf8"),
  ));
  const scorer = CoverageScorerSettingsSchema.parse(JSON.parse(
    readFileSync(join(root, "config", "summary-evals", "unieval-evaluator", "coverage.json"), "utf8"),
  ));
  const host = api.listener.host === "::1" ? "[::1]" : api.listener.host;
  return {
    evaluateUrl: `http://${host}:${api.listener.port}${COVERAGE_EVALUATION_PATH}`,
    maxRequestBytes: api.listener.max_body_bytes,
    maxResponseBytes: scorer.worker.max_reply_bytes,
    requestTimeoutMs: api.listener.body_read_timeout_ms + scorer.queue.wait_timeout_ms
      + scorer.evaluation.timeout_ms + scorer.worker.shutdown_timeout_ms,
  };
}
