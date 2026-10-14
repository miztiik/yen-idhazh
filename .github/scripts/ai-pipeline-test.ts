// .github/scripts/ai-pipeline.ts
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import crypto from "node:crypto";
import { execSync } from "node:child_process";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";

// -------------------------------------------------------------
// 1. UUID v5 GENERATOR (Zero dependencies, RFC 4122 compliant)
// -------------------------------------------------------------
const UUIDV5_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"; // RFC 4122 DNS namespace

function uuidToBytes(uuid: string): Buffer {
  return Buffer.from(uuid.replace(/-/g, ""), "hex");
}

function generateUuidV5(name: string, namespace: string = UUIDV5_NAMESPACE): string {
  const nsBytes = uuidToBytes(namespace);
  const hash = crypto.createHash("sha1");
  hash.update(nsBytes);
  hash.update(Buffer.from(name, "utf8"));
  const digest = hash.digest();

  // Set version to 5 (0101xxxx)
  digest[6] = (digest[6] & 0x0f) | 0x50;
  // Set variant to RFC 4122 (10xxxxxx)
  digest[8] = (digest[8] & 0x3f) | 0x80;

  const hex = digest.subarray(0, 16).toString("hex");
  return [
    hex.substring(0, 8),
    hex.substring(8, 12),
    hex.substring(12, 16),
    hex.substring(16, 20),
    hex.substring(20, 32),
  ].join("-");
}

// -------------------------------------------------------------
// 2. SCHEMAS & INTERFACES
// -------------------------------------------------------------
export interface TokenMetrics {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  duration_ms: number;
  tokens_per_second: number;
}

export interface SummaryStructuredOutput {
  headline: string;
  executive_summary: string;
  key_points: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  compression_ratio: string;
  raw_output: string;
  token_metrics: TokenMetrics;
}

export interface PipelineEvent<T = any> {
  eventId: string; // UUIDv5
  eventType: "INPUT_RECEIVED" | "INFERENCE_STARTED" | "INFERENCE_COMPLETED" | "OUTPUT_STRUCTURED";
  timestamp: string;
  correlationId: string;
  payload: T;
}

// -------------------------------------------------------------
// 3. HARDWARE & SWAP TELEMETRY (L3 Cache + Swappiness)
// -------------------------------------------------------------
function detectL3Cache(): string {
  try {
    const cacheDir = "/sys/devices/system/cpu/cpu0/cache";
    if (fs.existsSync(cacheDir)) {
      for (const idx of fs.readdirSync(cacheDir)) {
        const levelPath = `${cacheDir}/${idx}/level`;
        if (fs.existsSync(levelPath) && fs.readFileSync(levelPath, "utf8").trim() === "3") {
          const raw = fs.readFileSync(`${cacheDir}/${idx}/size`, "utf8").trim();
          let bytes = 0;
          if (raw.endsWith("K")) bytes = parseInt(raw) * 1024;
          else if (raw.endsWith("M")) bytes = parseInt(raw) * 1024 * 1024;
          else bytes = parseInt(raw);
          return `${(bytes / (1024 * 1024)).toFixed(2)} MB (${bytes} bytes)`;
        }
      }
    }
  } catch {}

  try {
    const out = execSync("lscpu", { encoding: "utf8" });
    const match = out.match(/L3 cache:\s*(.+)$/m);
    if (match) return match[1].trim();
  } catch {}

  return "32.00 MB (Estimated EPYC Shared)";
}

