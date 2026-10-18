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
import { parseFeed } from "feedsmith";
import { TidyURL } from "tidy-url";

// -------------------------------------------------------------
// 0. CONFIGURATION & CONSTANTS
// -------------------------------------------------------------
export const DEFAULT_FEED_URLS: string[] = [
  "https://www.nakedcapitalism.com/feed",
  "https://www.aljazeera.com/xml/rss/all.xml",
  "https://oilprice.com/rss/main",
  "https://jomodevplus.substack.com/feed",
  "https://wolfstreet.com/feed",
  "https://neuburger.substack.com/feed",
  "https://creditslips.org/feed",
  "https://www.thebignewsletter.com/feed",
  "https://angrybearblog.com/feed",
];

export const DEFAULT_FALLBACK_ARTICLE_URL =
  "https://www.nakedcapitalism.com/2026/10/when-will-politicians-turn-to-mmt.html";

export const PYTHON_EVAL_SERVER_URL = "http://127.0.0.1:9933";
export const DEFAULT_BLOCKED_CATEGORIES: string[] = ["Links", "Show Types"];

export interface ModelInferenceParams {
  temperature: number;
  top_k: number;
  top_p: number;
  min_p: number;
  repeat_penalty: number;
  max_tokens: number;
}

export const DEFAULT_INFERENCE_PARAMS: ModelInferenceParams = {
  temperature: 0.2,
  top_k: 40,
  top_p: 0.95,
  min_p: 0.05,
  repeat_penalty: 1.15,
  max_tokens: 4096,
};

export const STRICT_SUMMARY_JSON_SCHEMA = {
  type: "object",
  properties: {
    headline: { type: "string" },
    analytic_synthesis: { type: "string" },
    sentiment: { type: "string", enum: ["positive", "neutral", "negative", "mixed"] },
    stance_on_change: { type: "string", enum: ["conservatism", "progressivism", "not_applicable"] },
    stance_on_economic_power: { type: "string", enum: ["socialism", "libertarianism", "not_applicable"] },
    stance_on_state_power: { type: "string", enum: ["statism", "constitutionalism", "not_applicable"] },
    stance_on_borders: { type: "string", enum: ["nationalism", "internationalism", "not_applicable"] },
    stance_on_personal_sphere: { type: "string", enum: ["civil_libertarianism", "communitarianism", "not_applicable"] },
  },
  required: [
    "headline",
    "analytic_synthesis",
    "sentiment",
    "stance_on_change",
    "stance_on_economic_power",
    "stance_on_state_power",
    "stance_on_borders",
    "stance_on_personal_sphere",
  ],
  additionalProperties: false,
};

// -------------------------------------------------------------
// 1. STRUCTURED JSONL LOGGER & UUIDs
// -------------------------------------------------------------
const UUIDV5_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

export function logStructured(level: "INFO" | "WARN" | "ERROR", message: string, meta: Record<string, any> = {}): void {
  const record = {
    timestamp: new Date().toISOString(),
    level,
    message,
    ...meta,
  };
  process.stdout.write(JSON.stringify(record) + "\n");
}

function uuidToBytes(uuid: string): Buffer {
  return Buffer.from(uuid.replace(/-/g, ""), "hex");
}

export function generateUuidV5(name: string, namespace: string = UUIDV5_NAMESPACE): string {
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

export function buildDeterministicEventId(runnerName: string, shardId: string, sourceUrl: string, eventType: string): string {
  const seed = `runner:${runnerName}:shard:${shardId}:source:${sourceUrl}:event:${eventType}`;
  return `evt-${generateUuidV5(seed)}`;
}

// -------------------------------------------------------------
// 2. CATEGORY BLOCKLIST & URL TIDYING
// -------------------------------------------------------------
export function evaluateCategoryBlock(
  categories: any[],
  url: string,
  blockedCategories: string[] = DEFAULT_BLOCKED_CATEGORIES
): { isBlocked: boolean; matchedReason?: string } {
  const normalizedBlocked = blockedCategories.map((c) => c.toLowerCase().trim());

  const itemCategories = categories.map((c: any) =>
    (typeof c === "string" ? c : c?.name || c?.term || c?.value || "").toLowerCase().trim()
  );

  for (const cat of itemCategories) {
    if (normalizedBlocked.includes(cat)) {
      return { isBlocked: true, matchedReason: `Element category matched: "${cat}"` };
    }
  }

  const lowerUrl = url.toLowerCase();
  for (const blocked of normalizedBlocked) {
    const slug = blocked.replace(/\s+/g, "-");
    if (lowerUrl.includes(`/category/${slug}`) || lowerUrl.includes(`/${slug}/`)) {
      return { isBlocked: true, matchedReason: `URL slug matched blocked category: "${blocked}"` };
    }
  }

  return { isBlocked: false };
}

export function cleanUrlWithTidy(rawUrl: string): { cleanUrl: string; wasCleaned: boolean; reduction: number } {
  try {
    const res = TidyURL.clean(rawUrl);
    const cleanUrl = res.url || rawUrl;
    return { cleanUrl, wasCleaned: cleanUrl !== rawUrl, reduction: res.info?.reduction || 0 };
  } catch {
    return { cleanUrl: rawUrl, wasCleaned: false, reduction: 0 };
  }
}

// -------------------------------------------------------------
// 3. HARDWARE FINGERPRINT & CPU SAMPLER
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
  const totalRamGb = (os.totalmem() / 1024 ** 3).toFixed(2) + " GB";
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
      const idle = parts[3] + (parts[4] || 0);
      const nonIdle = parts[0] + parts[1] + parts[2] + (parts[5] || 0) + (parts[6] || 0) + (parts[7] || 0);
      return { total: idle + nonIdle, idle };
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
// 4. DATA SCHEMAS & INTERFACES
// -------------------------------------------------------------
export type StanceOnChange = "conservatism" | "progressivism" | "not_applicable";
export type StanceOnEconomicPower = "socialism" | "libertarianism" | "not_applicable";
export type StanceOnStatePower = "statism" | "constitutionalism" | "not_applicable";
export type StanceOnBorders = "nationalism" | "internationalism" | "not_applicable";
export type StanceOnPersonalSphere = "civil_libertarianism" | "communitarianism" | "not_applicable";

export interface ShallowClassificationResult {
  classification: string;
  reason: string;
  passed: boolean;
}

export interface DeepClassificationResult {
  classification: string;
  wordCount: number;
  linkDensity: number;
  listCount: number;
  passed: boolean;
  reason: string;
}

export interface FeedArticleCandidate {
  title: string;
  url: string;
  cleanedUrl?: string;
  sourceFeed: string;
  publishedDate?: string;
  ageHours?: number;
  shallowResult?: ShallowClassificationResult;
  deepResult?: DeepClassificationResult;
  extractedMarkdown?: string;
}

export interface FeedSelectionAudit {
  configuredFeeds: string[];
  maxAgeHours: number;
  goalCount: number;
  evaluatedArticles: FeedArticleCandidate[];
  acceptedArticles: FeedArticleCandidate[];
  usedFallback: boolean;
}

export interface SourceAudit {
  sourceType: "FEED" | "FEED_DEFAULT_FALLBACK" | "URL" | "INPUT_TEXT" | "FALLBACK_INPUT_TEXT";
  sourceIdentifier: string;
  sourceTitle: string;
  extractedWordCount: number;
  extractedCharCount: number;
  extractedText: string;
  scrapeError?: string;
  feedAudit?: FeedSelectionAudit;
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
  page_size_bytes: number;
  is_cgroup_constrained: boolean;
  diagnostics_error?: string;
}

export interface CompressionAnalysis {
  inputChars: number;
  outputChars: number;
  retentionRatioPercent: string;
  reductionRatioPercent: string;
  explanation: string;
}

export interface SentenceGroundingDetail {
  sentence_index: number;
  text: string;
  score: number;
  matched_chunk: number;
  supported: boolean;
  source_sentence?: string;
  reason?: string;
}

export interface UncoveredSectionDetail {
  chunk_index: number;
  chunk_total: number;
  excerpt: string;
  max_similarity_score: number;
  reason: string;
}

export interface QualityEvaluationMetrics {
  overall_consistency: number;
  coherence: number;
  fluency: number;
  document_chunks_total: number;
  document_chunks_covered: number;
  chunk_coverage_percent: number;
  sentence_breakdown: SentenceGroundingDetail[];
  uncovered_sections?: UncoveredSectionDetail[];
}

export interface SummaryStructuredOutput {
  headline: string;
  analytic_synthesis: string;
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
  inference_params: ModelInferenceParams;
  input_text: string;
  system_prompt: string;
  user_prompt: string;
  quality_metrics?: QualityEvaluationMetrics;
}

export interface PipelineEvent<T = any> {
  eventId: string;
  eventType: string;
  timestamp: string;
  correlationId: string;
  durationMs: number;
  cumulativeMs: number;
  payload: T;
}

// -------------------------------------------------------------
// 5. CLASSIFIERS
// -------------------------------------------------------------
export function shallowClassify(item: any, rawUrl: string): ShallowClassificationResult {
  const categories = item.categories || item.tags || [];
  const catCheck = evaluateCategoryBlock(categories, rawUrl);
  if (catCheck.isBlocked) {
    return {
      classification: "BLOCKED_BY_CATEGORY",
      reason: catCheck.matchedReason || "Category blocklist match",
      passed: false,
    };
  }

  if (
    item.enclosure?.type?.startsWith("audio/") ||
    item.enclosure?.type?.startsWith("video/") ||
    item.enclosures?.some((e: any) => e.type?.startsWith("audio/") || e.type?.startsWith("video/"))
  ) {
    return {
      classification: "PODCAST_OR_VIDEO",
      reason: `Media enclosure detected (${item.enclosure?.type || "audio/video"})`,
      passed: false,
    };
  }

  const link = (item.link || item.url || rawUrl || "").toLowerCase();
  if (/youtube\.com|youtu\.be|spotify\.com|apple\.com\/podcast|soundcloud\.com|vimeo\.com/i.test(link)) {
    return {
      classification: "PODCAST_OR_VIDEO",
      reason: `URL belongs to multimedia streaming host (${link})`,
      passed: false,
    };
  }

  const title = item.title || "";
  if (/\b(links|roundup|daily digest|morning reads|weekly wrap|news wrap)\b/i.test(title) || /^links\s+\d+/i.test(title)) {
    return {
      classification: "NEWSLETTER_ROUNDUP_DIGEST",
      reason: `Title heuristic matched roundup format ("${title}")`,
      passed: false,
    };
  }

  return {
    classification: "ARTICLE_CANDIDATE",
    reason: "Passed all shallow pre-fetch heuristics",
    passed: true,
  };
}

export function deepClassify(cleanMarkdown: string, wordCount: number): DeepClassificationResult {
  const sample = cleanMarkdown.slice(0, 600);
  if (/\b(FOR IMMEDIATE RELEASE|BUSINESS WIRE|PR NEWSWIRE|GLOBE NEWSWIRE|NEWS PROVIDED BY)\b/i.test(sample)) {
    return {
      classification: "PRESS_RELEASE_SPONSORED",
      wordCount,
      linkDensity: 0,
      listCount: 0,
      passed: false,
      reason: "Detected PR wire service boilerplate in opening prose",
    };
  }

  const linkMatches = cleanMarkdown.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g);
  let linkChars = 0;
  for (const m of linkMatches) {
    linkChars += m[1].length;
  }
  const totalChars = Math.max(1, cleanMarkdown.length);
  const linkDensity = Number((linkChars / totalChars).toFixed(2));

  const listLines = cleanMarkdown.split("\n").filter((line) => /^\s*([-*+]|\d+\.)\s+/.test(line));
  const listCount = listLines.length;

  if (linkDensity > 0.4 || (listCount > 10 && wordCount < 150)) {
    return {
      classification: "ROUNDUP_DIGEST",
      wordCount,
      linkDensity,
      listCount,
      passed: false,
      reason: `High link density (${linkDensity} > 0.40) or excessive list items (${listCount}) with low prose`,
    };
  }

  if (wordCount < 150) {
    return {
      classification: "THIN_CONTENT",
      wordCount,
      linkDensity,
      listCount,
      passed: false,
      reason: `Insufficient clean prose volume (${wordCount} words < 150)`,
    };
  }

  const classification = wordCount >= 700 ? "LONGFORM_ARTICLE" : "SHORT_ARTICLE";
  return {
    classification,
    wordCount,
    linkDensity,
    listCount,
    passed: true,
    reason: `Clean article prose confirmed (${wordCount} words, link density ${linkDensity})`,
  };
}

