// .github/scripts/ai-pipeline.ts
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import crypto from "node:crypto";
import { execSync } from "node:child_process";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";

import { parseHTML } from "linkedom";
import { Defuddle } from "defuddle/node";

// -------------------------------------------------------------
// 1. RFC 4122 UUID v5 GENERATOR (`evt-<uuidv5>`)
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
export type ActiveSourceType = "URL" | "INPUT_TEXT" | "FALLBACK_INPUT_TEXT";

export interface SourceAudit {
  activeSource: ActiveSourceType;
  sourceIdentifier: string;
  sourceTitle: string;
  resolutionReason: string;
  extractedWordCount: number;
  extractedCharCount: number;
  extractedText: string;
  scrapeError?: string;
}

export interface DetailedTokenMetrics {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  prompt_time_ms: number;
  completion_time_ms: number;
  total_duration_ms: number;
  prompt_tokens_per_second: number; // Input evaluation speed
  completion_tokens_per_second: number; // Generation speed
}

export interface SwapActivityMetrics {
  swappiness: number;
  server_pid: number | null;
  server_vm_rss_mb: number;
  peak_server_swap_mb: number;
  final_server_swap_mb: number;
  system_swap_used_mb: number;
  system_swap_total_mb: number;
  swap_bytes_written_mb: number;
  swap_bytes_read_mb: number;
}

export interface SummaryStructuredOutput {
  headline: string;
  executive_summary: string;
  key_points: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  compression_ratio: string;
  raw_output: string;
  source_audit: SourceAudit;
  token_metrics: DetailedTokenMetrics;
  swap_metrics: SwapActivityMetrics;
}

export interface PipelineEvent<T = any> {
  eventId: string; // Strictly `evt-<uuidv5>`
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
async function extractWithDefuddle(url: string) {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; DefuddleScraper/1.0)",
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
      signal: AbortSignal.timeout(15000),
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
      success: true,
      title: result.title || "Web Document",
      extractedText: content,
      wordCount: content.split(/\s+/).filter(Boolean).length,
    };
  } catch (err: any) {
    return {
      success: false,
      title: "Extraction Fallback",
      extractedText: "",
      wordCount: 0,
      error: err.message || String(err),
    };
  }
}

// -------------------------------------------------------------
// 4. SWAP ACTIVITY & HARDWARE DIAGNOSTICS
// -------------------------------------------------------------
function readServerPid(): number | null {
  try {
    if (fs.existsSync(".llama_server.pid")) {
      return parseInt(fs.readFileSync(".llama_server.pid", "utf8").trim(), 10);
    }
  } catch {}
  return null;
}

function getVmstatSwap(): { pswpin: number; pswpout: number } {
  try {
    const vmstat = fs.readFileSync("/proc/vmstat", "utf8");
    let pswpin = 0;
    let pswpout = 0;
    for (const line of vmstat.split("\n")) {
      if (line.startsWith("pswpin ")) pswpin = parseInt(line.split(/\s+/)[1], 10);
      if (line.startsWith("pswpout ")) pswpout = parseInt(line.split(/\s+/)[1], 10);
    }
    return { pswpin, pswpout };
  } catch {
    return { pswpin: 0, pswpout: 0 };
  }
}

