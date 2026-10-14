// .github/scripts/ai-pipeline.ts
import fs from "node:fs";
import os from "node:os";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";

// -------------------------------------------------------------
// 1. TYPES & SCHEMAS
// -------------------------------------------------------------
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
// 2. RUNNER FINGERPRINT
// -------------------------------------------------------------
function collectQuickFingerprint() {
  const cpus = os.cpus();
  return {
    runner: process.env.RUNNER_NAME || "local",
    os: `${os.platform()} ${os.release()} (${os.arch()})`,
    cpuModel: cpus[0]?.model || "unknown",
    cores: cpus.length,
    totalRamGB: (os.totalmem() / 1024 ** 3).toFixed(2),
    freeRamGB: (os.freemem() / 1024 ** 3).toFixed(2),
  };
}

// -------------------------------------------------------------
// 3. EVENT-DRIVEN ORCHESTRATOR
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
    serverUrl = "http://127.0.0.1:8080"
  ): Promise<SummaryStructuredOutput> {
    // Event 1: Ingestion
    this.logEvent("INPUT_RECEIVED", {
      inputTextPreview: inputText.substring(0, 100) + "...",
      inputLengthChars: inputText.length,
      systemPrompt,
    });

    // Event 2: Start Inference
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      serverUrl,
      targetModel: "Ternary-Bonsai-2-27B-PTQ1_0",
    });

    // Call Prism llama-server via OpenAI-compatible endpoint
    const response = await fetch(`${serverUrl}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [
          {
            role: "system",
            content: `${systemPrompt}
You MUST output ONLY a valid, parseable JSON object matching this schema:
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
        max_tokens: 300,
        // Disable extended reasoning mode for fast CI turnaround
        chat_template_kwargs: { enable_thinking: false },
      }),
    });

    if (!response.ok) {
      throw new Error(`llama-server responded with HTTP ${response.status}: ${await response.text()}`);
    }

    const jsonResponse: any = await response.json();
    const rawContent = jsonResponse.choices?.[0]?.message?.content || "";
    const inferenceDurationMs = Math.round(performance.now() - startTime);

    // Event 3: Inference Completed
    this.logEvent("INFERENCE_COMPLETED", {
      inferenceDurationMs,
      usage: jsonResponse.usage,
      rawOutputLength: rawContent.length,
    });

    // Event 4: Parse & Validate Structured Schema
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
      headline: parsed.headline || "Summary Report",
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
// 4. MARKDOWN REPORTER
// -------------------------------------------------------------
function publishStepSummary(
  fingerprint: ReturnType<typeof collectQuickFingerprint>,
  result: SummaryStructuredOutput,
  events: PipelineEvent[]
) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const markdown = `
## 🧠 AI Transformer Pipeline Execution Report

### 🖥️ Runner Host Snapshot
| Metric | Value |
| :--- | :--- |
| **Runner** | \`${fingerprint.runner}\` |
| **OS / Arch** | \`${fingerprint.os}\` |
| **CPU Model** | \`${fingerprint.cpuModel}\` (${fingerprint.cores} cores) |
| **RAM (Total / Free)** | \`${fingerprint.totalRamGB} GB\` / \`${fingerprint.freeRamGB} GB\` |

---

### 📝 Structured Model Summary: *"${result.headline}"*

> **Executive Summary:**  
> ${result.executive_summary}

**Key Takeaways:**
${result.key_points.map((p) => `- ${p}`).join("\n")}

| Attribute | Value |
| :--- | :--- |
| **Detected Sentiment** | \`${result.sentiment.toUpperCase()}\` |
| **Compression Ratio** | \`${result.compression_ratio}\` |

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
// 5. MAIN
// -------------------------------------------------------------
async function main() {
  const fingerprint = collectQuickFingerprint();
  const pipeline = new AIEventPipeline();

  pipeline.on("INPUT_RECEIVED", (e) => console.log(`[EVENT] Input Received: ${e.eventId}`));
  pipeline.on("INFERENCE_STARTED", (e) => console.log(`[EVENT] Inference Started on ${e.payload.targetModel}`));
  pipeline.on("INFERENCE_COMPLETED", (e) => console.log(`[EVENT] Inference Completed in ${e.payload.inferenceDurationMs}ms`));
  pipeline.on("OUTPUT_STRUCTURED", () => console.log(`[EVENT] Structured Payload Ready`));

  const prompt = process.env.PROMPT || "You are a concise analytical engine. Summarize the text accurately.";
  const inputText =
    process.env.INPUT_TEXT ||
    "Ternary quantization maps neural network weights to {-1, 0, +1}, enabling high compression rates while preserving reasoning capabilities. This architecture allows 27B parameter models to run within 6 GB of memory.";

  try {
    const result = await pipeline.execute(inputText, prompt);
    publishStepSummary(fingerprint, result, pipeline.getEventHistory());
    console.log("Pipeline run complete.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
