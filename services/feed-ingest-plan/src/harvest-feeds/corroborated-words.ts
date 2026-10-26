/** Count independent publisher article-length witnesses on one inert page. */
import { countWords } from "./extraction-quality";

// Native schema.org article types, not editorial classifications or fetch targets.
const ARTICLE_TYPES = new Set([
  "AnalysisNewsArticle", "Article", "BackgroundNewsArticle", "BlogPosting", "LiveBlogPosting",
  "NewsArticle", "OpinionNewsArticle", "ReportageNewsArticle", "ReviewNewsArticle",
]);
// Unicode case folds that produce ASCII beyond toLowerCase; other non-ASCII letters
// are removed by the native comparison's [a-z0-9] alphabet, not transliterated.
const ASCII_FOLDS: Readonly<Record<string, string>> = {
  "\u00df": "ss", "\u0149": "n", "\u017f": "s", "\u01f0": "j",
  "\u1e96": "h", "\u1e97": "t", "\u1e98": "w", "\u1e99": "y", "\u1e9a": "a",
  "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
  "\ufb05": "st", "\ufb06": "st",
};

function jsonWords(value: unknown): number {
  if (Array.isArray(value)) return value.reduce((best, child) => Math.max(best, jsonWords(child)), 0);
  if (!value || typeof value !== "object") return 0;
  const declared = "@type" in value ? value["@type"] : null;
  const types = Array.isArray(declared) ? declared : [declared];
  let best = types.some(type => typeof type === "string" && ARTICLE_TYPES.has(type))
    && "articleBody" in value && typeof value.articleBody === "string" ? countWords(value.articleBody) : 0;
  for (const child of Object.values(value)) best = Math.max(best, jsonWords(child));
  return best;
}

function reduced(text: string): string {
  return text.toLowerCase().replace(/[\u00df\u0149\u017f\u01f0\u1e96-\u1e9a\ufb00-\ufb06]/gu,
    letter => ASCII_FOLDS[letter]!).replace(/[^a-z0-9]+/g, " ").trim();
}

export async function corroborateWords(
  document: Document, metadata: readonly unknown[], minimum: number, extractContainer: (html: string) => Promise<string>,
): Promise<number | null> {
  let best = 0;
  for (const value of metadata) best = Math.max(best, jsonWords(value));
  // Match Python's independent tree reading: scripts and styles are not article prose.
  for (const node of document.querySelectorAll("script,style,noscript")) node.remove();
  for (const node of document.querySelectorAll('[itemprop="articleBody"]')) {
    best = Math.max(best, countWords(node.textContent ?? ""));
  }
  const wanted = reduced(document.querySelector('meta[property="og:title"]')?.getAttribute("content") ?? "");
  if (wanted) for (const node of document.querySelectorAll("article")) {
    const heading = reduced(node.querySelector("h1,h2")?.textContent ?? "");
    if (!heading || (!heading.includes(wanted) && !wanted.includes(heading))) continue;
    best = Math.max(best, countWords(await extractContainer(`<html><body>${node.outerHTML}</body></html>`)));
    break;
  }
  return best >= minimum ? best : null;
}