function getMemorySnapshot() {
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

  const pid = readServerPid();
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

  return {
    swappiness,
    pid,
    vmRssMb: Math.round(vmRss),
    vmSwapMb: Math.round(vmSwap),
    systemSwapUsedMb: Math.round(swapTotal - swapFree),
    systemSwapTotalMb: Math.round(swapTotal),
  };
}

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
// 6. EVENT-DRIVEN ORCHESTRATOR CLASS (UUIDv5 & Precedence Engine)
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

  // Generates RFC 4122 UUIDv5 prefixed with `evt-`
  private createEventId(eventType: string, epochMs: number): string {
    const seed = `runner:${this.runnerName}:shard:${this.shardId}:epoch:${epochMs}:event:${eventType}`;
    return `evt-${generateUuidV5(seed)}`;
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
      modelName = "model.gguf",
    } = options;

    const cleanUrl = (url || "").trim();
    let targetText = fallbackText;
    let sourceAudit: SourceAudit;

    // PRECEDENCE & VERIFICATION LOGIC:
    // 1. If URL is present -> URL takes precedence (Defuddle scrapes).
    //    If Defuddle fails -> Gracefully falls back to input_text.
    // 2. If URL is empty -> Direct input_text takes hold immediately (No Defuddle).
    if (cleanUrl.length > 0) {
      this.logEvent("URL_INGESTION_STARTED", { url: cleanUrl });
      const defuddleResult = await extractWithDefuddle(cleanUrl);

      if (defuddleResult.success) {
        sourceAudit = {
          activeSource: "URL",
          sourceIdentifier: cleanUrl,
          sourceTitle: defuddleResult.title,
          resolutionReason: "URL took precedence and was successfully extracted via Defuddle.",
          extractedWordCount: defuddleResult.wordCount,
          extractedCharCount: defuddleResult.extractedText.length,
          extractedText: defuddleResult.extractedText,
        };
        targetText = defuddleResult.extractedText;

        this.logEvent("URL_INGESTION_COMPLETED", {
          url: cleanUrl,
          title: defuddleResult.title,
          wordCount: defuddleResult.wordCount,
          preview: defuddleResult.extractedText.substring(0, 100) + "...",
        });
      } else {
        sourceAudit = {
          activeSource: "FALLBACK_INPUT_TEXT",
          sourceIdentifier: `Fallback (Scrape failed for: ${cleanUrl})`,
          sourceTitle: "Direct Input (Graceful Fallback)",
          resolutionReason: `URL scraping failed (${defuddleResult.error}); gracefully fell back to direct input_text.`,
          extractedWordCount: fallbackText.split(/\s+/).filter(Boolean).length,
          extractedCharCount: fallbackText.length,
          extractedText: fallbackText,
          scrapeError: defuddleResult.error,
        };
        targetText = fallbackText;

        this.logEvent("URL_INGESTION_FAILED", {
          url: cleanUrl,
          error: defuddleResult.error,
          resolution: "Fell back to direct input_text",
        });
      }
    } else {
      sourceAudit = {
        activeSource: "INPUT_TEXT",
        sourceIdentifier: "Direct Text Input (No URL provided)",
        sourceTitle: "Direct Input Text",
        resolutionReason: "URL was omitted; direct input_text took hold directly without web scraping.",
        extractedWordCount: fallbackText.split(/\s+/).filter(Boolean).length,
        extractedCharCount: fallbackText.length,
        extractedText: fallbackText,
      };
      targetText = fallbackText;
    }

    // Context safety: Trim to ~6,000 words
    const words = targetText.split(/\s+/).filter(Boolean);
    if (words.length > 6000) {
      targetText = words.slice(0, 6000).join(" ") + "\n\n[...Truncated to fit context window...]";
    }

    // Log explicit active source verification
    this.logEvent("INPUT_RECEIVED", {
      modelName,
      activeSource: sourceAudit.activeSource,
      resolutionReason: sourceAudit.resolutionReason,
      sourceIdentifier: sourceAudit.sourceIdentifier,
      sourceTitle: sourceAudit.sourceTitle,
      wordCount: words.length,
      charCount: targetText.length,
    });

    // Stage 2: Initialize Swap Baseline Tracking
    const vmstatStart = getVmstatSwap();
    let peakProcessSwapMb = 0;
    const initialSnap = getMemorySnapshot();
    peakProcessSwapMb = Math.max(peakProcessSwapMb, initialSnap.vmSwapMb);

    // Stage 3: Inference Dispatch
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      serverUrl,
      targetModel: modelName,
      activeSource: sourceAudit.activeSource,
      temperature: 0.2,
    });

    const progressTimer = setInterval(() => {
      const elapsed = Math.round((performance.now() - startTime) / 1000);
      const snap = getMemorySnapshot();
      peakProcessSwapMb = Math.max(peakProcessSwapMb, snap.vmSwapMb);

      console.log(
        `[PIPELINE] ⏳ Elapsed: ${elapsed}s | RAM RSS: ${snap.vmRssMb} MB | Process Swap: ${snap.vmSwapMb} MB (Peak: ${peakProcessSwapMb} MB) | Swappiness: ${snap.swappiness}`
      );
    }, 10000);

    let rawContent = "";
    let usage: any = null;
    let timings: any = null;

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
            content: `Document Title: ${sourceAudit.sourceTitle}\n\nContent:\n"""\n${targetText}\n"""`,
          },
        ],
        temperature: 0.2,
        stream: false,
        chat_template_kwargs: { enable_thinking: false },
      });

      rawContent = jsonResponse.choices?.[0]?.message?.content || "";
      usage = jsonResponse.usage;
      timings = jsonResponse.timings;
    } finally {
      clearInterval(progressTimer);
    }

    const totalDurationMs = Math.round(performance.now() - startTime);

    // Stage 4: Finalize Swap Telemetry
    const finalSnap = getMemorySnapshot();
    peakProcessSwapMb = Math.max(peakProcessSwapMb, finalSnap.vmSwapMb);
    const vmstatEnd = getVmstatSwap();

    const swapOutPages = Math.max(0, vmstatEnd.pswpout - vmstatStart.pswpout);
    const swapInPages = Math.max(0, vmstatEnd.pswpin - vmstatStart.pswpin);
    const swapWrittenMb = Number(((swapOutPages * 4) / 1024).toFixed(2));
    const swapReadMb = Number(((swapInPages * 4) / 1024).toFixed(2));

    const swapMetrics: SwapActivityMetrics = {
      swappiness: finalSnap.swappiness,
      server_pid: finalSnap.pid,
      server_vm_rss_mb: finalSnap.vmRssMb,
      peak_server_swap_mb: peakProcessSwapMb,
      final_server_swap_mb: finalSnap.vmSwapMb,
      system_swap_used_mb: finalSnap.systemSwapUsedMb,
      system_swap_total_mb: finalSnap.systemSwapTotalMb,
      swap_bytes_written_mb: swapWrittenMb,
      swap_bytes_read_mb: swapReadMb,
    };

    // Stage 5: Calculate Input vs Output Tokens Per Second
    const promptTokens = usage?.prompt_tokens || timings?.prompt_n || 0;
    const completionTokens = usage?.completion_tokens || timings?.predicted_n || 0;
    const totalTokens = usage?.total_tokens || promptTokens + completionTokens;

    let promptTimeMs = timings?.prompt_ms ? Math.round(timings.prompt_ms) : 0;
    let completionTimeMs = timings?.predicted_ms ? Math.round(timings.predicted_ms) : 0;
    if (promptTimeMs === 0 && completionTimeMs === 0) {
      completionTimeMs = totalDurationMs;
    }

    const promptTokensPerSec = timings?.prompt_per_second
      ? Number(timings.prompt_per_second.toFixed(2))
      : promptTimeMs > 0
      ? Number(((promptTokens / (promptTimeMs / 1000))).toFixed(2))
      : 0;

    const completionTokensPerSec = timings?.predicted_per_second
      ? Number(timings.predicted_per_second.toFixed(2))
      : completionTimeMs > 0
      ? Number(((completionTokens / (completionTimeMs / 1000))).toFixed(2))
      : 0;

    const tokenMetrics: DetailedTokenMetrics = {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: totalTokens,
      prompt_time_ms: promptTimeMs,
      completion_time_ms: completionTimeMs,
      total_duration_ms: totalDurationMs,
      prompt_tokens_per_second: promptTokensPerSec,
      completion_tokens_per_second: completionTokensPerSec,
    };

    // Stage 6: Emit Completion Event
    this.logEvent("INFERENCE_COMPLETED", {
      modelName,
      activeSource: sourceAudit.activeSource,
      tokenMetrics,
      swapMetrics,
    });

    // Stage 7: Parse Structured Output
    let parsed: any;
    try {
      const match = rawContent.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(match ? match[0] : rawContent);
    } catch {
      parsed = {
        headline: sourceAudit.sourceTitle || "Document Summary",
        executive_summary: rawContent.trim(),
        key_points: ["Extracted from raw model text"],
        sentiment: "neutral",
      };
    }

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || sourceAudit.sourceTitle || "Summary Output",
      executive_summary: parsed.executive_summary || rawContent,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      compression_ratio: `${((rawContent.length / targetText.length) * 100).toFixed(1)}%`,
      raw_output: rawContent,
      source_audit: sourceAudit,
      token_metrics: tokenMetrics,
      swap_metrics: swapMetrics,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 7. GITHUB STEP SUMMARY & ANNOTATION (ZERO-INDENT COMMONMARK)