function getMemoryAndSwapTelemetry() {
  let swappiness = -1;
  try {
    swappiness = parseInt(fs.readFileSync("/proc/sys/vm/swappiness", "utf8").trim(), 10);
  } catch {}

  let swapTotal = 0;
  let swapFree = 0;
  try {
    const meminfo = fs.readFileSync("/proc/meminfo", "utf8");
    for (const line of meminfo.split("\n")) {
      if (line.startsWith("SwapTotal:")) swapTotal = parseInt(line.split(/\s+/)[1], 10) / 1024;
      if (line.startsWith("SwapFree:")) swapFree = parseInt(line.split(/\s+/)[1], 10) / 1024;
    }
  } catch {}

  let pid: number | null = null;
  try {
    if (fs.existsSync(".llama_server.pid")) {
      pid = parseInt(fs.readFileSync(".llama_server.pid", "utf8").trim(), 10);
    }
  } catch {}

  let vmRss = 0;
  let vmSwap = 0;
  if (pid) {
    try {
      const status = fs.readFileSync(`/proc/${pid}/status`, "utf8");
      for (const line of status.split("\n")) {
        if (line.startsWith("VmRSS:")) vmRss = parseInt(line.split(/\s+/)[1], 10) / 1024;
        if (line.startsWith("VmSwap:")) vmSwap = parseInt(line.split(/\s+/)[1], 10) / 1024;
      }
    } catch {}
  }

  const cpus = os.cpus();
  return {
    runner_name: process.env.RUNNER_NAME || "local-runner",
    shard_id: process.env.SHARD_ID || "shard-1",
    cpu_model: cpus[0]?.model || "unknown",
    cores: cpus.length,
    l3_cache: detectL3Cache(),
    swappiness,
    server_pid: pid,
    server_vm_rss_mb: Math.round(vmRss),
    server_vm_swap_mb: Math.round(vmSwap),
    system_swap_used_mb: Math.round(swapTotal - swapFree),
    system_swap_total_mb: Math.round(swapTotal),
    total_ram_gb: Number((os.totalmem() / 1024 ** 3).toFixed(2)),
  };
}

