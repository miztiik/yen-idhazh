/** Extract sanitized article prose and access evidence from inert HTML. */
import { parseHTML } from "linkedom";
import Defuddle from "defuddle";
import type { HarvestObservation } from "./harvest-types";
import type { HarvestDiagnostics } from "@idhazh/common-contracts";
import { sanitizeText } from "./sanitize-text";
import type { ExtractionControls } from "./extraction-controls";
import type { ExtractionQuality } from "@idhazh/common-contracts";
import { measureExtractionQuality, countWords } from "./extraction-quality";
import { corroborateWords } from "./corroborated-words";

export class ArticleExtractionError extends Error {
  constructor(readonly reason: "missing-document-root" | "dom-depth-exceeded") { super(reason); }
}

export function cleanText(raw: string): string {
  const { document } = parseHTML(`<html><body>${sanitizeText(raw)}</body></html>`);
  return sanitizeText(document.body.innerText).replace(/\s+/gu, " ").trim();
}

function declaresPaywall(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(declaresPaywall);
  if (!value || typeof value !== "object") return false;
  if ("isAccessibleForFree" in value) {
    const access = value.isAccessibleForFree;
    if (access === false || (typeof access === "string" && access.trim().toLowerCase() === "false")) return true;
  }
  return Object.values(value).some(declaresPaywall);
}

function paywallEvidence(document: Document, html: string, markers: readonly string[]): {
  paywall: HarvestObservation["paywall"]; paywall_evidence: HarvestObservation["paywall_evidence"];
  warnings: HarvestDiagnostics["warnings"];
  metadata: unknown[];
} {
  let declared = false;
  let malformed = false;
  const metadata: unknown[] = [];
  for (const script of document.querySelectorAll("script")) {
    if (script.getAttribute("type")?.toLowerCase() !== "application/ld+json") continue;
    let payload: unknown;
    try { payload = JSON.parse(script.textContent ?? ""); }
    catch (error) {
      if (error instanceof SyntaxError) { malformed = true; continue; }
      throw error;
    }
    metadata.push(payload);
    if (declaresPaywall(payload)) declared = true;
  }
  const warnings: HarvestDiagnostics["warnings"] = malformed ? ["malformed-json-ld"] : [];
  if (declared) return { paywall: true, paywall_evidence: "json-ld", warnings, metadata };
  const normalized = html.replace(/\s+/gu, " ").toLowerCase();
  const compact = html.replace(/\s+/gu, "").toLowerCase();
  if (markers.some(marker => normalized.includes(marker.toLowerCase()) || compact.includes(marker.toLowerCase()))) {
    return { paywall: true, paywall_evidence: "configured-marker", warnings, metadata };
  }
  return { paywall: false, paywall_evidence: "none", warnings, metadata };
}

export function extractArticle(html: string, configuredUrl: string, config: ExtractionControls, form: "article" | "abstract" = "article") {
  if (!html.trim()) return {
    article_text: "", word_count: 0, author: null, page_title: null,
    paywall: false, paywall_evidence: "none" as const,
    warnings: [] as HarvestDiagnostics["warnings"],
    quality: null as ExtractionQuality | null,
  };
  try { return extractDocument(html, configuredUrl, config, form); }
  catch (error) {
    if (error instanceof RangeError && /call stack|recursion/i.test(error.message)) {
      throw new ArticleExtractionError("dom-depth-exceeded");
    }
    throw error;
  }
}

function extractBody(document: Document, configuredUrl: string) {
  return new Defuddle(document, {
    url: configuredUrl, useAsync: false,
    fetch: Object.assign(
      () => { throw new Error("DOM extraction must not request resources"); },
      { preconnect: () => { throw new Error("DOM extraction must not open connections"); } },
    ),
  }).parse();
}

function bodyText(html: string): string {
  const content = parseHTML(`<html><body>${html}</body></html>`).document;
  for (const node of content.querySelectorAll("script,style,template,noscript,iframe,object,embed")) node.remove();
  return content.body.innerText;
}

function extractDocument(html: string, configuredUrl: string, config: ExtractionControls, form: "article" | "abstract") {
  const { document } = parseHTML(html);
  if (!document.documentElement) throw new ArticleExtractionError("missing-document-root");
  const { metadata, ...paywall } = paywallEvidence(document, html, config.paywall_markers);
  const corroborated = paywall.paywall ? null : corroborateWords(parseHTML(html).document, metadata, config.corroboration_min_words,
    container => bodyText(extractBody(parseHTML(container).document, configuredUrl).content));
  for (const node of document.querySelectorAll(".o-em-consent,.o-em-adblock")) node.remove();
  const extracted = extractBody(document, configuredUrl);
  const text = sanitizeText(bodyText(extracted.content));
  return {
    article_text: text,
    word_count: countWords(text),
    author: cleanText(extracted.author) || null,
    page_title: cleanText(extracted.title) || null,
    ...paywall,
    quality: text && !paywall.paywall ? measureExtractionQuality(text, corroborated, config, form) : null,
  };
}
