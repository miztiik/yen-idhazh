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
  prompt_tokens_per_second: number;
  completion_tokens_per_second: number;
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
// 3. BULLETPROOF URL INGESTION (Defuddle + HTML Fallback)
// -------------------------------------------------------------
async function extractWithDefuddle(url: string) {
  // Standard desktop Chrome headers to avoid 403 Forbidden blocks on Wikipedia/Cloudflare
  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
  };

  console.log(`[SCRAPER] 🌐 Fetching URL: ${url}`);
  const res = await fetch(url, { headers, signal: AbortSignal.timeout(20000) });

  console.log(`[SCRAPER] 📡 HTTP Status: ${res.status} ${res.statusText}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }

  const html = await res.text();
  console.log(`[SCRAPER] 📥 Downloaded HTML size: ${(html.length / 1024).toFixed(1)} KB`);

  // Tier 1: Defuddle / Linkedom extraction
  try {
    const { document } = parseHTML(html);
    const result: any = await Defuddle(document, url, { markdown: true, useAsync: false });
    const content = result.content?.trim() || "";

    if (content.length > 50) {
      return {
        success: true,
        title: result.title || document.title || "Web Document",
        extractedText: content,
        wordCount: content.split(/\s+/).filter(Boolean).length,
      };
    }
  } catch (defuddleErr: any) {
    console.warn(`[SCRAPER] ⚠️ Defuddle parse warning: ${defuddleErr.message}. Trying HTML text fallback...`);
  }

  // Tier 2: Resilient HTML fallback (Guarantees URL content is never lost)
  const cleanText = html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<nav[\s\S]*?<\/nav>/gi, "")
    .replace(/<footer[\s\S]*?<\/footer>/gi, "")
    .replace(/<header[\s\S]*?<\/header>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();

  if (cleanText.length > 50) {
    const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    const title = titleMatch ? titleMatch[1].trim() : "Extracted Web Article";
    return {
      success: true,
      title,
      extractedText: cleanText,
      wordCount: cleanText.split(/\s+/).filter(Boolean).length,
    };
  }

  throw new Error("Unable to extract readable content from URL");
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
// 6. EVENT-DRIVEN ORCHESTRATOR CLASS
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

    // PRECEDENCE & VERIFICATION LOGIC
    if (cleanUrl.length > 0) {
      this.logEvent("URL_INGESTION_STARTED", { url: cleanUrl });

      try {
        const defuddleResult = await extractWithDefuddle(cleanUrl);

        sourceAudit = {
          activeSource: "URL",
          sourceIdentifier: cleanUrl,
          sourceTitle: defuddleResult.title,
          resolutionReason: "URL took precedence and was successfully extracted.",
          extractedWordCount: defuddleResult.wordCount,
          extractedCharCount: defuddleResult.extractedText.length,
          extractedText: defuddleResult.extractedText,
        };
        targetText = defuddleResult.extractedText;

        console.log(`[PIPELINE] ✅ URL TOOK HOLD: "${defuddleResult.title}" (${defuddleResult.wordCount} words)`);
        console.log(`[PIPELINE] 📄 Extracted Content Preview:\n"""\n${targetText.substring(0, 200)}...\n"""\n`);

        this.logEvent("URL_INGESTION_COMPLETED", {
          url: cleanUrl,
          title: defuddleResult.title,
          wordCount: defuddleResult.wordCount,
        });
      } catch (err: any) {
        console.warn(`[PIPELINE] ⚠️ URL extraction failed (${err.message}). Falling back to input_text.`);

        sourceAudit = {
          activeSource: "FALLBACK_INPUT_TEXT",
          sourceIdentifier: `Fallback (URL failed: ${cleanUrl})`,
          sourceTitle: "Direct Input (Graceful Fallback)",
          resolutionReason: `URL failed (${err.message}); gracefully fell back to direct input_text.`,
          extractedWordCount: fallbackText.split(/\s+/).filter(Boolean).length,
          extractedCharCount: fallbackText.length,
          extractedText: fallbackText,
          scrapeError: err.message,
        };
        targetText = fallbackText;

        this.logEvent("URL_INGESTION_FAILED", {
          url: cleanUrl,
          error: err.message,
          resolution: "Fell back to direct input_text",
        });
      }
    } else {
      sourceAudit = {
        activeSource: "INPUT_TEXT",
        sourceIdentifier: "Direct Text Input (No URL provided)",
        sourceTitle: "Dir