// -------------------------------------------------------------
function publishStepSummary(
  modelName: string,
  result: SummaryStructuredOutput,
  events: PipelineEvent[]
) {
  const tm = result.token_metrics;
  const sm = result.swap_metrics;
  const sa = result.source_audit;

  // 1. Surfaced directly in the GitHub Actions Workflow Run Header as an Annotation:
  console.log(
    `::notice title=AI Pipeline Succeeded (${modelName})::🎯 Source: ${sa.activeSource} | 📥 Ingest: ${tm.prompt_tokens_per_second} t/s (${tm.prompt_tokens}t) | ⚡ Gen: ${tm.completion_tokens_per_second} t/s (${tm.completion_tokens}t) | ⏱️ Time: ${(tm.total_duration_ms / 1000).toFixed(1)}s | 💾 Peak Swap: ${sm.peak_server_swap_mb} MB`
  );

  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  // 2. Strict CommonMark formatting (NO LEADING INDENTATION on any line)
  const lines: string[] = [
    `# 🧠 AI Transformer Pipeline Execution Report`,
    ``,
    `> **🎯 Active Input Source:** \`${sa.activeSource}\`  `,
    `> **Resolution:** ${sa.resolutionReason}`,
    ``,
    `---`,
    ``,
    `## ⏱️ Token Performance & Ingestion Rates`,
    ``,
    `| Metric | Token Count | Elapsed Time | Speed (Tokens / Sec) |`,
    `| :--- | :--- | :--- | :--- |`,
    `| **Prompt (Input Ingestion)** | **${tm.prompt_tokens} tokens** | ${tm.prompt_time_ms > 0 ? (tm.prompt_time_ms / 1000).toFixed(2) + "s" : "Batched"} | **⚡ ${tm.prompt_tokens_per_second} tokens/sec** |`,
    `| **Completion (Output Gen)** | **${tm.completion_tokens} tokens** | ${(tm.completion_time_ms / 1000).toFixed(2)}s | **⚡ ${tm.completion_tokens_per_second} tokens/sec** |`,
    `| **Total Evaluation** | **${tm.total_tokens} tokens** | **${(tm.total_duration_ms / 1000).toFixed(2)}s** | Overall Pipeline Throughput |`,
    ``,
    `---`,
    ``,
    `## 💾 Memory & Swap Diagnostics`,
    ``,
    `| Metric | Measured Value | Health & State |`,
    `| :--- | :--- | :--- |`,
    `| **Linux \`vm.swappiness\`** | **\`${sm.swappiness}\`** | ${sm.swappiness <= 10 ? "✅ Low Paging (Optimized)" : "⚠️ High Paging"} |`,
    `| **Server Process PID** | \`${sm.server_pid || "unknown"}\` | Background Daemon |`,
    `| **Server RAM (RSS)** | **${sm.server_vm_rss_mb} MB** | Active Physical Memory |`,
    `| **Peak Process Swap** | **${sm.peak_server_swap_mb} MB** | ${sm.peak_server_swap_mb > 0 ? "⚠️ Process Swapped to Disk" : "✅ 0 MB (Zero Process Swap)"} |`,
    `| **Final Process Swap** | **${sm.final_server_swap_mb} MB** | Current Swap Allocation |`,
    `| **Swap Written to SSD** | **${sm.swap_bytes_written_mb} MB** | Disk I/O: Pages Written Out |`,
    `| **Swap Read from SSD** | **${sm.swap_bytes_read_mb} MB** | Disk I/O: Pages Paged Back In |`,
    `| **Total System Swap Used** | \`${sm.system_swap_used_mb} MB / ${sm.system_swap_total_mb} MB\` | Allocated Swapfile Space |`,
    ``,
    `---`,
    ``,
    `## 🌐 Ingestion Source Diagnostics`,
    ``,
    `| Parameter | Value |`,
    `| :--- | :--- |`,
    `| **Active Source Mode** | \`${sa.activeSource}\` |`,
    `| **Source Identifier** | ${sa.sourceIdentifier.startsWith("http") ? `[${sa.sourceIdentifier}](${sa.sourceIdentifier})` : `\`${sa.sourceIdentifier}\``} |`,
    `| **Document Title** | **${sa.sourceTitle}** |`,
    `| **Word Count** | \`${sa.extractedWordCount} words\` (\`${sa.extractedCharCount} chars\`) |`,
    `| **Status Details** | ${sa.activeSource === "URL" ? "✅ Successfully Scraped & Extracted via `defuddle/node`" : sa.activeSource === "FALLBACK_INPUT_TEXT" ? `⚠️ Defuddle Fallback Invoked (${sa.scrapeError})` : "ℹ️ Direct Text Mode (URL not provided)"} |`,
    ``,
    `---`,
    ``,
    `## 📝 Structured Summary: *"${result.headline}"*`,
    ``,
    `> **Executive Summary:**  `,
    `> ${result.executive_summary}`,
    ``,
    `**Key Takeaways:**`,
    ...result.key_points.map((p) => `- ${p}`),
    ``,
    `| Attribute | Value |`,
    `| :--- | :--- |`,
    `| **Detected Sentiment** | \`${result.sentiment.toUpperCase()}\` |`,
    `| **Compression Ratio** | \`${result.compression_ratio}\` |`,
    ``,
    `---`,
    ``,
    `## 📄 Cleaned Source Content That Took Hold`,
    `<details>`,
    `<summary><b>Click to expand input content (${sa.extractedWordCount} words)</b></summary>`,
    ``,
    `\`\`\`markdown`,
    sa.extractedText || "No source text available",
    `\`\`\``,
    ``,
    `</details>`,
    ``,
    `## 🤖 Raw Model Output Text`,
    `<details>`,
    `<summary><b>Click to expand raw response</b></summary>`,
    ``,
    `\`\`\`text`,
    result.raw_output,
    `\`\`\``,
    ``,
    `</details>`,
    ``,
    `---`,
    ``,
    `## ⚡ Event-Driven Audit Trail (UUIDv5)`,
    ``,
    `| Event Type | RFC 4122 UUIDv5 | Timestamp |`,
    `| :--- | :--- | :--- |`,
    ...events.map((e) => `| \`${e.eventType}\` | \`${e.eventId}\` | \`${e.timestamp}\` |`),
    ``,
    `<details>`,
    `<summary><b>Inspect Full Event Stream Payloads (JSON)</b></summary>`,
    ``,
    `\`\`\`json`,
    JSON.stringify(events, null, 2),
    `\`\`\``,
    ``,
    `</details>`,
    ``,
  ];

  fs.appendFileSync(summaryPath, lines.join("\n"), "utf8");
}