// -------------------------------------------------------------
// 6. ZERO-PROXY RESILIENT EXTRACTION ENGINE
// -------------------------------------------------------------
const PRIMARY_BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
  "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
  "Sec-CH-UA-Mobile": "?0",
  "Sec-CH-UA-Platform": '"Windows"',
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
  "Sec-Fetch-User": "?1",
  "Upgrade-Insecure-Requests": "1",
};

const SECONDARY_BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:132.0) Gecko/20100101 Firefox/132.0",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.5",
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
  "Upgrade-Insecure-Requests": "1",
};

async function fetchHtmlWithFallback(url: string): Promise<string> {
  // Attempt 1: Primary Browser Footprint (Chrome/Win)
  try {
    const res = await fetch(url, { headers: PRIMARY_BROWSER_HEADERS, signal: AbortSignal.timeout(12000) });
    if (res.ok) {
      const html = await res.text();
      if (html.length > 200) return html;
    }
    logStructured("WARN", "Primary fetch returned non-200 or short response, retrying with secondary UA", {
      url,
      status: res.status,
    });
  } catch (err: any) {
    logStructured("WARN", "Primary fetch encountered network error, retrying with secondary UA", {
      url,
      error: err.message,
    });
  }

  // Attempt 2: Secondary Browser Footprint (Firefox/macOS)
  const res2 = await fetch(url, { headers: SECONDARY_BROWSER_HEADERS, signal: AbortSignal.timeout(15000) });
  if (!res2.ok) {
    throw new Error(`Direct fetch failed with HTTP ${res2.status} on all user-agent profiles`);
  }
  const html2 = await res2.text();
  if (html2.length < 200) {
    throw new Error(`Fetched HTML body below operational minimum (${html2.length} bytes)`);
  }
  return html2;
}

function extractSemanticDomFallback(document: any): { title: string; content: string; wordCount: number } {
  const title =
    document.querySelector("meta[property='og:title']")?.getAttribute("content") ||
    document.querySelector("title")?.textContent?.trim() ||
    "Extracted Document";

  // Remove non-content structural noise
  const removeSelectors = [
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "noscript",
    "iframe",
    "form",
    "svg",
    "button",
    ".ad",
    ".advertisement",
    ".social-share",
    ".cookie-banner",
    ".comments",
  ];

  for (const sel of removeSelectors) {
    try {
      const elements = document.querySelectorAll(sel);
      for (const el of elements) {
        el.parentNode?.removeChild(el);
      }
    } catch {}
  }

  // Candidate containers
  const containerSelectors = [
    "article",
    "main",
    '[role="main"]',
    ".post-content",
    ".article-content",
    ".entry-content",
    "#content",
    ".story-body",
  ];

  let selectedRoot: any = null;
  for (const sel of containerSelectors) {
    const match = document.querySelector(sel);
    if (match && (match.textContent || "").trim().length > 300) {
      selectedRoot = match;
      break;
    }
  }

  if (!selectedRoot) {
    selectedRoot = document.body || document;
  }

  const paragraphs: string[] = [];
  const nodes = selectedRoot.querySelectorAll("h1, h2, h3, h4, p, blockquote, li");
  for (const node of nodes) {
    const txt = (node.textContent || "").replace(/\s+/g, " ").trim();
    if (txt.length > 25) {
      paragraphs.push(txt);
    }
  }

  let combined = paragraphs.join("\n\n").trim();

  // If prose is still short, inspect meta description
  if (combined.split(/\s+/).length < 60) {
    const metaDesc =
      document.querySelector("meta[name='description']")?.getAttribute("content") ||
      document.querySelector("meta[property='og:description']")?.getAttribute("content");
    if (metaDesc && metaDesc.trim().length > 30) {
      combined = `${metaDesc.trim()}\n\n${combined}`.trim();
    }
  }

  const wordCount = combined.split(/\s+/).filter(Boolean).length;
  return { title, content: combined, wordCount };
}

