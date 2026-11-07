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
}).strict();
export const CoverageApiComponentSchema = z.enum(["hhem", "unieval", "coverage"]);
export const CoverageLoggingSchema = z.object({
  level: z.enum(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
  max_event_bytes: z.number().int().positive(),
}).strict();
const ApiSharedSettings = {
  version: z.literal("2026-11-07"),
  logging: CoverageLoggingSchema,
  log_directory: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._/-]*$/)
    .refine(value => value.split("/").every(part => part !== "" && part !== "." && part !== "..")),
  shutdown_timeout_ms: z.number().int().positive(),
};
export const CoverageApiSettingsSchema = z.object({
  ...ApiSharedSettings,
  listener: CoverageListenerSchema,
  enabled_routes: z.array(CoverageApiComponentSchema)
    .refine(routes => new Set(routes).size === routes.length),
}).strict();
export const CoverageDeploymentSettingsSchema = z.object({
  ...ApiSharedSettings,
  listeners: z.object({
    hhem: CoverageListenerSchema,
    unieval: CoverageListenerSchema,
    coverage: CoverageListenerSchema,
  }).strict(),
}).strict().superRefine((settings, context) => {
  const listeners = Object.values(settings.listeners);
  if (new Set(listeners.map(listener => `${listener.host}:${listener.port}`)).size !== listeners.length) {
    context.addIssue({ code: "custom", message: "Scorer API listeners must not collide" });
  }
});
export const CoverageApiConfigurationSchema = z.union([
  CoverageDeploymentSettingsSchema, CoverageApiSettingsSchema,
]);
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

export function resolveCoverageApiSettings(value: unknown) {
  const api = CoverageApiConfigurationSchema.parse(value);
  if ("listeners" in api) {
    return CoverageApiSettingsSchema.parse({
      version: api.version,
      listener: api.listeners.coverage,
      enabled_routes: ["coverage"],
      logging: api.logging,
      log_directory: api.log_directory,
      shutdown_timeout_ms: api.shutdown_timeout_ms,
    });
  }
  return CoverageApiSettingsSchema.parse({ ...api, enabled_routes: ["coverage"] });
}

export function readCoverageSettings(
  root = fileURLToPath(new URL("../../", import.meta.url)),
) {
  const api = resolveCoverageApiSettings(JSON.parse(
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
