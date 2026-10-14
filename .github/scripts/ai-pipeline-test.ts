// .github/scripts/ai-pipeline.ts
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import crypto from "node:crypto";
import { execSync } from "node:child_process";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";

// Defuddle & Linkedom for clean DOM extraction
import { parseHTML } from "linkedom";
import { Defuddle } from "defuddle/node";

// -------------------------------------------------------------
// 1. UUID v5 GENERATOR (RFC 4122 compliant)
// -------------------------------------------------------------
const UUIDV5_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

function uuidToBytes(uuid: string): Buffer {
  return Buffer.from(uuid.replace(/-/g, ""), "hex");
}

function generateUuidV5(name: string, namespace: string = UUIDV5_NAMESPACE): string {
  const nsBytes = uuidToBytes(namespace);
  const hash = crypto.createHash("sha1");
  hash.update(nsBytes);
  hash.update(Buffer.from(name, "utf8"));
  const digest = hash.digest();

  digest[6] = (digest[6] & 0x0f) | 0x50; // Version 5
  digest[8] = (digest[8] & 0x3f) | 0x80; // Variant RFC 4122

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
export interface IngestionResult {
  sourceUrl: string;
  success: boolean;
  title: string;
  extractedText: string;
  wordCount: number;
  error?: string;
}

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
  source_info: IngestionResult;
  token_metrics: TokenMetrics;
}

export interface PipelineEvent<T = any> {
  eventId: string;
  eventType:
    | "URL_INGESTION_STARTED"
    | "URL_INGESTION_COMPLETED"
    | "URL_INGESTION_FAILED"
    | "INPUT_RECEIVED"
    | "INFERENCE_STARTED"
    | "INFERENCE_COMPLETED"
    | "OUTPUT_STRUCTURED";
  timestamp: string;
  correlationId: string;
  payload: T;
}

export interface ExecuteOptions {
  url?: string;
  fallbackText: string;
  systemPrompt: string;
  serverUrl?: string;
  modelName?: string;
}

// -------------------------------------------------------------
// 3. DEFUDDLE URL INGESTION (With Graceful Fallback)
// -------------------------------------------------------------
async function extractWithDefuddle(url: string): Promise<IngestionResult> {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; DefuddleScraper/1.0)",
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
      signal: AbortSignal.timeout(15000), // 15s timeout
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const html = await res.text();
    const { document } = parseHTML(html);
    const result: any = await Defuddle(document, url, { markdown: true });

    const content = result.content?.trim() || "";
    if (!content) {
      throw new Error("Defuddle returned empty content for the URL");
    }

    return {
      sourceUrl: url,
      success: true,
      title: result.title || "Web Document",
      extractedText: content,
      wordCount: content.split(/\s+/).length,
    };
  } catch (err: any) {
    return {
      sourceUrl: url,
      success: false,
      title: "Extraction Failed",
      extractedText: "",
      wordCount: 0,
      error: err.message || String(err),
    };
  }
}

