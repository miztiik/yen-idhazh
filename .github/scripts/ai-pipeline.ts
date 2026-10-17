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
// 1. UUID GENERATORS (RFC 4122 UUIDv4 & RFC 4122 UUIDv5)
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
// 2. HARDWARE FINGERPRINT & HOST DIAGNOSTICS
// -------------------------------------------------------------
export interface HostFingerprint {
  cpuModel: string;
  coreCount: number;
  l3Cache: string;
  avxFlags: string[];
  totalRamGb: string;
  rawFingerprint: string;
}

export interface RunnerMetadata {
  runnerName: string;
  runId: string;
  runNumber: string;
  workflow: string;
  osArch: string;
  shardId: string;
  modelFamily: string;
  requestedModelId: string;
}

export interface CpuUtilizationMetrics {
  maxCpuPercent: number;
  avgCpuPercent: number;
  samplesTaken: number;
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
          if (raw.endsWith("K")) bytes = parseInt(raw, 10) * 1024;
          else if (raw.endsWith("M")) bytes = parseInt(raw, 10) * 1024 * 1024;
          else bytes = parseInt(raw, 10);
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

  return "Unknown";
}

function getHostFingerprint(): HostFingerprint {
  const cpus = os.cpus();
  const cpuModel = cpus[0]?.model?.trim() || "Unknown CPU";
  const coreCount = cpus.length;
  const totalRamGb = (os.totalmem() / (1024 ** 3)).toFixed(2) + " GB";
  const l3Cache = detectL3Cache();

  const avxFlags: string[] = [];
  try {
    const cpuInfo = fs.readFileSync("/proc/cpuinfo", "utf8");
    const flagsMatch = cpuInfo.match(/^flags\s*:\s*(.+)$/m);
    if (flagsMatch) {
      const flags = new Set(flagsMatch[1].split(/\s+/));
      if (flags.has("avx")) avxFlags.push("AVX");
      if (flags.has("avx2")) avxFlags.push("AVX2");
      if (flags.has("avx512f")) avxFlags.push("AVX-512");
      if (flags.has("fma")) avxFlags.push("FMA");
      if (flags.has("neon")) avxFlags.push("NEON");
    }
  } catch {}

  return {
    cpuModel,
    coreCount,
    l3Cache,
    avxFlags: avxFlags.length > 0 ? avxFlags : ["Not Detected / None"],
    totalRamGb,
    rawFingerprint: `CPU: ${cpuModel} (${coreCount} cores) | RAM: ${totalRamGb}`,
  };
}

class SystemCpuSampler {
  private prevStat: { total: number; idle: number } | null = null;
  private samples: number[] = [];
  private timer: NodeJS.Timeout | null = null;

  private readStat(): { total: number; idle: number } | null {
    try {
      const stat = fs.readFileSync("/proc/stat", "utf8");
      const line = stat.split("\n")[0];
      if (!line.startsWith("cpu ")) return null;

      const parts = line.trim().split(/\s+/).slice(1).map(Number);
      // fields: user, nice, system, idle, iowait, irq, softirq, steal
      const idle = parts[3] + (parts[4] || 0);
      const nonIdle = parts[0] + parts[1] + parts[2] + (parts[5] || 0) + (parts[6] || 0) + (parts[7] || 0);
      const total = idle + nonIdle;
      return { total, idle };
    } catch {
      return null;
    }
  }

  public start(intervalMs = 1000) {
    this.prevStat = this.readStat();
    this.samples = [];

    this.timer = setInterval(() => {
      const current = this.readStat();
      if (current && this.prevStat) {
        const deltaTotal = current.total - this.prevStat.total;
        const deltaIdle = current.idle - this.prevStat.idle;
        if (deltaTotal > 0) {
          const utilPercent = Math.max(0, Math.min(100, ((deltaTotal - deltaIdle) / deltaTotal) * 100));
          this.samples.push(utilPercent);
        }
      }
      this.prevStat = current;
    }, intervalMs);
  }

  public stop(): CpuUtilizationMetrics {
    if (this.timer) clearInterval(this.timer);
    if (this.samples.length === 0) {
      return { maxCpuPercent: 0, avgCpuPercent: 0, samplesTaken: 0 };
    }
    const max = Math.max(...this.samples);
    const avg = this.samples.reduce((a, b) => a + b, 0) / this.samples.length;
    return {
      maxCpuPercent: Number(max.toFixed(1)),
      avgCpuPercent: Number(avg.toFixed(1)),
      samplesTaken: this.samples.length,
    };
  }
}

