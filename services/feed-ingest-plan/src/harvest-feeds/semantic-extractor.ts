/** Recover actual prose from semantic HTML when the primary extractor yields too little. */
import { parseHTML } from "linkedom";
import { sanitizeText } from "./sanitize-text";

// HTML content roles, not publisher-specific selectors or editorial policy.
const NON_CONTENT_ELEMENTS = "script,style,template,noscript,iframe,object,embed,nav,header,footer,aside,form,svg,button";
const CONTENT_ROOTS = 'article,main,[role="main"]';
const PROSE_ELEMENTS = "h1,h2,h3,h4,h5,h6,p,blockquote,li";

export function extractSemanticContent(html: string): string {
  const { document } = parseHTML(html);
  for (const node of document.querySelectorAll(NON_CONTENT_ELEMENTS)) node.remove();
  const root = document.querySelector(CONTENT_ROOTS) ?? document.body;
  if (!root) return "";
  const paragraphs = [...root.querySelectorAll(PROSE_ELEMENTS)]
    .filter(node => !node.parentElement?.closest("blockquote,li"))
    .map(node => sanitizeText(node.textContent ?? ""))
    .filter(Boolean);
  return paragraphs.join("\n\n");
}