// -------------------------------------------------------------
// 8. CLI / WORKFLOW ENTRY POINT
// -------------------------------------------------------------
async function main() {
  const l3Cache = detectL3Cache();
  const runnerName = process.env.RUNNER_NAME || "local-runner";
  const shardId = process.env.SHARD_ID || "shard-1/1";
  const modelName = process.env.MODEL_NAME || "model.gguf";

  console.log("=== Initial System Diagnostics ===");
  console.log({
    runner: runnerName,
    shard: shardId,
    model: modelName,
    l3Cache: l3Cache,
  });

  const pipeline = new AIEventPipeline(runnerName, shardId);

  // Real-time lifecycle event listeners (Printing `evt-<uuidv5>`)
  pipeline.on("URL_INGESTION_STARTED", (e) =>
    console.log(`[EVENT] 🌐 Ingesting URL with Defuddle [${e.eventId}] -> ${e.payload.url}`)
  );
  pipeline.on("URL_INGESTION_COMPLETED", (e) =>
    console.log(`[EVENT] ✅ Defuddle Ingested: "${e.payload.title}" (${e.payload.wordCount} words) [${e.eventId}]`)
  );
  pipeline.on("URL_INGESTION_FAILED", (e) =>
    console.log(`[EVENT] ⚠️ Defuddle Failed (${e.payload.error}) [${e.eventId}]`)
  );
  pipeline.on("INPUT_RECEIVED", (e) =>
    console.log(
      `[EVENT] 📥 Input Prepared [${e.eventId}] -> Active Source: [${e.payload.activeSource}] (${e.payload.wordCount} words)\n       Reason: ${e.payload.resolutionReason}`
    )
  );
  pipeline.on("INFERENCE_STARTED", (e) =>
    console.log(`[EVENT] 🚀 Dispatched to ${e.payload.targetModel} [${e.eventId}]`)
  );
  pipeline.on("INFERENCE_COMPLETED", (e) => {
    const tm: DetailedTokenMetrics = e.payload.tokenMetrics;
    const sm: SwapActivityMetrics = e.payload.swapMetrics;
    console.log(
      `[EVENT] ✅ Completed [${e.eventId}] in ${(tm.total_duration_ms / 1000).toFixed(1)}s (Prompt: ${tm.prompt_tokens}t @ ${tm.prompt_tokens_per_second} t/s | Output: ${tm.completion_tokens}t @ ${tm.completion_tokens_per_second} t/s | Peak Swap: ${sm.peak_server_swap_mb} MB)`
    );
  });
  pipeline.on("OUTPUT_STRUCTURED", (e) =>
    console.log(`[EVENT] 📦 Structured JSON Ready [${e.eventId}]`)
  );

  const rawUrl = process.env.URL || "";
  const url = rawUrl.trim();

  const prompt =
    process.env.PROMPT ||
    "You are an executive summarizer. Output ONLY the requested JSON. Do NOT output thinking tags.";

  const rawInputText = process.env.INPUT_TEXT || "";
  const fallbackText =
    rawInputText.trim() ||
    "Local LLMs allow running transformer architectures directly on edge devices and continuous integration runners without transmitting data over third-party APIs.";

  const serverUrl = process.env.SERVER_URL || "http://127.0.0.1:9931";

  console.log(`[CONFIG] Source Mode Requested: ${url ? `URL (${url})` : "Direct Text Input"}`);

  try {
    const result = await pipeline.execute({
      url,
      fallbackText,
      systemPrompt: prompt,
      serverUrl,
      modelName,
    });

    console.log("\n============================================================");
    console.log(`📌 Document Title:   ${result.headline}`);
    console.log(`🎯 Active Source:    [${result.source_audit.activeSource}]`);
    console.log(`ℹ️ Source Reason:    ${result.source_audit.resolutionReason}`);
    console.log(
      `📥 Prompt Speed:     ${result.token_metrics.prompt_tokens_per_second} tokens/sec (${result.token_metrics.prompt_tokens} tokens)`
    );
    console.log(
      `⚡ Gen Speed:        ${result.token_metrics.completion_tokens_per_second} tokens/sec (${result.token_metrics.completion_tokens} tokens)`
    );
    console.log(
      `💾 Swap Activity:    Peak Process Swap: ${result.swap_metrics.peak_server_swap_mb} MB | Written to Disk: ${result.swap_metrics.swap_bytes_written_mb} MB`
    );
    console.log(`📝 Executive Summary:\n${result.executive_summary}\n`);
    console.log("🔑 Key Takeaways:");
    result.key_points.forEach((p) => console.log(`   • ${p}`));
    console.log("============================================================\n");

    publishStepSummary(modelName, result, pipeline.getEventHistory());
    console.log("Pipeline run complete.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