export async function extractDirectUrl(
  url: string,
  emitEvent: (type: string, payload: any) => void
): Promise<{ title: string; content: string; wordCount: number }> {
  emitEvent("URL_HTTP_FETCH_STARTED", { url });
  logStructured("INFO", "Beginning direct URL extraction", { url });

  const html = await fetchHtmlWithFallback(url);
  emitEvent("URL_HTTP_FETCH_COMPLETED", { url, bytes: Buffer.byteLength(html, "utf8") });

  const { document } = parseHTML(html);

  // Tier 1: Defuddle article parsing
  try {
    const defuddleResult: any = await Defuddle(document, url, { markdown: true, useAsync: false });
    const content = defuddleResult.content?.trim() || "";
    const wordCount = content.split(/\s+/).filter(Boolean).length;

    if (wordCount >= 50) {
      const title = defuddleResult.title || document.title || "Web Document";
      emitEvent("URL_DEFUDDLE_EXTRACTED", { url, title, wordCount });
      logStructured("INFO", "Successfully extracted article via Defuddle (Tier 1)", { url, title, wordCount });
      return { title, content, wordCount };
    }
    logStructured("WARN", "Defuddle extraction yielded thin prose (< 50 words). Engaging Tier 2 fallback.", {
      url,
      defuddleWords: wordCount,
    });
  } catch (err: any) {
    logStructured("WARN", "Defuddle parse threw error. Engaging Tier 2 fallback.", { url, error: err.message });
  }

  // Tier 2: Semantic Linkedom DOM Fallback
  const fallback = extractSemanticDomFallback(document);
  if (fallback.wordCount >= 50) {
    emitEvent("URL_SEMANTIC_DOM_EXTRACTED", { url, title: fallback.title, wordCount: fallback.wordCount });
    logStructured("INFO", "Successfully extracted article via Semantic Linkedom (Tier 2)", {
      url,
      title: fallback.title,
      wordCount: fallback.wordCount,
    });
    return fallback;
  }

  throw new Error(`All extraction tiers failed to yield minimum content (wordCount: ${fallback.wordCount})`);
}

// -------------------------------------------------------------
// 7. FEED HARVESTING & ROUND-ROBIN DISTRIBUTION
// -------------------------------------------------------------
function normalizeFeedEntries(parsedResult: any): Array<{ title: string; url: string; publishedDate: Date | null; rawItem: any }> {
  const { format, feed } = parsedResult;
  if (!feed) return [];

  const rawEntries = format === "atom" ? feed.entries || [] : feed.items || [];
  const normalized: Array<{ title: string; url: string; publishedDate: Date | null; rawItem: any }> = [];

  for (const item of rawEntries) {
    const title = (item.title || "").trim();
    let url = "";

    if (format === "atom") {
      if (Array.isArray(item.links) && item.links.length > 0) {
        const alt = item.links.find((l: any) => l.rel === "alternate" || !l.rel);
        url = (alt?.href || item.links[0]?.href || "").trim();
      } else if (typeof item.link === "string") {
        url = item.link.trim();
      }
      if (!url && item.id && item.id.startsWith("http")) {
        url = item.id.trim();
      }
    } else if (format === "json") {
      url = (item.url || item.id || "").trim();
    } else {
      url = (item.link || item.guid?.value || (typeof item.guid === "string" ? item.guid : "") || "").trim();
    }

    const rawDate = item.pubDate || item.published || item.updated || item.date_published || item.dc?.date;
    let publishedDate: Date | null = null;
    if (rawDate) {
      const d = new Date(rawDate);
      if (!isNaN(d.getTime())) publishedDate = d;
    }

    if (url) {
      normalized.push({ title: title || "Untitled Feed Item", url, publishedDate, rawItem: item });
    }
  }

  return normalized;
}

