/** How does each HTTP request retain its own pipeline context and event history? */
import http from "node:http";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { readTraceContext, writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import type { ModelRuntime } from "../config/load-model-runtime.js";
import { SummarizeRequestSchema } from "../schemas/export-all-schemas.js";
import { PipelineEventBus } from "../services/dispatch-event.service.js";
import { orchestratePipeline } from "../pipeline/orchestrate-pipeline.service.js";
import { getMemorySnapshot, detectL3Cache } from "../services/collect-telemetry.service.js";
import { renderGithubStepSummary } from "../reporters/render-github-summary.reporter.js";

type SummarizerServerOptions = {
  port: number;
  runtime: ModelRuntime;
  eventSource: string;
  eventFilePath?: string;
};

export function createHttpServer(options: SummarizerServerOptions) {
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
      const incoming = readTraceContext(req.headers);
      const context = incoming ? createChildContext(incoming) : createRootContext();
      for (const [name, value] of Object.entries(writeTraceContext(context))) {
        res.setHeader(name, value);
      }
      const eventBus = new PipelineEventBus(options.eventSource, options.eventFilePath);
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

          const result = await orchestratePipeline(
            validationResult.data, eventBus, options.runtime, context,
          );

          // If running inside CI, automatically publish the Step Summary
          if (process.env.GITHUB_STEP_SUMMARY) {
            renderGithubStepSummary(options.runtime.request.model, result, eventBus.getEventHistory());
          }

          res.writeHead(200);
          res.end(JSON.stringify({ success: true, data: result }));
        } catch (err) {
          console.error(JSON.stringify({
            code: "SUMMARIZE_FAILED", traceId: context.traceId, spanId: context.spanId,
          }));
          res.writeHead(500);
          res.end(JSON.stringify({
            error: "Pipeline execution failed",
            message: err instanceof Error ? err.message : "Unknown pipeline failure.",
          }));
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
      server.listen(options.port, () => {
        console.error(JSON.stringify({ code: "SUMMARIZER_LISTENING", port: options.port }));
      });
    },
  };
}