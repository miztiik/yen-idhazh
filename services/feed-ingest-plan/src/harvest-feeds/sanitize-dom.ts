/** Sanitize decoded DOM text before a Markdown converter can escape instruction delimiters. */
import { sanitizeText } from "./sanitize-text";

export function sanitizeDomText(document: Document): void {
  document.normalize();
  for (const element of document.querySelectorAll("*")) {
    if (element.tagName === "SCRIPT") continue;
    for (const child of element.childNodes) if (child.nodeType === child.TEXT_NODE) {
      const raw = child.textContent ?? "";
      child.textContent = `${/^\s/u.test(raw) ? " " : ""}${sanitizeText(raw)}${/\s$/u.test(raw) ? " " : ""}`;
    }
  }
}
