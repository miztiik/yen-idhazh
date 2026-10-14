// .github/scripts/ai-pipeline.ts
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";
import { getLlama, LlamaChatSession, defineChatSessionFunction } from "node-llama-cpp";

// -------------------------------------------------------------
// 1. TYPE DEFINITIONS & EVENT PAYLOADS
// -------------------------------------------------------------
export interface PipelineConfig {
  modelPath: string;
  systemPrompt: string;
  inputText: string;
  maxTokens: number;
  temperature: number;
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
// 2. HOST FINGERPRINT COLLECTOR
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

  public async execute(config: PipelineConfig): Promise<SummaryStructuredOutput> {
    // Stage 1: Input Received Event
    this.logEvent("INPUT_RECEIVED", {
      inputTextPreview: config.inputText.substring(0, 100) + "...",
      inputLengthChars: config.inputText.length,
      systemPrompt: config.systemPrompt,
    });

    // Stage 2: Inference Setup & Dispatch
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      model: path.basename(config.modelPath),
      temperature: config.temperature,
      maxTokens: config.maxTokens,
    });

    // Initialize node-llama-cpp
    const llama = await getLlama();
    const model = await llama.loadModel({
      modelPath: config.modelPath,
    });

    const context = await model.createContext({
      contextSize: 2048, // Compact context size to fit in runner RAM + swap
      batchSize: 256,
    });

    const session = new LlamaChatSession({
      contextSequence: context.getSequence(),
      systemPrompt: `${config.systemPrompt}
You MUST reply ONLY with a valid, strictly parseable JSON object matching this schema:
{
  "headline": "Short title",
  "executive_summary": "1-3 sentences",
  "key_points": ["bullet 1", "bullet 2"],
  "sentiment": "positive" | "neutral" | "negative" | "mixed"
}`,
    });

    // Run inference
    const rawResponse = await session.prompt(
      `Text to summarize:\n"""\n${config.inputText}\n"""`,
      {
        maxTokens: config.maxTokens,
        temperature: config.temperature,
      }
    );

    const inferenceDurationMs = Math.round(performance.now() - startTime);

    this.logEvent("INFERENCE_COMPLETED", {
      inferenceDurationMs,
      rawOutputLength: rawResponse.length,
    });

    // Stage 3: Parse and Structure Output
    let parsed: any;
    try {
      const jsonMatch = rawResponse.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(jsonMatch ? jsonMatch[0] : rawResponse);
    } catch {
      parsed = {
        headline: "Summary Output",
        executive_summary: rawResponse.trim(),
        key_points: ["Extracted from raw model response"],
        sentiment: "neutral",
      };
    }

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || "Document Summary",
      executive_summary: parsed.executive_summary || rawResponse,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      compression_ratio: `${((rawResponse.length / config.inputText.length) * 100).toFixed(1)}%`,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);

    return structuredResult;
  }
}

// -------------------------------------------------------------
// 4. MARKDOWN SUMMARY WRITER (GITHUB ACTIONS STEP SUMMARY)
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
// 5. MAIN ENTRY POINT
// -------------------------------------------------------------
async function main() {
  const fingerprint = collectQuickFingerprint();
  console.log("Host Fingerprint:", fingerprint);

  const modelPath = process.env.MODEL_PATH || "./models/Ternary-Bonsai-2-27B-PTQ1_0.gguf";

  const config: PipelineConfig = {
    modelPath,
    systemPrompt:
      process.env.PROMPT ||
      "You are a high-speed summarization engine. Distill the text into concise, factual points.",
    inputText:
      process.env.INPUT_TEXT ||
      `GitHub Actions is a continuous integration and continuous delivery (CI/CD) platform that allows you to automate your build, test, and deployment pipeline. You can create workflows that build and test every pull request to your repository, or deploy merged pull requests to production. GitHub Actions goes beyond just DevOps and lets you run workflows when other events happen in your repository. For example, you can run a workflow to automatically add the appropriate labels whenever someone creates a new issue in your repository.`,
    maxTokens: 512,
    temperature: 0.2,
  };

  const pipeline = new AIEventPipeline();

  // Attach event listeners for real-time observability
  pipeline.on("INPUT_RECEIVED", (e) => console.log(`[EVENT] Input Received: ${e.eventId}`));
  pipeline.on("INFERENCE_STARTED", (e) => console.log(`[EVENT] Inference Started on ${e.payload.model}`));
  pipeline.on("INFERENCE_COMPLETED", (e) => console.log(`[EVENT] Inference Finished in ${e.payload.inferenceDurationMs}ms`));
  pipeline.on("OUTPUT_STRUCTURED", (e) => console.log(`[EVENT] Structured Payload Ready`));

  try {
    const result = await pipeline.execute(config);
    const events = pipeline.getEventHistory();

    // Write results to GitHub Actions markdown summary
    publishStepSummary(fingerprint, result, events);
    console.log("Execution successfully completed.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