// -------------------------------------------------------------
// 4. HARDWARE & SWAP TELEMETRY
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
// 5. TIMEOUT-FREE HTTP POST CLIENT
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
              reject(new Error(`Invalid JSON response: ${raw}`));
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
// 6. EVENT-DRIVEN ORCHESTRATOR CLASS (API-READY)
// -------------------------------------------------------------
export class AIEventPipeline extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  private correlationId: string;
  private runnerName: string;
  private shardId: string;

  constructor(runnerName = "runner-1", shardId = "shard-1") {
    super();
    this.runnerName = runnerName;
    this.shardId = shardId;
    this.correlationId = `corr-${Date.now()}`;
  }

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

  public async execute(options: ExecuteOptions): Promise<SummaryStructuredOutput> {
    const {
      url,
      fallbackText,
      systemPrompt,
      serverUrl = "http://127.0.0.1:9931",
      modelName = "ornith-1.0-9b-Q4_K_M.gguf",
    } = options;

    let targetText = fallbackText;
    let ingestion: IngestionResult = {
      sourceUrl: "raw-text-input",
      success: true,
      title: "Direct Input Text",
      extractedText: fallbackText,
      wordCount: fallbackText.split(/\s+/).length,
    };

    // Stage 1: Defuddle URL Ingestion (If URL is provided)
    if (url && url.trim().length > 0) {
      this.logEvent("URL_INGESTION_STARTED", { url });
      ingestion = await extractWithDefuddle(url);

      if (ingestion.success) {
        this.logEvent("URL_INGESTION_COMPLETED", {
          url,
          title: ingestion.title,
          wordCount: ingestion.wordCount,
          preview: ingestion.extractedText.substring(0, 100) + "...",
        });
        targetText = ingestion.extractedText;
      } else {
        // Graceful Failure: Emit failure event and proceed with fallback text
        this.logEvent("URL_INGESTION_FAILED", {
          url,
          error: ingestion.error,
          fallbackLength: fallbackText.length,
        });
        targetText = fallbackText;
      }
    }

    // Safety: Trim to ~3500 words to ensure context fit
    const words = targetText.split(/\s+/);
    if (words.length > 3500) {
      targetText = words.slice(0, 3500).join(" ") + "\n\n[...Truncated to fit context window...]";
    }

    // Stage 2: Ingested Input Confirmation
    this.logEvent("INPUT_RECEIVED", {
      modelName,
      title: ingestion.title,
      wordCount: words.length,
      usedFallback: !ingestion.success && Boolean(url),
    });

    // Stage 3: Inference Dispatch
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      serverUrl,
      targetModel: modelName,
      temperature: 0.2,
    });

    const progressTimer = setInterval(() => {
      const elapsed = Math.round((performance.now() - startTime) / 1000);
      const tele = getMemoryAndSwapTelemetry();
      console.log(
        `[PIPELINE] ⏳ Elapsed: ${elapsed}s | RAM RSS: ${tele.server_vm_rss_mb} MB | Swap: ${tele.server_vm_swap_mb} MB | Swappiness: ${tele.swappiness}`
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
            content: `Document Title: ${ingestion.title}\n\nContent:\n"""\n${targetText}\n"""`,
          },
        ],
        temperature: 0.2,
        stream: false,
        chat_template_kwargs: { enable_thinking: false },
      });

      rawContent = jsonResponse.choices?.[0]?.message?.content || "";
      usage = jsonResponse.usage;
    } finally {
      clearInterval(progressTimer);
    }

    const durationMs = Math.round(performance.now() - startTime);

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

    // Stage 4: Inference Completed
    this.logEvent("INFERENCE_COMPLETED", {
      modelName,
      tokenMetrics,
      finalTelemetry: getMemoryAndSwapTelemetry(),
    });

    // Stage 5: Parse Structured Schema
    let parsed: any;
    try {
      const match = rawContent.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(match ? match[0] : rawContent);
    } catch {
      parsed = {
        headline: ingestion.title || "Document Summary",
        executive_summary: rawContent.trim(),
        key_points: ["Extracted from raw model text"],
        sentiment: "neutral",
      };
    }

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || ingestion.title || "Summary Output",
      executive_summary: parsed.executive_summary || rawContent,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      compression_ratio: `${((rawContent.length / targetText.length) * 100).toFixed(1)}%`,
      raw_output: rawContent,
      source_info: ingestion,
      token_metrics: tokenMetrics,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 7. GITHUB STEP SUMMARY REPORTER
