import { loadEnvConfig } from "./config/load-env-config.js";
import { PipelineEventBus } from "./services/dispatch-event.service.js";
import { orchestratePipeline } from "./pipeline/orchestrate-pipeline.service.js";
import { renderGithubStepSummary } from "./reporters/render-github-summary.reporter.js";
import { detectL3Cache } from "./services/collect-telemetry.service.js";

async function runCli(): Promise<void> {
  const env = loadEnvConfig();

  console.log("=== AI Inference Pipeline CLI Startup ===");
  console.log({
    runner: env.RUNNER_NAME,
    shard: env.SHARD_ID,
    model: env.modelRuntime.request.model,
    serverUrl: env.modelRuntime.base_url,
    hasUrl: Boolean(env.URL),
    hasInputText: Boolean(env.INPUT_TEXT),
    l3Cache: detectL3Cache(),
  });

  const eventBus = new PipelineEventBus(env.RUNNER_NAME, env.SHARD_ID);

  try {
    const result = await orchestratePipeline(
      {
        url: env.URL,
        input_text: env.INPUT_TEXT,
        system_prompt: env.PROMPT,
      },
      eventBus,
      env.modelRuntime
    );

    console.log("\n============================================================");
    console.log("🎯 PARSED & ZOD-VALIDATED RESULT:");
    console.log("============================================================");
    console.log(JSON.stringify(result, null, 2));
    console.log("============================================================\n");

    renderGithubStepSummary(env.modelRuntime.request.model, result, eventBus.getEventHistory());
    console.log("✅ CLI run completed successfully. Telemetry saved to pipeline-events.jsonl");
  } catch (err: any) {
    console.error("❌ Pipeline run terminated with error:", err.message);
    process.exit(1);
  }
}

runCli();