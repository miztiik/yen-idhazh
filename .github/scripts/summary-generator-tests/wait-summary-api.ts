/** How does the workflow wait for its owned generator's configuration health without duplicating URLs? */
import { setTimeout as wait } from "node:timers/promises";
import { performance } from "node:perf_hooks";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  SUMMARY_GENERATOR_HEALTH_PATH, summaryGeneratorUrl,
} from "../../../services/summary-generator/src/api/api-paths.js";
import { readGeneratorConfig } from "../../../services/summary-generator/src/config/load-generator-config.js";
import { SummaryHealthSchema } from "../../../services/summary-generator/src/schemas/summary-result.schema.js";
import {
  cancelResponseBody, readBoundedText, type CompletionFetch,
} from "../../../services/summary-generator/src/services/request-completion.service.js";
import { loadAnalysisConfig } from "./load-analysis-config.js";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "./declare-event-source.js";

export async function waitSummaryApi(
  configRoot?: string, processId?: number,
  send: CompletionFetch = request => fetch(request),
): Promise<void> {
  const generator = readGeneratorConfig(configRoot);
  const config = loadAnalysisConfig(configRoot);
  const endsAt = performance.now() + config.api_startup_timeout_ms;
  while (performance.now() < endsAt) {
    if (processId !== undefined) process.kill(processId, 0);
    const signal = AbortSignal.timeout(Math.max(1, Math.min(
      config.body_read_timeout_ms, Math.ceil(endsAt - performance.now()),
    )));
    try {
      const response = await send(new Request(summaryGeneratorUrl(generator, SUMMARY_GENERATOR_HEALTH_PATH), {
        redirect: "error", signal,
      }));
      if (!response.ok || response.headers.get("content-type")?.split(";", 1)[0]?.trim() !== "application/json") {
        await cancelResponseBody(response.body, signal);
        throw new Error("The generator is not ready.");
      }
      SummaryHealthSchema.parse(JSON.parse(await readBoundedText(
        response.body, config.max_native_response_bytes, signal,
      )));
      return;
    } catch {
      if (performance.now() >= endsAt) break;
    }
    await wait(Math.min(config.api_poll_interval_ms, Math.max(0, endsAt - performance.now())));
  }
  throw new Error("Summary generator configuration health did not become available.");
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const processId = Number(process.argv[2]);
    if (!Number.isInteger(processId) || processId <= 0) throw new Error("An owned API process ID is required.");
    await waitSummaryApi(process.env.CONFIG_ROOT, processId);
  } catch {
    console.error(JSON.stringify({ code: "SUMMARY_GENERATOR_NOT_READY", source: SUMMARY_GENERATOR_TESTS_EVENT_SOURCE }));
    process.exitCode = 1;
  }
}