async function collectAndClassifyFeedArticles(
  feedUrls: string[],
  maxAgeHours: number,
  goalCount: number,
  emitEvent: (type: string, payload: any) => void
): Promise<FeedSelectionAudit> {
  emitEvent("FEED_DISCOVERY_STARTED", { feedUrls, maxAgeHours, goalCount });
  logStructured("INFO", "Querying RSS/Atom feeds concurrently", { count: feedUrls.length, goalCount, maxAgeHours });

  const cutoffMs = Date.now() - maxAgeHours * 60 * 60 * 1000;

  const feedResponses = await Promise.allSettled(
    feedUrls.map(async (rawUrl) => {
      const url = rawUrl.startsWith("http://") || rawUrl.startsWith("https://") ? rawUrl : `https://${rawUrl}`;
      const res = await fetch(url, { headers: PRIMARY_BROWSER_HEADERS, signal: AbortSignal.timeout(12000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.text();
      return { url, body };
    })
  );

  interface FeedQueueBucket {
    feedUrl: string;
    entries: Array<{ title: string; url: string; publishedDate: Date | null; rawItem: any }>;
  }

  const validBuckets: FeedQueueBucket[] = [];

  for (const resp of feedResponses) {
    if (resp.status !== "fulfilled") {
      emitEvent("FEED_QUERY_FAILED", { error: resp.reason?.message || "Unknown error" });
      continue;
    }

    const { url: feedUrl, body } = resp.value;
    try {
      const parsed = parseFeed(body);
      const entries = normalizeFeedEntries(parsed);
      emitEvent("FEED_QUERY_SUCCESS", { feedUrl, format: parsed.format, rawEntriesCount: entries.length });

      const filtered = entries.filter((entry) => {
        if (!entry.publishedDate) return true;
        return entry.publishedDate.getTime() >= cutoffMs;
      });

      filtered.sort((a, b) => (b.publishedDate?.getTime() || 0) - (a.publishedDate?.getTime() || 0));

      if (filtered.length > 0) {
        validBuckets.push({ feedUrl, entries: filtered });
      }
    } catch (err: any) {
      emitEvent("FEED_QUERY_FAILED", { feedUrl, error: err.message });
    }
  }

  const roundRobinCandidates: Array<{ feedUrl: string; entry: (typeof validBuckets)[0]["entries"][0] }> = [];
  const maxEntriesPerFeed = Math.max(0, ...validBuckets.map((b) => b.entries.length));

  for (let depth = 0; depth < maxEntriesPerFeed; depth++) {
    for (const bucket of validBuckets) {
      if (depth < bucket.entries.length) {
        roundRobinCandidates.push({ feedUrl: bucket.feedUrl, entry: bucket.entries[depth] });
      }
    }
  }

  const evaluatedArticles: FeedArticleCandidate[] = [];
  const acceptedArticles: FeedArticleCandidate[] = [];
  const seenUrls = new Set<string>();

  for (const item of roundRobinCandidates) {
    if (acceptedArticles.length >= goalCount) break;

    const { feedUrl, entry } = item;
    const tidyResult = cleanUrlWithTidy(entry.url);
    const targetUrl = tidyResult.cleanUrl;

    if (seenUrls.has(targetUrl)) continue;
    seenUrls.add(targetUrl);

    if (tidyResult.wasCleaned) {
      emitEvent("URL_TIDIED", { originalUrl: entry.url, cleanUrl: targetUrl, reduction: tidyResult.reduction });
    }

    const ageHours = entry.publishedDate
      ? Number(((Date.now() - entry.publishedDate.getTime()) / (1000 * 60 * 60)).toFixed(1))
      : 0;

    const shallowResult = shallowClassify(entry.rawItem, targetUrl);
    emitEvent("SHALLOW_CLASSIFICATION_EVALUATED", { url: targetUrl, title: entry.title, shallowResult });

    const candidate: FeedArticleCandidate = {
      title: entry.title,
      url: targetUrl,
      cleanedUrl: targetUrl,
      sourceFeed: feedUrl,
      publishedDate: entry.publishedDate?.toISOString(),
      ageHours,
      shallowResult,
    };

    if (!shallowResult.passed) {
      logStructured("INFO", "Candidate rejected by shallow classifier", {
        title: entry.title,
        reason: shallowResult.reason,
      });
      evaluatedArticles.push(candidate);
      continue;
    }

    logStructured("INFO", "Attempting extraction for candidate", { title: entry.title, url: targetUrl });
    try {
      const extracted = await extractDirectUrl(targetUrl, emitEvent);
      candidate.extractedMarkdown = extracted.content;
      candidate.title = extracted.title || candidate.title;

      const deepResult = deepClassify(extracted.content, extracted.wordCount);
      candidate.deepResult = deepResult;
      emitEvent("DEEP_CLASSIFICATION_EVALUATED", { url: targetUrl, title: candidate.title, deepResult });
      evaluatedArticles.push(candidate);

      if (deepResult.passed) {
        acceptedArticles.push(candidate);
        logStructured("INFO", "Article candidate passed deep classification", {
          title: candidate.title,
          wordCount: deepResult.wordCount,
          acceptedCount: acceptedArticles.length,
          goalCount,
        });
      } else {
        logStructured("WARN", "Article rejected by deep classifier", {
          title: candidate.title,
          reason: deepResult.reason,
        });
      }
    } catch (err: any) {
      logStructured("WARN", "Candidate extraction failed, moving gracefully to next queue item", {
        url: targetUrl,
        error: err.message,
      });
      evaluatedArticles.push(candidate);
    }
  }

  if (acceptedArticles.length >= goalCount || acceptedArticles.length > 0) {
    emitEvent("FEED_COLLECTION_GOAL_MET", {
      goalCount,
      acceptedCount: acceptedArticles.length,
      articles: acceptedArticles,
    });
    return {
      configuredFeeds: feedUrls,
      maxAgeHours,
      goalCount,
      evaluatedArticles,
      acceptedArticles,
      usedFallback: false,
    };
  }

  const fallbackCandidate: FeedArticleCandidate = {
    title: "When Will Politicians Turn to MMT?",
    url: DEFAULT_FALLBACK_ARTICLE_URL,
    cleanedUrl: DEFAULT_FALLBACK_ARTICLE_URL,
    sourceFeed: "graceful-default-fallback",
    shallowResult: { classification: "ARTICLE_CANDIDATE", reason: "Default Fallback", passed: true },
    deepResult: {
      classification: "LONGFORM_ARTICLE",
      wordCount: 1450,
      linkDensity: 0.05,
      listCount: 2,
      passed: true,
      reason: "Verified Fallback Document",
    },
  };

  emitEvent("FEED_DEFAULT_FALLBACK_ENGAGED", { defaultUrl: DEFAULT_FALLBACK_ARTICLE_URL });
  logStructured("WARN", "Zero candidates accepted from feeds, engaging verified default fallback article", {
    fallbackUrl: DEFAULT_FALLBACK_ARTICLE_URL,
  });

  return {
    configuredFeeds: feedUrls,
    maxAgeHours,
    goalCount,
    evaluatedArticles,
    acceptedArticles: [fallbackCandidate],
    usedFallback: true,
  };
}

// -------------------------------------------------------------
// 8. MEMORY & SWAP DIAGNOSTICS
// -------------------------------------------------------------
let CACHED_PAGE_SIZE: number | null = null;
export function getSystemPageSizeBytes(): number {
  if (CACHED_PAGE_SIZE !== null) return CACHED_PAGE_SIZE;
  try {
    const out = execSync("getconf PAGESIZE", { encoding: "utf8" });
    const parsed = parseInt(out.trim(), 10);
    if (!isNaN(parsed) && parsed > 0) {
      CACHED_PAGE_SIZE = parsed;
      return CACHED_PAGE_SIZE;
    }
  } catch {}
  CACHED_PAGE_SIZE = 4096;
  return CACHED_PAGE_SIZE;
}

function readServerPid(): number | null {
  try {
    if (fs.existsSync(".llama_server.pid")) {
      const pidStr = fs.readFileSync(".llama_server.pid", "utf8").trim();
      const parsed = parseInt(pidStr, 10);
      return !isNaN(parsed) && parsed > 0 ? parsed : null;
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

export interface MemorySnapshot {
  swappiness: number;
  pid: number | null;
  vmRssMb: number | null;
  vmSwapMb: number | null;
  systemSwapUsedMb: number | null;
  systemSwapTotalMb: number | null;
  isCgroupConstrained: boolean;
  diagnosticsError?: string;
}

function getMemorySnapshot(): MemorySnapshot {
  let swappiness = -1;
  try {
    swappiness = parseInt(fs.readFileSync("/proc/sys/vm/swappiness", "utf8").trim(), 10);
  } catch {}

  let swapTotalMb: number | null = null;
  let swapUsedMb: number | null = null;
  let isCgroupConstrained = false;

  try {
    if (fs.existsSync("/sys/fs/cgroup/memory.swap.current")) {
      const curBytes = parseInt(fs.readFileSync("/sys/fs/cgroup/memory.swap.current", "utf8").trim(), 10);
      const maxRaw = fs.readFileSync("/sys/fs/cgroup/memory.swap.max", "utf8").trim();
      const maxBytes = maxRaw === "max" ? null : parseInt(maxRaw, 10);

      swapUsedMb = Math.round(curBytes / (1024 * 1024));
      swapTotalMb = maxBytes !== null ? Math.round(maxBytes / (1024 * 1024)) : null;
      isCgroupConstrained = true;
    }
  } catch {}

  if (swapTotalMb === null && !isCgroupConstrained) {
    try {
      const meminfo = fs.readFileSync("/proc/meminfo", "utf8");
      let totalKb = 0;
      let freeKb = 0;
      for (const line of meminfo.split("\n")) {
        if (line.startsWith("SwapTotal:")) totalKb = parseInt(line.split(/\s+/)[1], 10);
        if (line.startsWith("SwapFree:")) freeKb = parseInt(line.split(/\s+/)[1], 10);
      }
      swapTotalMb = Math.round(totalKb / 1024);
      swapUsedMb = Math.round((totalKb - freeKb) / 1024);
    } catch {}
  }

  const pid = readServerPid();
  let vmRssMb: number | null = null;
  let vmSwapMb: number | null = null;
  let diagnosticsError: string | undefined;

  if (pid) {
    try {
      const status = fs.readFileSync(`/proc/${pid}/status`, "utf8");
      for (const line of status.split("\n")) {
        if (line.startsWith("VmRSS:")) vmRssMb = Math.round(parseInt(line.split(/\s+/)[1], 10) / 1024);
        if (line.startsWith("VmSwap:")) vmSwapMb = Math.round(parseInt(line.split(/\s+/)[1], 10) / 1024);
      }
    } catch (err: any) {
      diagnosticsError = `Failed reading /proc/${pid}/status: ${err.message}`;
    }
  }

  return {
    swappiness,
    pid,
    vmRssMb,
    vmSwapMb,
    systemSwapUsedMb: swapUsedMb,
    systemSwapTotalMb: swapTotalMb,
    isCgroupConstrained,
    diagnosticsError,
  };
}

// -------------------------------------------------------------
// 9. OPENAI HTTP CLIENT
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
              reject(new Error(`Invalid JSON returned: ${raw}`));
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
// 10. AI EVENT PIPELINE ORCHESTRATOR
// -------------------------------------------------------------
export class AIEventPipeline extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  public correlationId: string;
  private runnerMetadata: RunnerMetadata;
  private hostFingerprint: HostFingerprint;
  private jsonlFilePath: string;
  private pipelineStartTime: number;
  private lastEventTime: number;

  constructor(runnerMetadata: RunnerMetadata, existingCorrelationId?: string, jsonlFilePath = "pipeline-events.jsonl") {
    super();
    this.runnerMetadata = runnerMetadata;
    this.hostFingerprint = getHostFingerprint();
    this.correlationId = existingCorrelationId || `corr-${crypto.randomUUID()}`;
    this.jsonlFilePath = jsonlFilePath;
    this.pipelineStartTime = performance.now();
    this.lastEventTime = this.pipelineStartTime;
  }

  public loadPriorEvents(): void {
    if (!fs.existsSync(this.jsonlFilePath)) return;
    try {
      const lines = fs.readFileSync(this.jsonlFilePath, "utf8").split("\n").filter(Boolean);
      this.auditLog = lines
        .map((l) => {
          try {
            return JSON.parse(l);
          } catch {
            return null;
          }
        })
        .filter((e): e is PipelineEvent => e !== null && typeof e.eventId === "string");

      logStructured("INFO", "Hydrated historical pipeline events from disk", {
        path: this.jsonlFilePath,
        count: this.auditLog.length,
      });
    } catch (err: any) {
      logStructured("WARN", "Failed hydrating historical pipeline events", { error: err.message });
    }
  }

  public logEvent(eventType: string, payload: any, sourceUrl: string = "pipeline-lifecycle"): PipelineEvent {
    const now = performance.now();
    const durationMs = Math.round(now - this.lastEventTime);
    const cumulativeMs = Math.round(now - this.pipelineStartTime);
    this.lastEventTime = now;

    const eventId = buildDeterministicEventId(
      this.runnerMetadata.runnerName,
      this.runnerMetadata.shardId,
      sourceUrl,
      eventType
    );

    const event: PipelineEvent = {
      eventId,
      eventType,
      timestamp: new Date().toISOString(),
      correlationId: this.correlationId,
      durationMs,
      cumulativeMs,
      payload,
    };

    this.auditLog.push(event);

    const jsonlLine = JSON.stringify(event);
    fs.appendFileSync(this.jsonlFilePath, jsonlLine + "\n", "utf8");

    logStructured("INFO", `Pipeline Event: ${eventType}`, {
      eventId,
      eventType,
      correlationId: this.correlationId,
      durationMs,
      cumulativeMs,
    });

    this.emit(eventType, event);
    return event;
  }

  public getEventHistory(): PipelineEvent[] {
    return this.auditLog;
  }

  public async executeSingleArticle(options: {
    sourceType: SourceAudit["sourceType"];
    sourceIdentifier: string;
    sourceTitle: string;
    targetText: string;
    feedAudit?: FeedSelectionAudit;
    systemPrompt: string;
    serverUrl: string;
    modelName: string;
    inferenceParams: ModelInferenceParams;
  }): Promise<SummaryStructuredOutput> {
    const {
      sourceType,
      sourceIdentifier,
      sourceTitle,
      targetText: rawTargetText,
      feedAudit,
      systemPrompt,
      serverUrl,
      modelName,
      inferenceParams,
    } = options;

    let targetText = rawTargetText;
    const words = targetText.split(/\s+/).filter(Boolean);
    if (words.length > 6000) {
      targetText = words.slice(0, 6000).join(" ") + "\n\n[...Truncated to fit context window...]";
    }

    const sourceAudit: SourceAudit = {
      sourceType,
      sourceIdentifier,
      sourceTitle,
      extractedWordCount: words.length,
      extractedCharCount: targetText.length,
      extractedText: targetText,
      feedAudit,
    };

    const userPromptContent = `Document Title: ${sourceTitle}\n\nContent:\n"""\n${targetText}\n"""`;

    this.logEvent(
      "INPUT_RESOLVED",
      {
        modelName,
        sourceType,
        sourceIdentifier,
        sourceTitle,
        wordCount: words.length,
        charCount: targetText.length,
      },
      sourceIdentifier
    );

    const pageSizeBytes = getSystemPageSizeBytes();
    const vmstatStart = getVmstatSwap();
    let peakProcessSwapMb = 0;
    const initialSnap = getMemorySnapshot();
    if (initialSnap.vmSwapMb !== null) {
      peakProcessSwapMb = Math.max(peakProcessSwapMb, initialSnap.vmSwapMb);
    }

    const cpuSampler = new SystemCpuSampler();
    cpuSampler.start(1000);

    const openAiPayload = {
      model: modelName,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPromptContent },
      ],
      temperature: inferenceParams.temperature,
      top_k: inferenceParams.top_k,
      top_p: inferenceParams.top_p,
      min_p: inferenceParams.min_p,
      repeat_penalty: inferenceParams.repeat_penalty,
      presence_penalty: 0.2,
      frequency_penalty: 0.2,
      max_tokens: inferenceParams.max_tokens,
      response_format: { type: "json_object", schema: STRICT_SUMMARY_JSON_SCHEMA },
      stream: false,
      chat_template_kwargs: { enable_thinking: false },
    };

    const startTime = performance.now();
    this.logEvent(
      "INFERENCE_DISPATCHED",
      {
        serverUrl,
        targetModel: modelName,
        sourceType,
        sourceIdentifier,
        inferenceParams,
        wordCount: words.length,
        charCount: targetText.length,
      },
      sourceIdentifier
    );

    let tickCounter = 0;
    const progressTimer = setInterval(() => {
      tickCounter++;
      const snap = getMemorySnapshot();
      if (snap.vmSwapMb !== null) {
        peakProcessSwapMb = Math.max(peakProcessSwapMb, snap.vmSwapMb);
      }

      if (tickCounter % 20 === 0) {
        const elapsed = Math.round((performance.now() - startTime) / 1000);
        logStructured("INFO", "LLM Inference Heartbeat", {
          elapsedSeconds: elapsed,
          ramRssMb: snap.vmRssMb ?? 0,
          vmSwapMb: snap.vmSwapMb ?? 0,
          peakProcessSwapMb,
        });
      }
    }, 500);

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

    const finalSnap = getMemorySnapshot();
    if (finalSnap.vmSwapMb !== null) {
      peakProcessSwapMb = Math.max(peakProcessSwapMb, finalSnap.vmSwapMb);
    }

    const vmstatEnd = getVmstatSwap();
    const swapOutPages = Math.max(0, vmstatEnd.pswpout - vmstatStart.pswpout);
    const swapInPages = Math.max(0, vmstatEnd.pswpin - vmstatStart.pswpin);
    const bytesPerMb = 1024 * 1024;

    const swapMetrics: SwapActivityMetrics = {
      swappiness: finalSnap.swappiness,
      server_pid: finalSnap.pid,
      server_vm_rss_mb: finalSnap.vmRssMb ?? 0,
      peak_server_swap_mb: peakProcessSwapMb,
      final_server_swap_mb: finalSnap.vmSwapMb ?? 0,
      system_swap_used_mb: finalSnap.systemSwapUsedMb ?? 0,
      system_swap_total_mb: finalSnap.systemSwapTotalMb ?? 0,
      swap_bytes_written_mb: Number(((swapOutPages * pageSizeBytes) / bytesPerMb).toFixed(2)),
      swap_bytes_read_mb: Number(((swapInPages * pageSizeBytes) / bytesPerMb).toFixed(2)),
      page_size_bytes: pageSizeBytes,
      is_cgroup_constrained: finalSnap.isCgroupConstrained,
      diagnostics_error: finalSnap.diagnosticsError,
    };

    const promptTokens = usage?.prompt_tokens || timings?.prompt_n || 0;
    const completionTokens = usage?.completion_tokens || timings?.predicted_n || 0;
    const totalTokens = usage?.total_tokens || promptTokens + completionTokens;

    let promptTimeMs = timings?.prompt_ms ? Math.round(timings.prompt_ms) : 0;
    let completionTimeMs = timings?.predicted_ms ? Math.round(timings.predicted_ms) : 0;
    if (promptTimeMs === 0 && completionTimeMs === 0) completionTimeMs = totalDurationMs;

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

    this.logEvent(
      "INFERENCE_COMPLETED",
      {
        modelName,
        sourceIdentifier,
        tokenMetrics,
        swapMetrics,
        cpuMetrics,
        rawOutput: rawContent,
      },
      sourceIdentifier
    );

    let parsed: any;
    try {
      const match = rawContent.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(match ? match[0] : rawContent);
    } catch {
      parsed = {};
    }

    let synthesisProse = "";
    if (typeof parsed.analytic_synthesis === "string" && parsed.analytic_synthesis.trim()) {
      synthesisProse = parsed.analytic_synthesis.trim();
    } else if (typeof parsed.summary === "string" && parsed.summary.trim()) {
      synthesisProse = parsed.summary.trim();
    } else {
      synthesisProse = rawContent.trim();
    }

    const inLen = targetText.length || 1;
    const outLen = synthesisProse.length;
    const retentionPct = ((outLen / inLen) * 100).toFixed(1);
    const reductionPct = Math.max(0, 100 - parseFloat(retentionPct)).toFixed(1);

    const compression: CompressionAnalysis = {
      inputChars: inLen,
      outputChars: outLen,
      retentionRatioPercent: `${retentionPct}%`,
      reductionRatioPercent: `${reductionPct}%`,
      explanation: `Retention Ratio = (Output Chars / Input Chars) * 100%. The synthesis retains ${retentionPct}% of the raw text size.`,
    };

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || parsed.title || sourceTitle,
      analytic_synthesis: synthesisProse,
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
      inference_params: inferenceParams,
      input_text: targetText,
      system_prompt: openAiPayload.messages[0].content,
      user_prompt: userPromptContent,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult, sourceIdentifier);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 11. STEP SUMMARY PUBLISHER
// -------------------------------------------------------------
export function publishStepSummary(
  modelName: string,
  results: SummaryStructuredOutput[],
  events: PipelineEvent[],
  inferenceParams: ModelInferenceParams,
  feedAudit?: FeedSelectionAudit
) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  if (!results || results.length === 0) {
    logStructured("WARN", "No results available to publish in GitHub Step Summary");
    return;
  }

  const firstResult = results[0];
  const hf = firstResult.host_fingerprint || getHostFingerprint();
  const rm = firstResult.runner_metadata || {
    runnerName: process.env.RUNNER_NAME || "GitHub Runner",
    runId: process.env.GITHUB_RUN_ID || "N/A",
    runNumber: process.env.GITHUB_RUN_NUMBER || "1",
    workflow: process.env.GITHUB_WORKFLOW || "CI",
    osArch: `${os.type()} ${os.arch()}`,
    shardId: process.env.SHARD_ID || "N/A",
    modelFamily: process.env.MODEL_FAMILY || "N/A",
    requestedModelId: process.env.REQUESTED_MODEL_ID || "N/A",
  };
  const cm = firstResult.cpu_metrics || { maxCpuPercent: 0, avgCpuPercent: 0, samplesTaken: 0 };
  const sm = firstResult.swap_metrics || {
    swappiness: -1,
    server_pid: null,
    server_vm_rss_mb: 0,
    peak_server_swap_mb: 0,
    final_server_swap_mb: 0,
    system_swap_used_mb: 0,
    system_swap_total_mb: 0,
    swap_bytes_written_mb: 0,
    swap_bytes_read_mb: 0,
    page_size_bytes: 4096,
    is_cgroup_constrained: false,
  };
  const tm = firstResult.token_metrics || {
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    prompt_time_ms: 0,
    completion_time_ms: 0,
    total_duration_ms: 0,
    prompt_tokens_per_second: 0,
    completion_tokens_per_second: 0,
  };

  process.stdout.write(
    `::notice title=AI Pipeline Execution Report (${modelName})::🖥️ ${hf.rawFingerprint} | ⚡ Max CPU: ${cm.maxCpuPercent}% | 📥 Ingest: ${tm.prompt_tokens_per_second} t/s | ⚡ Gen: ${tm.completion_tokens_per_second} t/s\n`
  );

  const lines: string[] = [
    `# 🧠 AI Transformer & Quality Audit Execution Report`,
    ``,
    `## 🖥️ Host, System & Runner Telemetry`,
    `| Attribute | Detected System / Runner Specification |`,
    `| :--- | :--- |`,
    `| **Host Machine CPU** | \`${hf.cpuModel}\` |`,
    `| **Allocated Core Count** | **${hf.coreCount} physical/vCPU cores** |`,
    `| **L3 Cache Size** | **${hf.l3Cache}** |`,
    `| **SIMD / Vector Acceleration** | \`${hf.avxFlags.join(", ")}\` |`,
    `| **Total Physical RAM** | **${hf.totalRamGb}** |`,
    `| **Kernel Page Size** | **\`${sm.page_size_bytes} bytes\`** |`,
    `| **Runner Name** | \`${rm.runnerName || "Self-Hosted / Local"}\` |`,
    `| **GitHub Run ID** | \`${rm.runId || "N/A"}\` |`,
    `| **GitHub Run Number** | \`#${rm.runNumber || "1"}\` |`,
    `| **Runner OS & Architecture** | \`${rm.osArch}\` |`,
    `| **Workflow Name** | \`${rm.workflow || "CI"}\` |`,
    `| **Job / Shard ID** | \`${rm.shardId || "N/A"}\` |`,
    ``,
    `---`,
    ``,
    `## 📈 CPU & Memory Utilization Dynamics`,
    `| Resource Metric | Measured Value | Operational & Health Status |`,
    `| :--- | :--- | :--- |`,
    `| **Peak CPU Utilization** | **\`${cm.maxCpuPercent}%\`** | Highest instantaneous utilization across all cores |`,
    `| **Average CPU Utilization** | **\`${cm.avgCpuPercent}%\`** | Mean CPU load over ${cm.samplesTaken} samples |`,
    `| **Inference Parallelism** | **${hf.coreCount} threads** | Configured execution threads |`,
    `| **Linux \`vm.swappiness\`** | **\`${sm.swappiness}\`** | ${sm.swappiness >= 0 ? (sm.swappiness <= 10 ? "✅ Low Paging (Optimized)" : "⚠️ High Paging") : "N/A"} |`,
    `| **Server Process PID** | \`${sm.server_pid ?? "Unresolved"}\` | Background Daemon |`,
    `| **Server RAM (RSS)** | **${sm.server_vm_rss_mb} MB** | Resident in Physical Memory |`,
    `| **Peak Process Swap** | **${sm.peak_server_swap_mb} MB** | ${sm.peak_server_swap_mb > 0 ? "⚠️ Process Paged Out" : "✅ 0 MB (Zero Process Swap)"} |`,
    `| **Final Process Swap** | **${sm.final_server_swap_mb} MB** | Current Process VmSwap |`,
    `| **System Swap Space Out** | **${sm.swap_bytes_written_mb} MB** | Kernel Global Page-Out Activity |`,
    `| **System Swap Space In** | **${sm.swap_bytes_read_mb} MB** | Kernel Global Page-In Activity |`,
    `| **Total Swap Allocation** | \`${sm.system_swap_used_mb} MB / ${sm.system_swap_total_mb} MB\` | ${sm.is_cgroup_constrained ? "Cgroup v2 Container Boundary" : "Host Swapfile Space"} |`,
  ];

  if (sm.diagnostics_error) {
    lines.push(`| **Diagnostics Warning** | \`${sm.diagnostics_error}\` | ⚠️ Incomplete Procfs Access |`);
  }

  lines.push(
    ``,
    `---`,
    ``,
    `## 🤖 Model Telemetry & Sampling Configuration`,
    `| Parameter / Telemetry Field | Configured Value | Description |`,
    `| :--- | :--- | :--- |`,
    `| **HF Repo / Model Family** | \`${rm.modelFamily || "N/A"}\` | Hugging Face repository source |`,
    `| **Model File / ID** | \`${modelName}${rm.requestedModelId ? " (Explicit: " + rm.requestedModelId + ")" : " (Auto-detected)"}\` | GGUF model binary |`,
    `| **Temperature** | \`${inferenceParams.temperature}\` | Randomness / creativity control |`,
    `| **Top-K** | \`${inferenceParams.top_k}\` | Top-K vocabulary truncation |`,
    `| **Top-P (Nucleus)** | \`${inferenceParams.top_p}\` | Cumulative probability cutoff |`,
    `| **Min-P** | \`${inferenceParams.min_p}\` | Relative minimum probability threshold |`,
    `| **Repeat Penalty** | \`${inferenceParams.repeat_penalty}\` | Penalty against degenerative token loops |`,
    `| **Max Output Tokens** | \`${inferenceParams.max_tokens}\` | Hard completion circuit-breaker |`,
    `| **Context Size** | \`${process.env.CONTEXT_SIZE || "16384"}\` | Maximum transformer context window |`,
    ``,
    `---`,
    ``,
    `## ⚡ Deterministic Event Audit Trail (RFC 4122 UUIDv5)`,
    ``,
    `| Event Type | Deterministic UUIDv5 | Timestamp | Step Duration (ms) | Cumulative Time (ms) |`,
    `| :--- | :--- | :--- | :--- | :--- |`,
    ...events.map(
      (e) =>
        `| \`${e.eventType}\` | \`${e.eventId}\` | \`${e.timestamp}\` | **\`+${e.durationMs} ms\`** | **\`${e.cumulativeMs} ms\`** |`
    ),
    ``,
    `<details>`,
    `<summary><b>Inspect Full Event Stream Payloads (${events.length} Events - JSON)</b></summary>`,
    ``,
    `\`\`\`json`,
    JSON.stringify(events, null, 2),
    `\`\`\``,
    ``,
    `</details>`,
    ``,
    `---`,
    ``,
    `## ⏱️ Token Performance & Ingestion Rates`,
    ``,
    `| Evaluation Target | Prompt Tokens | Ingest Speed | Gen Tokens | Gen Speed | Total Time |`,
    `| :--- | :--- | :--- | :--- | :--- | :--- |`,
    ...results.map(
      (res, idx) =>
        `| **#${idx + 1}: ${res.headline.slice(0, 30)}...** | **${res.token_metrics?.prompt_tokens ?? "N/A"}** | **⚡ ${res.token_metrics?.prompt_tokens_per_second ?? "N/A"} t/s** | **${res.token_metrics?.completion_tokens ?? "N/A"}** | **⚡ ${res.token_metrics?.completion_tokens_per_second ?? "N/A"} t/s** | **${res.token_metrics ? (res.token_metrics.total_duration_ms / 1000).toFixed(2) + "s" : "N/A"}** |`
    ),
    ``,
    `---`,
    ``
  );

  if (feedAudit) {
    lines.push(`## 📡 Feed Discovery & Article Ingestion (Multi-Stage Classification)`, ``);
    if (feedAudit.usedFallback) {
      lines.push(
        `> ⚠️ **Collection goal unmet** (${feedAudit.acceptedArticles.length}/${feedAudit.goalCount} accepted within ${feedAudit.maxAgeHours}h). Engaged fallback URL.`
      );
    } else {
      lines.push(
        `> ✅ **Collection goal achieved:** Evaluated ${feedAudit.evaluatedArticles.length} candidates, accepted ${feedAudit.acceptedArticles.length} article(s) across diverse feeds.`
      );
    }
    lines.push(
      ``,
      `| # | Title | Source Feed | Shallow Classifier | Deep Classifier | Age | Link |`,
      `| :--- | :--- | :--- | :--- | :--- | :--- | :--- |`
    );

    feedAudit.evaluatedArticles.forEach((art, idx) => {
      const shallow = art.shallowResult?.passed ? "✅ Passed" : `❌ ${art.shallowResult?.classification}`;
      const deep = art.deepResult
        ? art.deepResult.passed
          ? `✅ ${art.deepResult.classification}`
          : `❌ ${art.deepResult.classification}`
        : "⏭️ Skipped";
      lines.push(
        `| **${idx + 1}** | **${art.title.slice(0, 35)}...** | \`${art.sourceFeed}\` | \`${shallow}\` | \`${deep}\` | ${art.ageHours !== undefined ? `\`${art.ageHours}h\`` : "N/A"} | [Visit](${art.url}) |`
      );
    });
    lines.push(``, `---`, ``);
  }

  results.forEach((res, idx) => {
    const comp = res.compression || {
      inputChars: 0,
      outputChars: 0,
      retentionRatioPercent: "N/A",
      reductionRatioPercent: "N/A",
    };
    lines.push(
      `## 📊 Text Compression & Reduction Analysis (${idx + 1}/${results.length})`,
      `| Metric | Value | Explanation & Formula |`,
      `| :--- | :--- | :--- |`,
      `| **Raw Input Size** | \`${comp.inputChars} chars\` | Ingested character count |`,
      `| **Model Output Size** | \`${comp.outputChars} chars\` | Completion character count |`,
      `| **Retention Ratio** | **\`${comp.retentionRatioPercent}\`** | **\`(Output Chars / Input Chars) * 100%\`** |`,
      `| **Content Reduction** | **\`${comp.reductionRatioPercent}\`** | **\`100% - Retention Ratio\`** |`,
      ``,
      `---`,
      ``,
      `## 🧭 Content Stance & Ideological Alignment (${idx + 1}/${results.length})`,
      `| Axis | Classification | Question Evaluated |`,
      `| :--- | :--- | :--- |`,
      `| **General Sentiment** | \`${res.sentiment.toUpperCase()}\` | Overall emotional and qualitative tone |`,
      `| **Stance on Change** | \`${res.stance_on_change}\` | Institutional preservation vs reform |`,
      `| **Stance on Economic Power** | \`${res.stance_on_economic_power}\` | Public/collective vs private market control |`,
      `| **Stance on State Power** | \`${res.stance_on_state_power}\` | Centralized authority vs constitutional constraints |`,
      `| **Stance on Borders** | \`${res.stance_on_borders}\` | National self-interest vs internationalism |`,
      `| **Stance on Personal Sphere** | \`${res.stance_on_personal_sphere}\` | Autonomy vs communitarian obligations |`,
      ``,
      `---`,
      ``,
      `## 📝 Analytic Synthesis: *"${res.headline}"*`,
      ``,
      res.analytic_synthesis,
      ``,
      `---`,
      ``
    );

    if (res.quality_metrics) {
      const qm = res.quality_metrics;
      lines.push(
        `## 🧪 UniEval Grounding & Factual Quality (${idx + 1}/${results.length})`,
        `| Quality Dimension | Metric Score | Operational Rating | Evaluation Methodology |`,
        `| :--- | :---: | :---: | :--- |`,
        `| **Factual Consistency** | **\`${qm.overall_consistency}\`** | ${qm.overall_consistency >= 0.75 ? "🟢 Fully Supported" : "⚠️ Grounding Variance"} | Chunked BM25 Sentence Entailment |`,
        `| **Sectional Coverage** | **\`${qm.chunk_coverage_percent}%\`** | ${qm.chunk_coverage_percent >= 60 ? "🟢 High Coverage" : "⚠️ Partial Coverage"} | ${qm.document_chunks_covered}/${qm.document_chunks_total} document chunks represented |`,
        `| **Discourse Coherence** | **\`${qm.coherence}\`** | ${qm.coherence >= 0.70 ? "🟢 Fluid" : "⚠️ Fragmented"} | Inter-sentence discourse flow |`,
        `| **Fluency (Syntax)** | **\`${qm.fluency}\`** | ${qm.fluency >= 0.85 ? "🟢 Natural" : "⚠️ Mechanical"} | Grammatical syntax & readability |`,
        ``
      );

      if (qm.uncovered_sections && qm.uncovered_sections.length > 0) {
        lines.push(
          `### ⚠️ Uncovered Document Sections (${qm.uncovered_sections.length}/${qm.document_chunks_total} Chunks Omitted)`,
          `> The following source sections have no supporting claims in the generated summary:`,
          ``,
          `| Missing Section | Section Topic / Lead Excerpt | Reason / Diagnostics |`,
          `| :---: | :--- | :--- |`,
          ...qm.uncovered_sections.map(
            (u) =>
              `| **Chunk ${u.chunk_index} of ${u.chunk_total}** | *"${u.excerpt.replace(/\|/g, "\\|")}"* | ⚠️ ${u.reason.replace(/\|/g, "\\|")} |`
          ),
          ``
        );
      } else {
        lines.push(
          `> ✅ **Full Document Grounding:** All ${qm.document_chunks_total}/${qm.document_chunks_total} document sections are represented in the analytic synthesis.`,
          ``
        );
      }

      const failedSentences = qm.sentence_breakdown.filter((s) => !s.supported);
      if (failedSentences.length > 0) {
        lines.push(
          `### ❌ Unsupported Claims / Grounding Failures (${failedSentences.length}/${qm.sentence_breakdown.length} Sentences)`,
          `> The following summary claims failed the factual consistency check against the source document:`,
          ``,
          `| # | Summary Sentence (Generated Claim) | Closest Source Evidence / Sentence | Consistency Score | Diagnostics |`,
          `| :-: | :--- | :--- | :-: | :--- |`,
          ...failedSentences.map(
            (s) =>
              `| **${s.sentence_index}** | "${s.text.replace(/\|/g, "\\|")}" | *"${(s.source_sentence || "No closely aligned passage").replace(/\|/g, "\\|")}"* | **\`${s.score}\`** | ❌ ${s.reason || "Low entailment (< 0.50)"} |`
          ),
          ``
        );
      } else {
        lines.push(
          `> ✅ **100% Factually Grounded:** All ${qm.sentence_breakdown.length} summary sentences are verified and supported by source document evidence.`,
          ``
        );
      }

      lines.push(`---`, ``);
    }

    lines.push(
      `## 📝 Full Input Prompt (${idx + 1}/${results.length})`,
      `<details>`,
      `<summary><b>Click to expand exact prompt payload sent to model</b></summary>`,
      ``,
      `### System Prompt:`,
      `\`\`\`text`,
      res.system_prompt,
      `\`\`\``,
      ``,
      `### User Prompt:`,
      `\`\`\`text`,
      res.user_prompt,
      `\`\`\``,
      ``,
      `</details>`,
      ``,
      `---`,
      ``
    );
  });

  fs.writeFileSync(summaryPath, lines.join("\n"), "utf8");
}

// -------------------------------------------------------------
// 12. MAIN RUNTIME
// -------------------------------------------------------------
async function main() {
  const runnerMetadata: RunnerMetadata = {
    runnerName: process.env.RUNNER_NAME ?? "Local-Runner",
    runId: process.env.GITHUB_RUN_ID ?? "0",
    runNumber: process.env.GITHUB_RUN_NUMBER ?? "1",
    workflow: process.env.GITHUB_WORKFLOW ?? "CI",
    osArch: `${os.type()} ${os.arch()}`,
    shardId: process.env.SHARD_ID ?? "shard-1",
    modelFamily: process.env.MODEL_FAMILY ?? "",
    requestedModelId: process.env.REQUESTED_MODEL_ID ?? "",
  };

  const phase = (process.argv.find((a) => a.startsWith("--phase="))?.split("=")[1] || "infer").toLowerCase();
  const modelName = process.env.MODEL_NAME ?? "";
  const serverUrl = process.env.SERVER_URL || "http://127.0.0.1:9931";
  const pipelineEventsPath = process.env.PIPELINE_EVENTS_PATH || "pipeline-events.jsonl";

  // -------------------------------------------------------------
  // PHASE 2: EVALUATION (CLIENT HTTP DISPATCH)
  // -------------------------------------------------------------
  if (phase === "eval") {
    logStructured("INFO", "Executing Phase 2: Parallel UniEval Quality Audit");
    if (!fs.existsSync(pipelineEventsPath)) {
      logStructured("WARN", "No pipeline events file found. Skipping evaluation phase.", { path: pipelineEventsPath });
      return;
    }

    const lines = fs.readFileSync(pipelineEventsPath, "utf8").split("\n").filter(Boolean);
    const structuredEvents = lines
      .map((l) => {
        try {
          return JSON.parse(l);
        } catch {
          return null;
        }
      })
      .filter((e) => e && e.eventType === "OUTPUT_STRUCTURED");

    if (structuredEvents.length === 0) {
      logStructured("WARN", "No OUTPUT_STRUCTURED events discovered in pipeline events. Exiting.");
      return;
    }

    const correlationId = structuredEvents[0].correlationId;
    const pipeline = new AIEventPipeline(runnerMetadata, correlationId, pipelineEventsPath);
    pipeline.loadPriorEvents();

    pipeline.logEvent("QUALITY_EVALUATION_STARTED", { articleCount: structuredEvents.length }, "evaluation-phase");

    const evalResults = await Promise.allSettled(
      structuredEvents.map(async (event) => {
        const payload = event.payload;
        const res = await fetch(`${PYTHON_EVAL_SERVER_URL}/v1/evaluate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            correlationId,
            runnerName: runnerMetadata.runnerName,
            shardId: runnerMetadata.shardId,
            sourceIdentifier: payload.source_audit.sourceIdentifier,
            sourceTitle: payload.headline,
            sourceText: payload.source_audit.extractedText,
            summaryText: payload.analytic_synthesis,
          }),
        });

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`Python eval HTTP ${res.status}: ${errText}`);
        }
        const data = await res.json();
        return { metrics: data.metrics };
      })
    );

    const updatedOutputs: SummaryStructuredOutput[] = structuredEvents.map((evt, idx) => {
      const output: SummaryStructuredOutput = evt.payload;
      const evalRes = evalResults[idx];

      if (evalRes && evalRes.status === "fulfilled") {
        output.quality_metrics = evalRes.value.metrics;
        pipeline.logEvent(
          "QUALITY_EVALUATION_COMPLETED",
          {
            sourceIdentifier: output.source_audit?.sourceIdentifier,
            sourceTitle: output.headline,
            metrics: evalRes.value.metrics,
          },
          output.source_audit?.sourceIdentifier || "evaluation-target"
        );
      } else {
        logStructured("WARN", "Evaluation request failed for target", {
          headline: output.headline,
          error: evalRes?.status === "rejected" ? evalRes.reason?.message : "Unfulfilled",
        });
      }

      if (!output.host_fingerprint) output.host_fingerprint = getHostFingerprint();
      if (!output.runner_metadata) output.runner_metadata = runnerMetadata;
      return output;
    });

    pipeline.logEvent("QUALITY_EVALUATION_BATCH_COMPLETED", { totalEvaluated: updatedOutputs.length }, "evaluation-phase");

    const retainedFeedAudit = updatedOutputs.find((o) => o.source_audit?.feedAudit)?.source_audit?.feedAudit;
    const activeInferenceParams = updatedOutputs[0]?.inference_params || DEFAULT_INFERENCE_PARAMS;

    publishStepSummary(
      modelName || "GGUF-Model",
      updatedOutputs,
      pipeline.getEventHistory(),
      activeInferenceParams,
      retainedFeedAudit
    );

    logStructured("INFO", "Quality evaluation phase completed successfully and step summary published.");
    return;
  }

  // -------------------------------------------------------------
  // PHASE 1: INGESTION & INFERENCE
  // -------------------------------------------------------------
  logStructured("INFO", "Executing Phase 1: Ingestion & LLM Inference");

  const defaultPreamble = `You are a precise, objective intelligence analyst. Your mandate is to produce a faithful, high-density synthesis of the provided document.`;
  const promptPreamble = (process.env.PROMPT || defaultPreamble).trim();

  const systemPrompt = `${promptPreamble}

OPERATIONAL PRINCIPLES:
1. STRICT DERIVATIVE FIDELITY:
   Distill ONLY what is explicitly reported or asserted in the document. Never introduce outside background history, unstated context, or speculative extrapolations.
   
2. ACCESSIBLE & OBJECTIVE TONE:
   Write in clear, direct, and neutral prose for an intelligent reader. Do not tutorialize, do not define common terms, and do not use empty academic jargon.

3. NATURAL, COHERENT PROSE (NO ARRAYS, NO BULLETS):
   Deliver the entire summary in fluent, continuous paragraphs within "analytic_synthesis".
   - Trace the core reality or thesis.
   - Detail the specific evidence, actors, figures, or causal mechanisms in-line.
   - Note any acknowledged boundaries, limitations, or counter-claims.
   - Let the depth of the document determine the length naturally: simple news briefs require brief paragraphs; complex treatises naturally require thorough multi-paragraph exposition.

4. SEPARATION OF STANCE CLASSIFICATION:
   Do NOT explain, defend, or mention your stance classifications inside the summary. Keep the synthesis strictly focused on the source content.

You MUST analyze the text and output ONLY a valid JSON object matching this exact schema:
{
  "headline": "A concise, descriptive headline for the document",
  "analytic_synthesis": "Comprehensive, cohesive narrative prose synthesizing the core findings, mechanisms, and nuances of the document.",
  "sentiment": "positive" | "neutral" | "negative" | "mixed",
  "stance_on_change": "conservatism" | "progressivism" | "not_applicable",
  "stance_on_economic_power": "socialism" | "libertarianism" | "not_applicable",
  "stance_on_state_power": "statism" | "constitutionalism" | "not_applicable",
  "stance_on_borders": "nationalism" | "internationalism" | "not_applicable",
  "stance_on_personal_sphere": "civil_libertarianism" | "communitarianism" | "not_applicable"
}`;

  const inputSource = (process.env.INPUT_SOURCE || "feed").toLowerCase().trim();
  const rawUrl = (process.env.URL ?? "").trim();
  const rawInputText = (process.env.INPUT_TEXT ?? "").trim();
  const maxAgeHours = parseFloat(process.env.FEED_MAX_AGE_HOURS || "24");
  const goalCount = parseInt(process.env.ARTICLE_COUNT_GOAL || "1", 10);

  const inferenceParams: ModelInferenceParams = {
    temperature: parseFloat(process.env.LLAMA_TEMPERATURE || String(DEFAULT_INFERENCE_PARAMS.temperature)),
    top_k: parseInt(process.env.LLAMA_TOP_K || String(DEFAULT_INFERENCE_PARAMS.top_k), 10),
    top_p: parseFloat(process.env.LLAMA_TOP_P || String(DEFAULT_INFERENCE_PARAMS.top_p)),
    min_p: parseFloat(process.env.LLAMA_MIN_P || String(DEFAULT_INFERENCE_PARAMS.min_p)),
    repeat_penalty: parseFloat(process.env.LLAMA_REPEAT_PENALTY || String(DEFAULT_INFERENCE_PARAMS.repeat_penalty)),
    max_tokens: parseInt(process.env.LLAMA_MAX_TOKENS || String(DEFAULT_INFERENCE_PARAMS.max_tokens), 10),
  };

  const pipeline = new AIEventPipeline(runnerMetadata, undefined, pipelineEventsPath);

  interface IngestionTarget {
    sourceType: SourceAudit["sourceType"];
    sourceIdentifier: string;
    sourceTitle: string;
    content: string;
  }

  const targets: IngestionTarget[] = [];
  let feedAudit: FeedSelectionAudit | undefined;

  if (inputSource === "feed") {
    feedAudit = await collectAndClassifyFeedArticles(DEFAULT_FEED_URLS, maxAgeHours, goalCount, (type, payload) =>
      pipeline.logEvent(type, payload, "feed-crawler")
    );

    for (const art of feedAudit.acceptedArticles) {
      let content = art.extractedMarkdown;
      if (!content) {
        try {
          const res = await extractDirectUrl(art.url, (type, payload) => pipeline.logEvent(type, payload, art.url));
          content = res.content;
          art.title = res.title || art.title;
        } catch {
          content = rawInputText;
        }
      }

      if (content) {
        targets.push({
          sourceType: feedAudit.usedFallback ? "FEED_DEFAULT_FALLBACK" : "FEED",
          sourceIdentifier: art.url,
          sourceTitle: art.title,
          content,
        });
      }
    }
  } else if (inputSource === "url") {
    const tidy = cleanUrlWithTidy(rawUrl);
    pipeline.logEvent("URL_TIDIED", { rawUrl, cleanUrl: tidy.cleanUrl, reduction: tidy.reduction }, tidy.cleanUrl);
    const extracted = await extractDirectUrl(tidy.cleanUrl, (type, payload) =>
      pipeline.logEvent(type, payload, tidy.cleanUrl)
    );
    targets.push({
      sourceType: "URL",
      sourceIdentifier: tidy.cleanUrl,
      sourceTitle: extracted.title,
      content: extracted.content,
    });
  } else {
    targets.push({
      sourceType: "INPUT_TEXT",
      sourceIdentifier: "Direct Text Input",
      sourceTitle: "Direct Input Text",
      content: rawInputText,
    });
  }

  const results: SummaryStructuredOutput[] = [];
  for (let i = 0; i < targets.length; i++) {
    const t = targets[i];
    logStructured("INFO", `Processing Ingestion Target (${i + 1}/${targets.length})`, {
      title: t.sourceTitle,
      sourceIdentifier: t.sourceIdentifier,
    });

    const result = await pipeline.executeSingleArticle({
      sourceType: t.sourceType,
      sourceIdentifier: t.sourceIdentifier,
      sourceTitle: t.sourceTitle,
      targetText: t.content,
      feedAudit,
      systemPrompt,
      serverUrl,
      modelName,
      inferenceParams,
    });

    results.push(result);
  }

  publishStepSummary(modelName, results, pipeline.getEventHistory(), inferenceParams, feedAudit);
  logStructured("INFO", "Phase 1 inference executed successfully", {
    processedCount: results.length,
    eventsRecorded: pipeline.getEventHistory().length,
  });
}

main().catch((err) => {
  logStructured("ERROR", "Unhandled fatal pipeline exception", { error: err.message, stack: err.stack });
  process.exit(1);
});
