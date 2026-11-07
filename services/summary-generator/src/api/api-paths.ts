/** Which fixed first-party paths identify generation and its configuration health? */
import type { GeneratorConfig } from "../config/load-generator-config.js";
// The date identifies this HTTP protocol, not a runtime setting.
export const SUMMARY_HTTP_VERSION = "2026-11-05";
export const GENERATE_SUMMARY_PATH = `/api/${SUMMARY_HTTP_VERSION}/generate-summary`;
export const SUMMARY_GENERATOR_HEALTH_PATH = `/api/${SUMMARY_HTTP_VERSION}/get-summary-generator-health`;

export function summaryGeneratorUrl(
  config: Pick<GeneratorConfig, "hostname" | "port">,
  operation: typeof GENERATE_SUMMARY_PATH | typeof SUMMARY_GENERATOR_HEALTH_PATH,
): string {
  const host = config.hostname === "::1" ? `[${config.hostname}]` : config.hostname;
  return new URL(operation, `http://${host}:${config.port}`).href;
}
