/** Recover actual prose from semantic HTML when the primary extractor yields too little. */
import { parseHTML } from "linkedom";
import { sanitizeText } from "./sanitize-text";
import type { ExtractionControls } from "./extraction-controls";

type SemanticControls = ExtractionControls["semantic_fallback"];

export function validateSemanticSelectors(config: SemanticControls): void {
  const { document } = parseHTML("<html><body></body></html>");
  for (const [name, selectors] of [
    ["content_roots", config.content_roots], ["remove_elements", config.remove_elements],
    ["paragraph_elements", config.paragraph_elements],
    ["title_sources", config.title_sources.map(source => source.selector)],
    ["author_sources", config.author_sources.map(source => source.selector)],
  ] as const) {
    for (const [index, selector] of selectors.entries()) {
      try {
        if (!selector.trim()) throw new Error("empty CSS selector");
        document.querySelectorAll(selector);
      }
      catch (error) {
        throw new Error(`harvest.semantic_fallback.${name}[${index}] must be a valid CSS selector`, { cause: error });
      }
    }
  }
}

function readText(element: HTMLElement): string {
  return sanitizeText(element.innerText ?? element.textContent ?? "").replace(/\s+/gu, " ").trim();
}

export function extractSemanticContent(html: string, config: SemanticControls): string {
  const { document } = parseHTML(html);
  for (const selector of config.remove_elements) {
    for (const node of document.querySelectorAll(selector)) node.remove();
  }
  let root: HTMLElement | undefined;
  for (const selector of config.content_roots) {
    root = [...document.querySelectorAll<HTMLElement>(selector)]
      .find(candidate => readText(candidate).length >= config.min_root_chars);
    if (root) break;
  }
  root ??= document.body;
  if (!root) return "";
  const selector = config.paragraph_elements.join(",");
  const nodes = [...root.querySelectorAll<HTMLElement>(selector)];
  if (root.matches(selector)) nodes.unshift(root);
  const paragraphs = new Set<string>();
  for (const node of nodes) {
    let parent = node.parentElement;
    let nested = false;
    while (node !== root && parent && parent !== root) {
      if (parent.matches(selector)) { nested = true; break; }
      parent = parent.parentElement;
    }
    if (nested) continue;
    const text = readText(node);
    if (text && text.length >= config.min_paragraph_chars) paragraphs.add(text);
  }
  return [...paragraphs].join("\n\n");
}