// -------------------------------------------------------------
// 4. HTTP CLIENT (No Timeout)
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
        timeout: 0,
      },
      (res) => {
        let raw = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            try {
              resolve(JSON.parse(raw));
            } catch {
              reject(new Error(`Invalid JSON: ${raw}`));
            }
          } else {
            reject(new Error(`Server error HTTP ${res.statusCode}: ${raw}`));
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
// 5. EVENT-DRIVEN ORCHESTRATOR
// -------------------------------------------------------------
class AIEventPipeline extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  private correlationId: string;
  private runnerName: string;
  private shardId: string;

  constructor(runnerName: string, shardId: string) {
    super();
    this.runnerName = runnerName;
    this.shardId = shardId;
    this.correlationId = `corr-${Date.now()}`;
  }

  // Generates RFC 4122 UUIDv5 based on runner, shard, epoch ms, and event type
  private createEventId(eventType: string, epochMs: number): string {
    const seed = `runner:${this.runnerName}:shard:${this.shardId}:epoch:${epochMs}:event:${eventType}`;
    return generateUuidV5(seed);
  }

  private logEvent(eventType: PipelineEvent["eventType"], payload: any) {
    const epochMs = Date.now();
    const event: PipelineEvent = {
      eventId: this.createEventId(eventType, epochMs),
      eventType,
      timestamp: new Date(epochMs).toISOString(),
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
    serverUrl = "http://127.0.0.1:9931",
    modelName = "Ornith-1.0-9B"
  ): Promise<SummaryStructuredOutput> {
    const initialTele = getMemoryAndSwapTelemetry();

    // Event 1: Input Ingestion
    this.logEvent("INPUT_RECEIVED", {
      modelName,
      inputText,
      systemPrompt,
      telemetry: initialTele,
    });

    // Event 2: Start Inference
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      serverUrl,
      targetModel: modelName,
      temperature: 0.2,
    });

    const progressInterval = setInterval(() => {
      const elapsed = Math.round((performance.now() - startTime) / 1000);
      const tele = getMemoryAndSwapTelemetry();
      console.log(
        `[PIPELINE] ⏳ Elapsed: ${elapsed}s | RAM RSS: ${tele.server_vm_rss_mb} MB | Process Swap: ${tele.server_vm_swap_mb} MB | Swappiness: ${tele.swappiness}`
      );
    }, 15000);

    let rawContent = "";
    let usage: any = null;

    try {
      const jsonResponse = await postJsonNoTimeout(`${serverUrl}/v1/chat/completions`, {
        messages: [
          {
            role: "system",
            content: `${systemPrompt}
You MUST reply ONLY with a valid, parseable JSON object matching this schema:
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

    const durationMs = Math.round(performance.now() - startTime);
    const finalTele = getMemoryAndSwapTelemetry();

    // Calculate token metrics
    const promptTokens = usage?.prompt_tokens || 0;
    const completionTokens = usage?.completion_tokens || 0;
    const totalTokens = usage?.total_tokens || promptTokens + completionTokens;
    const tokensPerSec = completionTokens > 0
      ? Number(((completionTokens / (durationMs / 1000))).toFixed(2))
      : 0;

    const tokenMetrics: TokenMetrics = {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: totalTokens,
      duration_ms: durationMs,
      tokens_per_second: tokensPerSec,
    };

    // Event 3: Inference Completed
    this.logEvent("INFERENCE_COMPLETED", {
      modelName,
      tokenMetrics,
      finalTelemetry: finalTele,
    });

    // Event 4: Parse Structured Output
    let parsed: any;
    try {
      const match = rawContent.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(match ? match[0] : rawContent);
    } catch {
      parsed = {
        headline: "Document Summary",
        executive_summary: rawContent.trim(),
        key_points: ["Extracted from raw model text"],
        sentiment: "neutral",
      };
    }

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || "Summary Output",
      executive_summary: parsed.executive_summary || rawContent,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      compression_ratio: `${((rawContent.length / inputText.length) * 100).toFixed(1)}%`,
      raw_output: rawContent,
      token_metrics: tokenMetrics,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 6. PUBLISH TO GITHUB STEP SUMMARY & ANNOTATIONS
// -------------------------------------------------------------
function publishStepSummary(
  modelName: string,
  sourceText: string,
  result: SummaryStructuredOutput,
  tele: ReturnType<typeof getMemoryAndSwapTelemetry>,
  events: PipelineEvent[]
) {
  // Output a GitHub Actions ::notice annotation
  console.log(
    `::notice title=AI Pipeline Succeeded (${modelName})::Processed ${result.token_metrics.total_tokens} tokens in ${(result.token_metrics.duration_ms / 1000).toFixed(1)}s (~${result.token_metrics.tokens_per_second} t/s)`
  );

  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const markdown = `
## 🧠 AI Transformer Pipeline Execution Report

### 🖥️ Hardware, Cache & Swap Diagnostics
| Metric | Measured Value | Health Status |
| :--- | :--- | :--- |
| **Model Executed** | \`${modelName}\` | ✅ Loaded |
| **Runner & Shard** | \`${tele.runner_name}\` (Shard: \`${tele.shard_id}\`) | - |
| **CPU Model & Cores** | \`${tele.cpu_model}\` (${tele.cores} vCPUs) | - |
| **L3 Cache Size** | **${tele.l3_cache}** | Hardware Cache |
| **Linux \`vm.swappiness\`** | **\`${tele.swappiness}\`** | ${tele.swappiness <= 10 ? "✅ Low Paging (Optimized)" : "⚠️ High Paging"} |
| **Server Physical RAM (RSS)** | **${tele.server_vm_rss_mb} MB** | In Physical Memory |
| **Server Process in SWAP** | **${tele.server_vm_swap_mb} MB** | ${tele.server_vm_swap_mb > 0 ? "⚠️ Swapping" : "✅ 0 MB (Pure In-RAM)"} |
| **System Total Swap Used** | \`${tele.system_swap_used_mb} MB / ${tele.system_swap_total_mb} MB\` | - |

---

### ⏱️ Token Performance & Latency Telemetry
| Metric | Measured Value |
| :--- | :--- |
| **Prompt (Input) Tokens** | **${result.token_metrics.prompt_tokens} tokens** |
| **Completion (Output) Tokens** | **${result.token_metrics.completion_tokens} tokens** |
| **Total Processed Tokens** | **${result.token_metrics.total_tokens} tokens** |
| **Total Inference Time** | **${(result.token_metrics.duration_ms / 1000).toFixed(2)} seconds** (\`${result.token_metrics.duration_ms} ms\`) |
| **Generation Speed** | **${result.token_metrics.tokens_per_second} tokens/sec** |

---

### 📝 Structured Executive Summary: *"${result.headline}"*

> **Executive Summary:**  
> ${result.executive_summary}

**Key Takeaways:**
${result.key_points.map((p) => `- ${p}`).join("\n")}

| Attribute | Value |
| :--- | :--- |
| **Detected Sentiment** | \`${result.sentiment.toUpperCase()}\` |
| **Compression Ratio** | \`${result.compression_ratio}\` |

---

### 📄 Full Source Input Text
<details>
<summary><b>Click to expand full source input text (${sourceText.length} characters)</b></summary>

\`\`\`text
${sourceText}
\`\`\`

</details>

### 🤖 Full Raw Model Output
<details>
<summary><b>Click to expand raw response text</b></summary>

\`\`\`text
${result.raw_output}
\`\`\`

</details>

---

### ⚡ Event-Driven Audit Trail (UUIDv5)
| Event Type | RFC 4122 UUIDv5 | Timestamp |
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
// 7. MAIN ENTRY POINT
// -------------------------------------------------------------
async function main() {
  const tele = getMemoryAndSwapTelemetry();
  console.log("=== Initial System Diagnostics ===");
  console.log({
    runner: tele.runner_name,
    shard: tele.shard_id,
    cpu: tele.cpu_model,
    l3Cache: tele.l3_cache,
    swappiness: tele.swappiness,
    serverPid: tele.server_pid,
    serverRamRSS: `${tele.server_vm_rss_mb} MB`,
    serverSwap: `${tele.server_vm_swap_mb} MB`,
  });

  const pipeline = new AIEventPipeline(tele.runner_name, tele.shard_id);

  pipeline.on("INPUT_RECEIVED", (e) =>
    console.log(`[EVENT] 📥 Input Received [UUIDv5: ${e.eventId}] (${e.payload.inputText.length} chars)`)
  );
  pipeline.on("INFERENCE_STARTED", (e) =>
    console.log(`[EVENT] 🚀 Dispatched to ${e.payload.targetModel} [UUIDv5: ${e.eventId}]`)
  );
  pipeline.on("INFERENCE_COMPLETED", (e) => {
    const tm: TokenMetrics = e.payload.tokenMetrics;
    console.log(
      `[EVENT] ✅ Completed [UUIDv5: ${e.eventId}] in ${(tm.duration_ms / 1000).toFixed(1)}s (Prompt: ${tm.prompt_tokens}t, Output: ${tm.completion_tokens}t, Speed: ${tm.tokens_per_second} t/s)`
    );
  });
  pipeline.on("OUTPUT_STRUCTURED", (e) =>
    console.log(`[EVENT] 📦 Structured JSON Ready [UUIDv5: ${e.eventId}]`)
  );

  const prompt =
    process.env.PROMPT || "You are an executive summarizer. Output ONLY the requested JSON. Do NOT output thinking tags.";
  const inputText =
    process.env.INPUT_TEXT ||
    "Ornith-1.0 is an open-source model family designed for agentic coding and reasoning tasks. The 9B parameter model delivers high throughput on consumer and continuous integration compute hardware when quantized to 4-bit precision.";
  const serverUrl = process.env.SERVER_URL || "http://127.0.0.1:9931";
  const modelName = process.env.MODEL_NAME || "ornith-1.0-9b-Q4_K_M.gguf";

  try {
    const result = await pipeline.execute(inputText, prompt, serverUrl, modelName);

    console.log("\n============================================================");
    console.log(`📌 Model Used: ${modelName}`);
    console.log(`📊 Tokens: ${result.token_metrics.total_tokens} (Prompt: ${result.token_metrics.prompt_tokens}, Output: ${result.token_metrics.completion_tokens})`);
    console.log(`⚡ Speed: ${result.token_metrics.tokens_per_second} tokens/sec in ${(result.token_metrics.duration_ms / 1000).toFixed(1)}s`);
    console.log(`📌 Headline: ${result.headline}`);
    console.log(`📝 Executive Summary: ${result.executive_summary}`);
    result.key_points.forEach((p) => console.log(`   • ${p}`));
    console.log("============================================================\n");

    const finalTele = getMemoryAndSwapTelemetry();
    publishStepSummary(modelName, inputText, result, finalTele, pipeline.getEventHistory());
    console.log("Pipeline run complete.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
