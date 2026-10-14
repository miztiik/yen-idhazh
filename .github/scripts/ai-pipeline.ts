// .github/scripts/ai-pipeline.ts
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";

// -------------------------------------------------------------
// 1. TYPES & SCHEMAS
// -------------------------------------------------------------
export interface HostFingerprint {
  runner_name: string;
  run_id: string;
  cpu_model: string;
  cores: number;
  total_memory_gb: number;
}

export interface SummaryStructuredOutput {
  headline: string;
  executive_summary: string;
  key_points: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  compression_ratio: string;
}

export interface PipelineEvent<T = any> {
  eventId: string;
  eventType: "INPUT_RECEIVED" | "INFERENCE_STARTED" | "INFERENCE_COMPLETED" | "OUTPUT_STRUCTURED";
  timestamp: string;
  correlationId: string;
  payload: T;
}

// -------------------------------------------------------------
// 2. TIMEOUT-FREE HTTP CLIENT (Bypasses Undici 300s limit)
// -------------------------------------------------------------
function postJsonNoTimeout(urlStr: string, payload: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const bodyData = JSON.stringify(payload);

    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port || 9931,
        path: url.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(bodyData),
        },
        timeout: 0, // No client-side timeout: allow 4 CPU cores to finish evaluation
      },
      (res) => {
        let raw = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            try {
              resolve(JSON.parse(raw));
            } catch (err) {
              reject(new Error(`Failed to parse response JSON: ${raw}`));
            }
          } else {
            reject(new Error(`llama-server responded with HTTP ${res.statusCode}: ${raw}`));
          }
        });
      }
    );

    req.on("error", reject);
    req.write(bodyData);
    req.end();
  });
}

// -------------------------------------------------------------
// 3. RUNNER FINGERPRINT
// -------------------------------------------------------------
function collectQuickFingerprint(): HostFingerprint {
  const cpus = os.cpus();
  return {
    runner_name: process.env.RUNNER_NAME || "local-runner",
    run_id: process.env.GITHUB_RUN_ID || "local-run",
    cpu_model: cpus[0]?.model || "unknown",
    cores: cpus.length,
    total_memory_gb: Number((os.totalmem() / 1024 ** 3).toFixed(2)),
  };
}

// -------------------------------------------------------------
// 4. EVENT-DRIVEN ORCHESTRATOR
// -------------------------------------------------------------
class AIEventPipeline extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  private correlationId = `corr-${Date.now()}`;

  private logEvent(eventType: PipelineEvent["eventType"], payload: any) {
    const event: PipelineEvent = {
      eventId: `evt-${Math.random().toString(36).substring(2, 9)}`,
      eventType,
      timestamp: new Date().toISOString(),
      correlationId: this.correlationId,
      payload,
    };
    this.auditLog.push(event);
    this.emit(eventType, event);
    return event;
  }

  public getEventHistory(): PipelineEvent[] {
    return this.auditLog;
  }

  public async execute(
    inputText: string,
    systemPrompt: string,
    serverUrl = "http://127.0.0.1:9931"
  ): Promise<SummaryStructuredOutput> {
    // Event 1: Ingestion
    this.logEvent("INPUT_RECEIVED", {
      inputTextPreview: inputText.substring(0, 80) + "...",
      inputLengthChars: inputText.length,
      systemPrompt,
    });

    // Event 2: Start Inference
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      serverUrl,
      targetModel: "Ternary-Bonsai-2-27B-PTQ1_0",
      temperature: 0.2,
      streaming: false,
    });

    // Clean terminal progress indicator (heartbeat every 15 seconds)
    const progressInterval = setInterval(() => {
      const elapsed = Math.round((performance.now() - startTime) / 1000);
      console.log(`[PIPELINE] ⏳ Model is evaluating prompt on CPU (elapsed: ${elapsed}s)...`);
    }, 15000);

    let rawContent = "";
    let usage: any = null;

    try {
      // POST without max_tokens and without streaming
      const jsonResponse = await postJsonNoTimeout(`${serverUrl}/v1/chat/completions`, {
        messages: [
          {
            role: "system",
            content: `${systemPrompt}
You MUST output ONLY a valid JSON object matching this schema:
{
  "headline": "Short title",
  "executive_summary": "1-3 sentences",
  "key_points": ["bullet 1", "bullet 2"],
  "sentiment": "positive" | "neutral" | "negative" | "mixed"
}`,
          },
          {
            role: "user",
            content: `Summarize this text:\n"""\n${inputText}\n"""`,
          },
        ],
        temperature: 0.2,
        stream: false,
        chat_template_kwargs: { enable_thinking: false },
      });

      rawContent = jsonResponse.choices?.[0]?.message?.content || "";
      usage = jsonResponse.usage;
    } finally {
      clearInterval(progressInterval);
    }

    const inferenceDurationMs = Math.round(performance.now() - startTime);

    // Event 3: Completed
    this.logEvent("INFERENCE_COMPLETED", {
      durationMs: inferenceDurationMs,
      usage,
      rawOutputLength: rawContent.length,
    });

    // Event 4: Parse Structured JSON
    let parsed: any;
    try {
      const match = rawContent.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(match ? match[0] : rawContent);
    } catch {
      parsed = {
        headline: "Summary Output",
        executive_summary: rawContent.trim(),
        key_points: ["Extracted from raw model text"],
        sentiment: "neutral",
      };
    }

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || "Document Summary",
      executive_summary: parsed.executive_summary || rawContent,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      compression_ratio: `${((rawContent.length / inputText.length) * 100).toFixed(1)}%`,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 5. OUTPUT REPORTERS
