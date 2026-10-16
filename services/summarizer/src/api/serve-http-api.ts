// services/summarizer/src/api/serve-http-api.ts
import http from "node:http";
import { loadEnvConfig } from "../config/load-env-config.js";
import { SummarizeRequestSchema } from "../schemas/export-all-schemas.js";
import { PipelineEventBus } from "../services/dispatch-event.service.js";
import { orchestratePipeline } from "../pipeline/orchestrate-pipeline.service.js";
import { getMemorySnapshot, detectL3Cache } from "../services/collect-telemetry.service.js";
import { renderGithubStepSummary } from "../reporters/render-github-summary.reporter.js";

export function createHttpServer(port?: number) {
  const env = loadEnvConfig();
  const listenPort = port || env.PORT;

  const server = http.createServer(async (req, res) => {
    const parsedUrl = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);

    res.setHeader("Content-Type", "application/json");

    // 1. Healthcheck Endpoint
    if (req.method === "GET" && parsedUrl.pathname === "/health") {
      res.writeHead(200);
      res.end(JSON.stringify({ status: "ok", uptime: process.uptime(), memory: getMemorySnapshot() }));
      return;
    }

    // 2. Hardware Diagnostics Endpoint
    if (req.method === "GET" && parsedUrl.pathname === "/api/diagnostics") {
      res.writeHead(200);
      res.end(JSON.stringify({ memory: getMemorySnapshot(), l3Cache: detectL3Cache() }));
      return;
    }

    // 3. Summarization Ingestion API Endpoint
    if (req.method === "POST" && parsedUrl.pathname === "/api/summarize") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", async () => {
        try {
          const rawJson = body ? JSON.parse(body) : {};
          const validationResult = SummarizeRequestSchema.safeParse(rawJson);

          if (!validationResult.success) {
            res.writeHead(400);
            res.end(JSON.stringify({ error: "Invalid request payload", details: validationResult.error.format() }));
            return;
          }

          const eventBus = new PipelineEventBus(env.RUNNER_NAME, env.SHARD_ID);
          const result = await orchestratePipeline(validationResult.data, eventBus, {
            serverUrl: env.SERVER_URL,
            modelName: env.MODEL_NAME,
          });

          // If running inside CI, automatically publish the Step Summary
          if (process.env.GITHUB_STEP_SUMMARY) {
            renderGithubStepSummary(env.MODEL_NAME, result, eventBus.getEventHistory());
          }

          res.writeHead(200);
          res.end(JSON.stringify({ success: true, data: result }));
        } catch (err: any) {
          console.error("[API_ERROR]", err);
          res.writeHead(500);
          res.end(JSON.stringify({ error: "Pipeline execution failed", message: err.message }));
        }
      });
      return;
    }

    // 404 Route
    res.writeHead(404);
    res.end(JSON.stringify({ error: "Not Found" }));
  });

  return {
    server,
    start: () => {
      server.listen(listenPort, () => {
        console.log(`🚀 Summarizer API Server listening on http://127.0.0.1:${listenPort}`);
      });
    },
  };
}