// -------------------------------------------------------------
// 3. SCHEMAS & INTERFACES
// -------------------------------------------------------------
export type StanceOnChange = "conservatism" | "progressivism" | "not_applicable";
export type StanceOnEconomicPower = "socialism" | "libertarianism" | "not_applicable";
export type StanceOnStatePower = "statism" | "constitutionalism" | "not_applicable";
export type StanceOnBorders = "nationalism" | "internationalism" | "not_applicable";
export type StanceOnPersonalSphere = "civil_libertarianism" | "communitarianism" | "not_applicable";

export interface SourceAudit {
  sourceType: "URL" | "INPUT_TEXT" | "FALLBACK_INPUT_TEXT";
  sourceIdentifier: string;
  sourceTitle: string;
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

export interface CompressionAnalysis {
  inputChars: number;
  outputChars: number;
  retentionRatioPercent: string;
  reductionRatioPercent: string;
  explanation: string;
}

export interface SummaryStructuredOutput {
  headline: string;
  executive_summary: string;
  key_points: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  stance_on_change: StanceOnChange;
  stance_on_economic_power: StanceOnEconomicPower;
  stance_on_state_power: StanceOnStatePower;
  stance_on_borders: StanceOnBorders;
  stance_on_personal_sphere: StanceOnPersonalSphere;
  compression: CompressionAnalysis;
  raw_output: string;
  source_audit: SourceAudit;
  token_metrics: DetailedTokenMetrics;
  swap_metrics: SwapActivityMetrics;
  cpu_metrics: CpuUtilizationMetrics;
  host_fingerprint: HostFingerprint;
  runner_metadata: RunnerMetadata;
  input_text: string;
  system_prompt: string;
  user_prompt: string;
}

export interface PipelineEvent<T = any> {
  eventId: string;
  eventType:
    | "URL_HTTP_FETCH_STARTED"
    | "URL_HTTP_FETCH_COMPLETED"
    | "URL_DEFUDDLE_EXTRACTED"
    | "URL_READER_PROXY_USED"
    | "URL_EXTRACTION_FAILED"
    | "INPUT_RESOLVED"
    | "INFERENCE_DISPATCHED"
    | "INFERENCE_COMPLETED"
    | "OUTPUT_STRUCTURED";
  timestamp: string;
  correlationId: string;
  payload: T;
}

// -------------------------------------------------------------
// 4. DIRECT URL INGESTION (Defuddle + Reader Proxy Fallback)
// -------------------------------------------------------------
async function extractDirectUrl(
  url: string,
  emitEvent: (type: PipelineEvent["eventType"], payload: any) => void
): Promise<{ title: string; content: string; wordCount: number }> {
  emitEvent("URL_HTTP_FETCH_STARTED", { url });

  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
  };

  console.log(`[SCRAPER] 🌐 Directly querying URL: ${url}`);
  let html = "";
  let directFetchFailed = false;

  try {
    const res = await fetch(url, { headers, signal: AbortSignal.timeout(15000) });
    console.log(`[SCRAPER] 📡 Direct Response Status: ${res.status} ${res.statusText}`);

    if (res.ok) {
      html = await res.text();
    } else {
      console.warn(`[SCRAPER] ⚠️ Direct fetch blocked by WAF/Cloudflare (HTTP ${res.status}).`);
      directFetchFailed = true;
    }
  } catch (err: any) {
    console.warn(`[SCRAPER] ⚠️ Direct connection error: ${err.message}`);
    directFetchFailed = true;
  }

  // Direct fetch parsing with Defuddle
  if (!directFetchFailed && html.length > 100) {
    emitEvent("URL_HTTP_FETCH_COMPLETED", { url, bytes: Buffer.byteLength(html, "utf8") });

    try {
      const { document } = parseHTML(html);
      const title = document.title || "Web Document";
      const result: any = await Defuddle(document, url, { markdown: true, useAsync: false });
      const content = result.content?.trim() || "";

      if (content.length > 50) {
        const wordCount = content.split(/\s+/).filter(Boolean).length;
        emitEvent("URL_DEFUDDLE_EXTRACTED", { url, title: result.title || title, wordCount });
        console.log(`[SCRAPER] ✅ Successfully parsed with Defuddle/node: "${result.title || title}" (${wordCount} words)`);
        return {
          title: result.title || title,
          content,
          wordCount,
        };
      }
    } catch (parseErr: any) {
      console.warn(`[SCRAPER] ⚠️ Defuddle DOM parse error: ${parseErr.message}`);
    }
  }

