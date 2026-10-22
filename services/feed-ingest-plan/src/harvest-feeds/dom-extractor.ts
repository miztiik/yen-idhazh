/** Extract sanitized article prose and access evidence from inert HTML. */
import { parseHTML } from "linkedom";
import Defuddle from "defuddle";
import type { HarvestObservation } from "./harvest-types";
import type { HarvestDiagnostics } from "@idhazh/common-contracts";
import { sanitizeText } from "./sanitize-text";

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
  if ("isAccessibleForFree" in value &&
    (value.isAccessibleForFree === false || String(value.isAccessibleForFree).toLowerCase() === "false")) return true;
  return Object.values(value).some(declaresPaywall);
}

function paywallEvidence(document: Document, html: string, markers: readonly string[]): {
  paywall: HarvestObservation["paywall"]; paywall_evidence: HarvestObservation["paywall_evidence"];
  warnings: HarvestDiagnostics["warnings"];
} {
  let declared = false;
  let malformed = false;
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    let payload: unknown;
    try { payload = JSON.parse(script.textContent ?? ""); }
    catch (error) {
      if (error instanceof SyntaxError) { malformed = true; continue; }
      throw error;
    }
    if (declaresPaywall(payload)) declared = true;
  }
  const warnings: HarvestDiagnostics["warnings"] = malformed ? ["malformed-json-ld"] : [];
  if (declared) return { paywall: true, paywall_evidence: "json-ld", warnings };
  const normalized = html.replace(/\s+/gu, " ").toLowerCase();
  const compact = html.replace(/\s+/gu, "").toLowerCase();
  if (markers.some(marker => normalized.includes(marker.toLowerCase()) || compact.includes(marker.toLowerCase()))) {
    return { paywall: true, paywall_evidence: "configured-marker", warnings };
  }
  return { paywall: false, paywall_evidence: "none", warnings };
}

export function extractArticle(html: string, configuredUrl: string, markers: readonly string[]) {
  if (!html.trim()) return {
    article_text: "", word_count: 0, author: null, page_title: null,
    paywall: false, paywall_evidence: "none" as const,
    warnings: [] as HarvestDiagnostics["warnings"],
  };
  try { return extractDocument(html, configuredUrl, markers); }
  catch (error) {
    if (error instanceof RangeError && /call stack|recursion/i.test(error.message)) {
      throw new ArticleExtractionError("dom-depth-exceeded");
    }
    throw error;
  }
}

function extractDocument(html: string, configuredUrl: string, markers: readonly string[]) {
  const { document } = parseHTML(html);
  if (!document.documentElement) throw new ArticleExtractionError("missing-document-root");
  const paywall = paywallEvidence(document, html, markers);
  const extracted = new Defuddle(document, {
    url: configuredUrl, useAsync: false,
    fetch: Object.assign(
      () => { throw new Error("DOM extraction must not request resources"); },
      { preconnect: () => { throw new Error("DOM extraction must not open connections"); } },
    ),
  }).parse();
  const content = parseHTML(`<html><body>${extracted.content}</body></html>`).document;
  for (const node of content.querySelectorAll("script,style,template,noscript,iframe,object,embed")) node.remove();
  const text = sanitizeText(content.body.innerText);
  return {
    article_text: text,
    word_count: text ? text.split(/\s+/u).length : 0,
    author: cleanText(extracted.author) || null,
    page_title: cleanText(extracted.title) || null,
    ...paywall,
  };
}
