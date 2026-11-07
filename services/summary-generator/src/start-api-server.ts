/** Which committed settings start the independent Bun summary listener? */
import { createSummaryListener } from "./api/create-summary-listener.js";
import { loadGeneratorConfig } from "./config/load-generator-config.js";
import { loadModelRuntime } from "./config/load-model-runtime.js";
import { SUMMARY_GENERATOR_EVENT_SOURCE } from "./declare-event-source.js";

try {
  const selected = loadGeneratorConfig(process.env.CONFIG_ROOT);
  Bun.serve(createSummaryListener({ ...selected, runtime: loadModelRuntime(process.env.CONFIG_ROOT) }));
} catch {
  console.error(JSON.stringify({ code: "SUMMARY_GENERATOR_START_FAILED", source: SUMMARY_GENERATOR_EVENT_SOURCE }));
  process.exitCode = 1;
}