  // Fallback to Jina Reader Proxy
  console.log(`[SCRAPER] 🔄 Engaging Reader Proxy to bypass Cloudflare datacenter IP block...`);
  const proxyUrl = `https://r.jina.ai/${url}`;

  const proxyRes = await fetch(proxyUrl, {
    headers: { Accept: "text/plain, text/markdown" },
    signal: AbortSignal.timeout(20000),
  });

  if (!proxyRes.ok) {
    throw new Error(`Both direct query and reader proxy failed (Proxy HTTP ${proxyRes.status})`);
  }

  const markdownContent = await proxyRes.text();
  const wordCount = markdownContent.split(/\s+/).filter(Boolean).length;

  if (wordCount < 20) {
    throw new Error("Reader proxy returned insufficient content");
  }

  const titleMatch = markdownContent.match(/^Title:\s*(.+)$/m) || markdownContent.match(/^#\s*(.+)$/m);
  const title = titleMatch ? titleMatch[1].trim() : "Extracted Web Article";

  emitEvent("URL_READER_PROXY_USED", { url, proxyUrl, title, wordCount });
  console.log(`[SCRAPER] ✅ Reader proxy extracted article: "${title}" (${wordCount} words)`);

  return {
    title,
    content: markdownContent,
    wordCount,
  };
}

// -------------------------------------------------------------
// 5. SWAP ACTIVITY & MEMORY SNAPSHOTS
// -------------------------------------------------------------
function readServerPid(): number | null {
  try {
    if (fs.existsSync(".llama_server.pid")) {
      const pidStr = fs.readFileSync(".llama_server.pid", "utf8").trim();
      return pidStr ? parseInt(pidStr, 10) : null;
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

// -------------------------------------------------------------
// 6. TIMEOUT-FREE OPENAPI HTTP CLIENT
// -------------------------------------------------------------
function postOpenAIChatCompletion(urlStr: string, payload: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const bodyData = JSON.stringify(payload);

    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port,
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
            reject(new Error(`llama-server returned HTTP ${res.statusCode}: ${raw}`));
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
// 7. EVENT-DRIVEN PIPELINE ORCHESTRATOR
// -------------------------------------------------------------
export class AIEventPipeline extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  private correlationId: string;
  private runnerMetadata: RunnerMetadata;
  private hostFingerprint: HostFingerprint;
  private jsonlFilePath: string;

  constructor(runnerMetadata: RunnerMetadata, jsonlFilePath = "pipeline-events.jsonl") {
    super();
    this.runnerMetadata = runnerMetadata;
    this.hostFingerprint = getHostFingerprint();
    // Standard RFC 4122 UUIDv4 Correlation ID
    this.correlationId = `corr-${crypto.randomUUID()}`;
    this.jsonlFilePath = jsonlFilePath;
  }

  private createEventId(eventType: string, epochMs: number): string {
    const seed = `runner:${this.runnerMetadata.runnerName}:shard:${this.runnerMetadata.shardId}:epoch:${epochMs}:event:${eventType}`;
    return `evt-${generateUuidV5(seed)}`;
  }

  public logEvent(eventType: PipelineEvent["eventType"], payload: any) {
    const epochMs = Date.now();
    const event: PipelineEvent = {
      eventId: this.createEventId(eventType, epochMs),
      eventType,
      timestamp: new Date(epochMs).toISOString(),
      correlationId: this.correlationId,
      payload,
    };

    this.auditLog.push(event);

    const jsonlLine = JSON.stringify(event);
    fs.appendFileSync(this.jsonlFilePath, jsonlLine + "\n", "utf8");
    console.log(`[JSONL_EVENT] ${jsonlLine}`);

    this.emit(eventType, event);
    return event;
  }

  public getEventHistory(): PipelineEvent[] {
    return this.auditLog;
  }

  public async execute(options: {
    url?: string;
    fallbackText?: string;
    systemPrompt: string;
    serverUrl: string;
    modelName: string;
  }): Promise<SummaryStructuredOutput> {
    const { url, fallbackText = "", systemPrompt, serverUrl, modelName } = options;

    const cleanUrl = (url || "").trim();
    let targetText = fallbackText;
    let sourceAudit: SourceAudit;

    if (cleanUrl.length > 0) {
      console.log(`[PIPELINE] 🔍 Target URL supplied: ${cleanUrl}`);

      try {
        const extracted = await extractDirectUrl(cleanUrl, (type, payload) => this.logEvent(type, payload));

        sourceAudit = {
          sourceType: "URL",
          sourceIdentifier: cleanUrl,
          sourceTitle: extracted.title,
          extractedWordCount: extracted.wordCount,
          extractedCharCount: extracted.content.length,
          extractedText: extracted.content,
        };
        targetText = extracted.content;

        console.log(`[PIPELINE] ✅ URL extracted: "${extracted.title}" (${extracted.wordCount} words)`);
      } catch (err: any) {
        if (!fallbackText) {
          throw new Error(`URL extraction failed (${err.message}) and no input_text was provided.`);
        }

        console.warn(`[PIPELINE] ⚠️ URL extraction failed (${err.message}). Falling back to input_text.`);
        this.logEvent("URL_EXTRACTION_FAILED", {
          url: cleanUrl,
          error: err.message,
          resolution: "Fell back to input_text",
        });

        sourceAudit = {
          sourceType: "FALLBACK_INPUT_TEXT",
          sourceIdentifier: `Fallback (URL failed: ${cleanUrl})`,
          sourceTitle: "Direct Input (Fallback)",
          extractedWordCount: fallbackText.split(/\s+/).filter(Boolean).length,
          extractedCharCount: fallbackText.length,
          extractedText: fallbackText,
          scrapeError: err.message,
        };
        targetText = fallbackText;
      }
    } else {
      if (!fallbackText) {
        throw new Error("Execution rejected: Both URL and input_text are empty.");
      }

      sourceAudit = {
        sourceType: "INPUT_TEXT",
        sourceIdentifier: "Direct Text Input",
        sourceTitle: "Direct Input Text",
        extractedWordCount: fallbackText.split(/\s+/).filter(Boolean).length,
        extractedCharCount: fallbackText.length,
        extractedText: fallbackText,
      };
      targetText = fallbackText;
      console.log(`[PIPELINE] ℹ️ Using input_text directly (${sourceAudit.extractedWordCount} words).`);
    }

    // Context protection truncation
    const words = targetText.split(/\s+/).filter(Boolean);
    if (words.length > 6000) {
      targetText = words.slice(0, 6000).join(" ") + "\n\n[...Truncated to fit context window...]";
    }

    const userPromptContent = `Document Title: ${sourceAudit.sourceTitle}\n\nContent:\n"""\n${targetText}\n"""`;

    this.logEvent("INPUT_RESOLVED", {
      modelName,
      sourceType: sourceAudit.sourceType,
      sourceIdentifier: sourceAudit.sourceIdentifier,
      sourceTitle: sourceAudit.sourceTitle,
      wordCount: words.length,
      charCount: targetText.length,
      inputText: targetText,
      systemPrompt,
      userPrompt: userPromptContent,
    });

    // Start swap & CPU sampling
    const vmstatStart = getVmstatSwap();
    let peakProcessSwapMb = 0;
    const initialSnap = getMemorySnapshot();
    peakProcessSwapMb = Math.max(peakProcessSwapMb, initialSnap.vmSwapMb);

    const cpuSampler = new SystemCpuSampler();
    cpuSampler.start(1000);

    const openAiPayload = {
      model: modelName,
      messages: [
        {
          role: "system",
          content: `${systemPrompt}

You MUST analyze the text and output ONLY a valid JSON object matching this exact schema:
{
  "headline": "A concise, descriptive headline for the document",
  "executive_summary": "Thorough, comprehensive narrative summary of the document. Do not artificially abbreviate or constrain the summary to a fixed sentence count; scale the length proportionally to capture the full depth, arguments, and substance of the content.",
  "key_points": [
    "Comprehensive array of all major arguments, key findings, and essential takeaways from the text (scale the number of points to the depth of the text)"
  ],
  "sentiment": "positive" | "neutral" | "negative" | "mixed",
  "stance_on_change": "conservatism" | "progressivism" | "not_applicable",
  "stance_on_economic_power": "socialism" | "libertarianism" | "not_applicable",
  "stance_on_state_power": "statism" | "constitutionalism" | "not_applicable",
  "stance_on_borders": "nationalism" | "internationalism" | "not_applicable",
  "stance_on_personal_sphere": "civil_libertarianism" | "communitarianism" | "not_applicable"
}

Definitions for classification axes:
- stance_on_change: Evaluates what to do about the existing arrangement.
  * conservatism: Maintain, protect, or return to established structures.
  * progressivism: Reform, replace, or advance beyond existing arrangements.
  * not_applicable: Topic does not address institutional or social arrangements.
- stance_on_economic_power: Evaluates who should hold economic power.
  * socialism: Collective, public, state, or democratic control of economic resources.
  * libertarianism: Private ownership, decentralized free markets, and property rights.
  * not_applicable: Topic does not address economic power allocation.
- stance_on_state_power: Evaluates whether state power is centralized or checked.
  * statism: Strong centralized government authority is necessary or justified.
  * constitutionalism: State power must be strictly constrained, distributed, and checked by rule of law.
  * not_applicable: Topic does not discuss governance authority.
- stance_on_borders: Evaluates whether solutions are inside or outside national borders.
  * nationalism: Focus on domestic sovereignty, borders, and national self-interest.
  * internationalism: Global cooperation, open borders, transnational agreements.
  * not_applicable: Topic does not address borders or national scope.
- stance_on_personal_sphere: Evaluates whether an individual retains an inviolable personal sphere.
  * civil_libertarianism: Strict individual autonomy and privacy that nobody may enter.
  * communitarianism: Social obligations, collective well-being, or communal cohesion supersede individual autonomy.
  * not_applicable: Topic does not discuss individual vs communal rights.`,
        },
        {
          role: "user",
          content: userPromptContent,
        },
      ],
      temperature: 0.2,
      response_format: { type: "json_object" },
      stream: false,
      chat_template_kwargs: { enable_thinking: false },
    };

    const startTime = performance.now();
    this.logEvent("INFERENCE_DISPATCHED", {
      serverUrl,
      targetModel: modelName,
      sourceType: sourceAudit.sourceType,
      wordCount: words.length,
      charCount: targetText.length,
      messages: openAiPayload.messages,
    });

    const progressTimer = setInterval(() => {
      const elapsed = Math.round((performance.now() - startTime) / 1000);
      const snap = getMemorySnapshot();
      peakProcessSwapMb = Math.max(peakProcessSwapMb, snap.vmSwapMb);

      console.log(
        `[INFERENCE_HEARTBEAT] ⏳ Processing... (elapsed: ${elapsed}s) | RAM: ${snap.vmRssMb} MB | Process Swap: ${snap.vmSwapMb} MB`
      );
    }, 10000);

    let rawContent = "";
    let usage: any = null;
    let timings: any = null;

    try {
      const response = await postOpenAIChatCompletion(`${serverUrl}/v1/chat/completions`, openAiPayload);
      rawContent = response.choices?.[0]?.message?.content || "";
      usage = response.usage;
      timings = response.timings;
    } finally {
      clearInterval(progressTimer);
    }

    const totalDurationMs = Math.round(performance.now() - startTime);
    const cpuMetrics = cpuSampler.stop();

    // Finalize Swap Stats
    const finalSnap = getMemorySnapshot();
    peakProcessSwapMb = Math.max(peakProcessSwapMb, finalSnap.vmSwapMb);
    const vmstatEnd = getVmstatSwap();
    const swapOutPages = Math.max(0, vmstatEnd.pswpout - vmstatStart.pswpout);
    const swapInPages = Math.max(0, vmstatEnd.pswpin - vmstatStart.pswpin);

    const swapMetrics: SwapActivityMetrics = {
      swappiness: finalSnap.swappiness,
      server_pid: finalSnap.pid,
      server_vm_rss_mb: finalSnap.vmRssMb,
      peak_server_swap_mb: peakProcessSwapMb,
      final_server_swap_mb: finalSnap.vmSwapMb,
      system_swap_used_mb: finalSnap.systemSwapUsedMb,
      system_swap_total_mb: finalSnap.systemSwapTotalMb,
      swap_bytes_written_mb: Number(((swapOutPages * 4) / 1024).toFixed(2)),
      swap_bytes_read_mb: Number(((swapInPages * 4) / 1024).toFixed(2)),
    };

    // Calculate Ingestion vs Generation Speeds
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
      ? Number((promptTokens / (promptTimeMs / 1000)).toFixed(2))
      : 0;

    const completionTokensPerSec = timings?.predicted_per_second
      ? Number(timings.predicted_per_second.toFixed(2))
      : completionTimeMs > 0
      ? Number((completionTokens / (completionTimeMs / 1000)).toFixed(2))
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

    console.log(`⏱️ Duration: ${(totalDurationMs / 1000).toFixed(2)}s | CPU Peak: ${cpuMetrics.maxCpuPercent}% | Ingest: ${tokenMetrics.prompt_tokens_per_second} t/s | Gen: ${tokenMetrics.completion_tokens_per_second} t/s\n`);

    this.logEvent("INFERENCE_COMPLETED", {
      modelName,
      sourceType: sourceAudit.sourceType,
      tokenMetrics,
      swapMetrics,
      cpuMetrics,
      rawOutput: rawContent,
    });

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
        stance_on_change: "not_applicable",
        stance_on_economic_power: "not_applicable",
        stance_on_state_power: "not_applicable",
        stance_on_borders: "not_applicable",
        stance_on_personal_sphere: "not_applicable",
      };
    }

    // Transparent Compression Calculation
    const inLen = targetText.length || 1;
    const outLen = rawContent.length;
    const retentionPct = ((outLen / inLen) * 100).toFixed(1);
    const reductionPct = Math.max(0, 100 - parseFloat(retentionPct)).toFixed(1);

    const compression: CompressionAnalysis = {
      inputChars: inLen,
      outputChars: outLen,
      retentionRatioPercent: `${retentionPct}%`,
      reductionRatioPercent: `${reductionPct}%`,
      explanation: `Retention Ratio = (Output Chars / Input Chars) * 100%. The summary retains ${retentionPct}% of the raw text size, corresponding to a ${reductionPct}% content reduction.`,
    };

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || sourceAudit.sourceTitle || "Summary Output",
      executive_summary: parsed.executive_summary || rawContent,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      stance_on_change: parsed.stance_on_change || "not_applicable",
      stance_on_economic_power: parsed.stance_on_economic_power || "not_applicable",
      stance_on_state_power: parsed.stance_on_state_power || "not_applicable",
      stance_on_borders: parsed.stance_on_borders || "not_applicable",
      stance_on_personal_sphere: parsed.stance_on_personal_sphere || "not_applicable",
      compression,
      raw_output: rawContent,
      source_audit: sourceAudit,
      token_metrics: tokenMetrics,
      swap_metrics: swapMetrics,
      cpu_metrics: cpuMetrics,
      host_fingerprint: this.hostFingerprint,
      runner_metadata: this.runnerMetadata,
      input_text: targetText,
      system_prompt: openAiPayload.messages[0].content,
      user_prompt: userPromptContent,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 8. GITHUB STEP SUMMARY (Zero-Indent CommonMark)
// -------------------------------------------------------------
function publishStepSummary(
  modelName: string,
  result: SummaryStructuredOutput,
  events: PipelineEvent[]
) {
  const tm = result.token_metrics;
  const sm = result.swap_metrics;
  const cm = result.cpu_metrics;
  const hf = result.host_fingerprint;
  const rm = result.runner_metadata;
  const sa = result.source_audit;
  const comp = result.compression;

  // Annotated Notice including Host Fingerprint & Max CPU
  console.log(
    `::notice title=AI Pipeline Succeeded (${modelName})::🖥️ ${hf.rawFingerprint} | ⚡ Max CPU: ${cm.maxCpuPercent}% | 📥 Ingest: ${tm.prompt_tokens_per_second} t/s | ⚡ Gen: ${tm.completion_tokens_per_second} t/s | 💾 Peak Swap: ${sm.peak_server_swap_mb} MB`
  );

  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const lines: string[] = [
    `# 🧠 AI Transformer Pipeline Execution Report`,
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
    `## 🧭 Content Stance & Ideological Alignment`,
    ``,
    `| Axis | Classification | Question Evaluated |`,
    `| :--- | :--- | :--- |`,
    `| **General Sentiment** | \`${result.sentiment.toUpperCase()}\` | Overall emotional and qualitative tone |`,
    `| **Stance on Change** | \`${result.stance_on_change}\` | What to do about the existing arrangement |`,
    `| **Stance on Economic Power** | \`${result.stance_on_economic_power}\` | Who should hold economic power |`,
    `| **Stance on State Power** | \`${result.stance_on_state_power}\` | Whether a power the state holds was properly checked |`,
    `| **Stance on Borders** | \`${result.stance_on_borders}\` | Whether the answer is inside or outside the border |`,
    `| **Stance on Personal Sphere** | \`${result.stance_on_personal_sphere}\` | Whether a person keeps an inviolable personal sphere |`,
    ``,
    `---`,
    ``,
    `## 🖥️ Host & System Diagnostics`,
    ``,
    `### ⚙️ Host Machine & Hardware Fingerprint`,
    `| Hardware Component | Detected Host Specification |`,
    `| :--- | :--- |`,
    `| **Host Machine CPU** | \`${hf.cpuModel}\` |`,
    `| **Allocated Core Count** | **${hf.coreCount} physical/vCPU cores** |`,
    `| **L3 Cache Size** | **${hf.l3Cache}** |`,
    `| **SIMD / Vector Acceleration** | \`${hf.avxFlags.join(", ")}\` |`,
    `| **Total Physical RAM** | **${hf.totalRamGb}** |`,
    ``,
    `### 🏃 GitHub Actions Runner & Model Telemetry`,
    `| Attribute | Context Value |`,
    `| :--- | :--- |`,
    `| **Runner Name** | \`${rm.runnerName || "Self-Hosted / Local"}\` |`,
    `| **GitHub Run ID** | \`${rm.runId || "N/A"}\` |`,
    `| **GitHub Run Number** | \`#${rm.runNumber || "1"}\` |`,
    `| **Runner OS & Architecture** | \`${rm.osArch}\` |`,
    `| **HF Repo / Model Family** | \`${rm.modelFamily || "N/A"}\` |`,
    `| **Model File / ID** | \`${modelName}${rm.requestedModelId ? " (Explicit: " + rm.requestedModelId + ")" : " (Auto-detected)"}\` |`,
    `| **Workflow Name** | \`${rm.workflow || "CI"}\` |`,
    `| **Job / Shard ID** | \`${rm.shardId || "N/A"}\` |`,
    ``,
    `### 📈 CPU Utilization Dynamics (Inference Phase)`,
    `| Metric | Recorded Value | Measurement Details |`,
    `| :--- | :--- | :--- |`,
    `| **Peak CPU Utilization** | **\`${cm.maxCpuPercent}%\`** | Highest instantaneous utilization across all cores |`,
    `| **Average CPU Utilization** | **\`${cm.avgCpuPercent}%\`** | Mean CPU load over ${cm.samplesTaken} samples |`,
    `| **Inference Parallelism** | **${hf.coreCount} threads** | Threads configured for \`llama-server\` |`,
    ``,
    `### 💾 Memory & Linux Swap Diagnostics`,
    `| Metric | Measured Value | Health Status |`,
    `| :--- | :--- | :--- |`,
    `| **Linux \`vm.swappiness\`** | **\`${sm.swappiness}\`** | ${sm.swappiness <= 10 ? "✅ Low Paging (Optimized)" : "⚠️ High Paging"} |`,
    `| **Server Process PID** | \`${sm.server_pid ?? ""}\` | Background Daemon |`,
    `| **Server RAM (RSS)** | **${sm.server_vm_rss_mb} MB** | In Physical Memory |`,
    `| **Peak Process Swap** | **${sm.peak_server_swap_mb} MB** | ${sm.peak_server_swap_mb > 0 ? "⚠️ Process Swapped" : "✅ 0 MB (Zero Process Swap)"} |`,
    `| **Final Process Swap** | **${sm.final_server_swap_mb} MB** | Current Swap Allocation |`,
    `| **Swap Written to SSD** | **${sm.swap_bytes_written_mb} MB** | Pages Paged Out |`,
    `| **Swap Read from SSD** | **${sm.swap_bytes_read_mb} MB** | Pages Paged In |`,
    `| **Total System Swap Used** | \`${sm.system_swap_used_mb} MB / ${sm.system_swap_total_mb} MB\` | Allocated Swapfile Space |`,
    ``,
    `---`,
    ``,
    `## 📝 Structured Summary: *"${result.headline}"*`,
    ``,
    `### Comprehensive Executive Summary:`,
    result.executive_summary,
    ``,
    `### Core Takeaways:`,
    ...result.key_points.map((p) => `- ${p}`),
    ``,
    `### 📊 Text Compression & Reduction Analysis`,
    `| Metric | Value | Explanation & Formula |`,
    `| :--- | :--- | :--- |`,
    `| **Raw Input Size** | \`${comp.inputChars} chars\` | Character count of input text ingested by the model |`,
    `| **Model Output Size** | \`${comp.outputChars} chars\` | Total characters produced in model completion |`,
    `| **Retention Ratio** | **\`${comp.retentionRatioPercent}\`** | **\`(Output Chars / Input Chars) * 100%\`** (Proportion of original volume retained) |`,
    `| **Content Reduction** | **\`${comp.reductionRatioPercent}\`** | **\`100% - Retention Ratio\`** (Space saved through summarization) |`,
    ``,
    `---`,
    ``,
    `## 📝 Full Input Prompt (System + User Prompt)`,
    `<details open>`,
    `<summary><b>Click to collapse/expand exact prompt payload sent to model</b></summary>`,
    ``,
    `### System Prompt:`,
    `\`\`\`text`,
    result.system_prompt,
    `\`\`\``,
    ``,
    `### User Prompt:`,
    `\`\`\`text`,
    result.user_prompt,
    `\`\`\``,
    ``,
    `</details>`,
    ``,
    `---`,
    ``,
    `## 📄 Full Input Text (Source Material)`,
    `<details open>`,
    `<summary><b>Click to collapse/expand input text (${sa.extractedWordCount} words, ${sa.extractedCharCount} chars)</b></summary>`,
    ``,
    `\`\`\`markdown`,
    result.input_text,
    `\`\`\``,
    ``,
    `</details>`,
    ``,
    `---`,
    ``,
    `## 🤖 Verbatim Raw Model Output`,
    `<details open>`,
    `<summary><b>Click to collapse/expand raw model output</b></summary>`,
    ``,
    `\`\`\`text`,
    result.raw_output,
    `\`\`\``,
    ``,
    `</details>`,
    ``,
    `---`,
    ``,
    `## ⚡ Event-Driven Audit Trail (RFC 4122 UUIDv5)`,
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
// 9. MAIN ENTRY POINT
// -------------------------------------------------------------
async function main() {
  const runnerMetadata: RunnerMetadata = {
    runnerName: process.env.RUNNER_NAME ?? "",
    runId: process.env.GITHUB_RUN_ID ?? "",
    runNumber: process.env.GITHUB_RUN_NUMBER ?? "",
    workflow: process.env.GITHUB_WORKFLOW ?? "",
    osArch: `${os.type()} ${os.arch()} (${os.release()})`,
    shardId: process.env.SHARD_ID ?? "",
    modelFamily: process.env.MODEL_FAMILY ?? "",
    requestedModelId: process.env.REQUESTED_MODEL_ID ?? "",
  };

  const modelName = process.env.MODEL_NAME ?? "";
  const serverUrl = process.env.SERVER_URL;

  if (!serverUrl) {
    throw new Error("Missing required environment variable: SERVER_URL");
  }
  if (!modelName) {
    throw new Error("Missing required environment variable: MODEL_NAME");
  }

  const rawUrl = (process.env.URL ?? "").trim();
  const rawInputText = (process.env.INPUT_TEXT ?? "").trim();
  const prompt = (process.env.PROMPT ?? "").trim();

  if (!prompt) {
    throw new Error("Missing required environment variable: PROMPT");
  }
  if (!rawUrl && !rawInputText) {
    throw new Error("No input provided: Both URL and INPUT_TEXT environment variables are empty.");
  }

  const hostFingerprint = getHostFingerprint();

  console.log("=== Host & Environment Configuration ===");
  console.log({
    hostFingerprint: hostFingerprint.rawFingerprint,
    l3Cache: hostFingerprint.l3Cache,
    avxFlags: hostFingerprint.avxFlags,
    runnerMetadata,
    modelName,
    serverUrl,
    hasUrl: Boolean(rawUrl),
    hasInputText: Boolean(rawInputText),
  });

  const pipeline = new AIEventPipeline(runnerMetadata);

  try {
    const result = await pipeline.execute({
      url: rawUrl,
      fallbackText: rawInputText,
      systemPrompt: prompt,
      serverUrl,
      modelName,
    });

    console.log("============================================================");
    console.log("🎯 PARSED STRUCTURED JSON RESULT:");
    console.log("============================================================");
    console.log(JSON.stringify(result, null, 2));
    console.log("============================================================\n");

    publishStepSummary(modelName, result, pipeline.getEventHistory());
    console.log("Pipeline run completed successfully. JSONL saved to pipeline-events.jsonl");
  } catch (err: any) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
