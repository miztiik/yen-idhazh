/** Extract sanitized article prose and access evidence from inert HTML. */
import { parseHTML } from "linkedom";
import { Defuddle } from "defuddle/node";
import type { HarvestObservation } from "./harvest-types";
import type { HarvestDiagnostics } from "@idhazh/common-contracts";
import { sanitizeText } from "./sanitize-text";
import type { ExtractionControls } from "./extraction-controls";
import type { ExtractionQuality } from "@idhazh/common-contracts";
import { measureExtractionQuality, countWords } from "./extraction-quality";
import { corroborateWords } from "./corroborated-words";
import { extractSemanticContent } from "./semantic-extractor";

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

function publisherMetadata(document: Document): { metadata: unknown[]; malformed: boolean } {
  let malformed = false;
  const metadata: unknown[] = [];
  for (const script of document.querySelectorAll("script")) {
    if (script.getAttribute("type")?.toLowerCase() !== "application/ld+json") continue;
    let payload: unknown;
    try { payload = JSON.parse(script.textContent ?? ""); }
    catch (error) {
      if (error instanceof SyntaxError) {
        malformed = true;
        script.remove();
        continue;
      }
      throw error;
    }
    metadata.push(payload);
  }
  return { metadata, malformed };
}

function readMetadata(document: Document, sources: ExtractionControls["semantic_fallback"]["title_sources"]): string | null {
  for (const source of sources) {
    for (const element of document.querySelectorAll(source.selector)) {
      const value = cleanText((source.attribute === null ? element.textContent : element.getAttribute(source.attribute)) ?? "");
      if (value) return value;
    }
  }
  return null;
}

function paywallEvidence(document: Document, html: string, markers: readonly string[]): {
  paywall: HarvestObservation["paywall"]; paywall_evidence: HarvestObservation["paywall_evidence"];
  warnings: HarvestDiagnostics["warnings"];
  metadata: unknown[];
} {
  const { metadata, malformed } = publisherMetadata(document);
  const declared = metadata.some(declaresPaywall);
  const warnings: HarvestDiagnostics["warnings"] = malformed ? ["malformed-json-ld"] : [];
  if (declared) return { paywall: true, paywall_evidence: "json-ld", warnings, metadata };
  const normalized = html.replace(/\s+/gu, " ").toLowerCase();
  const compact = html.replace(/\s+/gu, "").toLowerCase();
  if (markers.some(marker => normalized.includes(marker.toLowerCase()) || compact.includes(marker.toLowerCase()))) {
    return { paywall: true, paywall_evidence: "configured-marker", warnings, metadata };
  }
  return { paywall: false, paywall_evidence: "none", warnings, metadata };
}

export async function extractArticle(html: string, configuredUrl: string, config: ExtractionControls, form: "article" | "abstract" = "article") {
  if (!html.trim()) return {
    article_text: "", word_count: 0, author: null, page_title: null,
    paywall: false, paywall_evidence: "none" as const,
    warnings: [] as HarvestDiagnostics["warnings"],
    quality: null as ExtractionQuality | null,
  };
  try { return await extractDocument(html, configuredUrl, config, form); }
  catch (error) {
    if (error instanceof RangeError && /call stack|recursion/i.test(error.message)) {
      throw new ArticleExtractionError("dom-depth-exceeded");
    }
    throw error;
  }
}

function extractBody(document: Document, configuredUrl: string) {
  for (const node of document.querySelectorAll("script:not([type='application/ld+json']),style,template,noscript,iframe,object,embed")) node.remove();
  document.normalize();
  // Sanitize decoded text before Markdown can escape instruction delimiters.
  for (const element of document.querySelectorAll("*")) {
    if (element.tagName === "SCRIPT") continue;
    for (const child of element.childNodes) if (child.nodeType === child.TEXT_NODE) {
      const raw = child.textContent ?? "";
      child.textContent = `${/^\s/u.test(raw) ? " " : ""}${sanitizeText(raw)}${/\s$/u.test(raw) ? " " : ""}`;
    }
  }
  return Defuddle(document, configuredUrl, {
    markdown: true, useAsync: false,
    fetch: Object.assign(
      () => { throw new Error("DOM extraction must not request resources"); },
      { preconnect: () => { throw new Error("DOM extraction must not open connections"); } },
    ),
  });
}

async function extractDocument(html: string, configuredUrl: string, config: ExtractionControls, form: "article" | "abstract") {
  const { document } = parseHTML(html);
  if (!document.documentElement) throw new ArticleExtractionError("missing-document-root");
  const { metadata, ...paywall } = paywallEvidence(document, html, config.paywall_markers);
  const recovered = {
    page_title: readMetadata(document, config.semantic_fallback.title_sources),
    author: readMetadata(document, config.semantic_fallback.author_sources),
  };
  let corroborated: number | null = null;
  if (!paywall.paywall) {
    const corroborationDocument = parseHTML(html).document;
    publisherMetadata(corroborationDocument);
    corroborated = await corroborateWords(corroborationDocument, metadata, config.corroboration_min_words,
      async container => sanitizeText((await extractBody(parseHTML(container).document, configuredUrl)).content));
  }
  for (const node of document.querySelectorAll(".o-em-consent,.o-em-adblock")) node.remove();
  let extracted: Awaited<ReturnType<typeof extractBody>> | null = null;
  let primaryError: unknown;
  try { extracted = await extractBody(document, configuredUrl); }
  catch (error) {
    if (error instanceof RangeError) throw error;
    primaryError = error;
  }
  let text = sanitizeText(extracted?.content ?? "");
  if (primaryError !== undefined || countWords(text) < config.min_source_words) {
    const fallback = extractSemanticContent(html, config.semantic_fallback);
    if (fallback && countWords(fallback) > countWords(text)) {
      text = fallback;
      paywall.warnings.push("semantic-dom-fallback");
    } else if (primaryError !== undefined) throw primaryError;
  }
  return {
    article_text: text,
    word_count: countWords(text),
    author: cleanText(extracted?.author ?? "") || recovered.author,
    page_title: cleanText(extracted?.title ?? "") || recovered.page_title,
    ...paywall,
    quality: text && !paywall.paywall ? measureExtractionQuality(text, corroborated, config, form) : null,
  };
}
