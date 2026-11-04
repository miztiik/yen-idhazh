/** How does one CLI invocation return a summary and retain its private events? */
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { loadEventSources } from "@idhazh/common-contracts/load-event-sources";
import { loadEnvConfig } from "./config/load-env-config.js";
import { PipelineEventBus } from "./services/dispatch-event.service.js";
import { orchestratePipeline } from "./pipeline/orchestrate-pipeline.service.js";
import { renderGithubStepSummary } from "./reporters/render-github-summary.reporter.js";

async function runCli(): Promise<void> {
  const context = createRootContext();

  try {
    const env = loadEnvConfig();
    const sources = await loadEventSources(new URL("../../../config/typescript-event-sources.json", import.meta.url));
    const eventBus = new PipelineEventBus(sources.summarizer);
    const result = await orchestratePipeline(
      {
        url: env.URL,
        input_text: env.INPUT_TEXT,
        system_prompt: env.PROMPT,
      },
      eventBus,
      env.modelRuntime,
      context,
    );

    process.stdout.write(JSON.stringify(result) + "\n");

    renderGithubStepSummary(env.modelRuntime.request.model, result, eventBus.getEventHistory());
    console.error(JSON.stringify({
      code: "SUMMARIZE_COMPLETED",
      traceId: context.traceId,
      spanId: context.spanId,
      events: eventBus.getEventHistory().length,
    }));
  } catch {
    console.error(JSON.stringify({
      code: "SUMMARIZE_FAILED", traceId: context.traceId, spanId: context.spanId,
    }));
    process.exitCode = 1;
  }
}

await runCli();