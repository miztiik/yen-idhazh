/** How does one full-analysis CLI invocation retain its validated result and private events? */
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "./declare-event-source.js";
import { loadEnvConfig } from "./load-analysis-config.js";
import { GeneratorLoggingSchema } from "../../../services/summary-generator/src/config/load-generator-config.js";
import { PipelineEventBus } from "./publish-events.js";
import { orchestratePipeline } from "./orchestrate-analysis.js";
import { renderGithubStepSummary } from "./render-report.js";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import type { Writable } from "node:stream";
import type { CompletionFetch } from "../../../services/summary-generator/src/services/request-completion.service.js";

export async function runCli(
  send?: CompletionFetch, output: Pick<Writable, "write"> = process.stdout,
  options: {
    environment?: NodeJS.ProcessEnv;
    eventFilePath?: string;
    diagnostic?: Pick<Writable, "write">;
  } = {},
): Promise<boolean> {
  const context = createRootContext();
  const diagnostic = options.diagnostic ?? process.stderr;

  try {
    const env = loadEnvConfig(options.environment);
    const eventBus = new PipelineEventBus(
      SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, options.eventFilePath, env.workflow.logging, diagnostic,
    );
    const result = await orchestratePipeline(
      {
        url: env.URL,
        input_text: env.INPUT_TEXT,
        system_prompt: env.PROMPT,
      },
      eventBus,
      env.modelRuntime,
      context,
      send,
      { config: env.workflow, analysisPrompt: env.analysisPrompt },
    );

    output.write(JSON.stringify(result) + "\n");

    const levels = GeneratorLoggingSchema.shape.level.options;
    renderGithubStepSummary(env.modelRuntime.request.model, result, eventBus.getEventHistory(), {
      summaryPath: env.GITHUB_STEP_SUMMARY, diagnostic,
      writeNotice: levels.indexOf(env.workflow.logging.level) <= levels.indexOf("INFO"),
    });
    eventBus.recordDiagnostic({
      code: "SUMMARIZE_COMPLETED",
      traceId: context.traceId,
      spanId: context.spanId,
      events: eventBus.getEventHistory().length,
    });
    return true;
  } catch {
    diagnostic.write(JSON.stringify({
      code: "SUMMARIZE_FAILED", traceId: context.traceId, spanId: context.spanId,
    }) + "\n");
    return false;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!await runCli()) process.exitCode = 1;
}