// -------------------------------------------------------------
function publishStepSummary(
  modelName: string,
  result: SummaryStructuredOutput,
  tele: ReturnType<typeof getMemoryAndSwapTelemetry>,
  events: PipelineEvent[]
) {
  console.log(
    `::notice title=AI Pipeline Succeeded (${modelName})::Processed ${result.token_metrics.total_tokens} tokens in ${(result.token_metrics.duration_ms / 1000).toFixed(1)}s (~${result.token_metrics.tokens_per_second} t/s)`
  );

  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const markdown = `
## 🧠 AI Transformer Pipeline Execution Report

### 🌐 Ingestion Source Diagnostics (Defuddle)
| Parameter | Value |
| :--- | :--- |
| **Source URL** | ${result.source_info.sourceUrl !== "raw-text-input" ? `[${result.source_info.sourceUrl}](${result.source_info.sourceUrl})` : "Raw Text Input"} |
| **Ingestion Status** | ${result.source_info.success ? "✅ Successfully Cleaned & Parsed via `defuddle/node`" : `⚠️ Fallback Used (${result.source_info.error})`} |
| **Extracted Document Title** | **${result.source_info.title}** |
| **Word Count** | \`${result.source_info.wordCount} words\` |

---

### 🖥️ Hardware, Cache & Swap Diagnostics
| Metric | Measured Value | Health Status |
| :--- | :--- | :--- |
| **Model Executed** | \`${modelName}\` | ✅ Active |
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
| **Total Inference Time** | **${(result.token_metrics.duration_ms / 1000).toFixed(2)}s** (\`${result.token_metrics.duration_ms} ms\`) |
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

### 📄 Cleaned Source Content (via Defuddle)
<details>
<summary><b>Click to expand extracted content (${result.source_info.wordCount} words)</b></summary>

\`\`\`markdown
${result.source_info.extractedText || "No source text available"}
\`\`\`

</details>

### 🤖 Raw Model Output Text
<details>
<summary><b>Click to expand raw response</b></summary>

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
// 8. CLI / WORKFLOW ENTRY POINT
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
  });

  const pipeline = new AIEventPipeline(tele.runner_name, tele.shard_id);

  // Real-time lifecycle event listeners
  pipeline.on("URL_INGESTION_STARTED", (e) =>
    console.log(`[EVENT] 🌐 Scraping URL with Defuddle [UUIDv5: ${e.eventId}] -> ${e.payload.url}`)
  );
  pipeline.on("URL_INGESTION_COMPLETED", (e) =>
    console.log(`[EVENT] ✅ Defuddle Ingested: "${e.payload.title}" (${e.payload.wordCount} words) [UUIDv5: ${e.eventId}]`)
  );
  pipeline.on("URL_INGESTION_FAILED", (e) =>
    console.log(`[EVENT] ⚠️ Defuddle Failed (${e.payload.error}). Falling back to text. [UUIDv5: ${e.eventId}]`)
  );
  pipeline.on("INPUT_RECEIVED", (e) =>
    console.log(`[EVENT] 📥 Input Prepared [UUIDv5: ${e.eventId}] (Used Fallback: ${e.payload.usedFallback})`)
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

  const url = process.env.URL || "https://en.wikipedia.org/wiki/Ternary_numeral_system";
  const prompt =
    process.env.PROMPT || "You are an executive summarizer. Output ONLY the requested JSON. Do NOT output thinking tags.";
  const fallbackText =
    process.env.INPUT_TEXT ||
    "Ternary numeral systems use base 3 with digits -1, 0, and +1. Balanced ternary is applied in specialized hardware architectures and modern quantization techniques.";
  const serverUrl = process.env.SERVER_URL || "http://127.0.0.1:9931";
  const modelName = process.env.MODEL_NAME || "ornith-1.0-9b-Q4_K_M.gguf";

  try {
    const result = await pipeline.execute({
      url,
      fallbackText,
      systemPrompt: prompt,
      serverUrl,
      modelName,
    });

    console.log("\n============================================================");
    console.log(`📌 Document Title: ${result.headline}`);
    console.log(`🌐 Source: ${result.source_info.sourceUrl}`);
    console.log(`📊 Tokens: ${result.token_metrics.total_tokens} (Throughput: ${result.token_metrics.tokens_per_second} t/s)`);
    console.log(`📝 Executive Summary: ${result.executive_summary}`);
    result.key_points.forEach((p) => console.log(`   • ${p}`));
    console.log("============================================================\n");

    const finalTele = getMemoryAndSwapTelemetry();
    publishStepSummary(modelName, result, finalTele, pipeline.getEventHistory());
    console.log("Pipeline run complete.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