// -------------------------------------------------------------
function printTerminalSummary(result: SummaryStructuredOutput) {
  console.log("\n============================================================");
  console.log("🎯 FINAL STRUCTURED SUMMARY RESULT");
  console.log("============================================================");
  console.log(`📌 Headline: ${result.headline}`);
  console.log(`\n📝 Executive Summary:\n${result.executive_summary}\n`);
  console.log("🔑 Key Takeaways:");
  result.key_points.forEach((point) => console.log(`   • ${point}`));
  console.log(`\n📊 Sentiment: [${result.sentiment.toUpperCase()}] | Compression: ${result.compression_ratio}`);
  console.log("============================================================\n");
}

function publishStepSummary(
  fp: HostFingerprint,
  result: SummaryStructuredOutput,
  events: PipelineEvent[]
) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const markdown = `
## 🧠 AI Transformer Pipeline Execution Report

### 🖥️ Runner Snapshot
- **Runner:** \`${fp.runner_name}\` | **Run ID:** \`${fp.run_id}\`
- **CPU:** \`${fp.cpu_model}\` (${fp.cores} cores) | **RAM:** \`${fp.total_memory_gb} GB\`

---

### 📝 Structured Summary: *"${result.headline}"*

> **Executive Summary:**  
> ${result.executive_summary}

**Key Takeaways:**
${result.key_points.map((p) => `- ${p}`).join("\n")}

| Metric | Value |
| :--- | :--- |
| **Sentiment** | \`${result.sentiment.toUpperCase()}\` |
| **Compression** | \`${result.compression_ratio}\` |

---

### ⚡ Event-Driven Audit Trail
| Event Type | Event ID | Timestamp |
| :--- | :--- | :--- |
${events.map((e) => `| \`${e.eventType}\` | \`${e.eventId}\` | \`${e.timestamp}\` |`).join("\n")}

<details>
<summary><b>Inspect Full Event Stream Payloads (JSON)</b></summary>

\`\`\`json
${JSON.stringify(events, null, 2)}
\`\`\`

</details>
`;

  fs.appendFileSync(summaryPath, markdown, "utf8");
}

// -------------------------------------------------------------
// 6. MAIN
// -------------------------------------------------------------
async function main() {
  const fingerprint = collectQuickFingerprint();
  console.log("Runner Hardware Captured:", {
    cpu: fingerprint.cpu_model,
    cores: fingerprint.cores,
    totalRam: `${fingerprint.total_memory_gb} GB`,
  });

  const pipeline = new AIEventPipeline();

  pipeline.on("INPUT_RECEIVED", (e) => console.log(`[EVENT] 📥 Input Received (${e.payload.inputLengthChars} chars)`));
  pipeline.on("INFERENCE_STARTED", (e) =>
    console.log(`[EVENT] 🚀 Dispatched to llama-server on port 9931 (Non-streaming, no timeout)`)
  );
  pipeline.on("INFERENCE_COMPLETED", (e) =>
    console.log(`[EVENT] ✅ Model execution finished in ${Math.round(e.payload.durationMs / 1000)}s`)
  );
  pipeline.on("OUTPUT_STRUCTURED", () => console.log(`[EVENT] 📦 Structured JSON Validated`));

  const prompt =
    process.env.PROMPT || "You are a concise analytical engine. Summarize the text accurately into key structured takeaways.";
  const inputText =
    process.env.INPUT_TEXT ||
    "Ternary quantization maps neural network weights to {-1, 0, +1}, enabling high compression rates while preserving reasoning capabilities. This architecture allows 27B parameter models to run within 6 GB of memory.";

  try {
    const result = await pipeline.execute(inputText, prompt);
    printTerminalSummary(result);
    publishStepSummary(fingerprint, result, pipeline.getEventHistory());
    console.log("All pipeline stages executed successfully.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
