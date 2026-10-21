/** Remove the same injection machinery as idhazh-sanitizer-3, without changing prose. */
export const SANITIZER_VERSION = "idhazh-sanitizer-3";

const chatControl = /<[|\uff5c][^|\uff5c>\n]{0,64}[|\uff5c]>|<(?:[|\uff5c][A-Za-z][A-Za-z0-9_]{0,62}|[A-Za-z][A-Za-z0-9_]{0,62}[|\uff5c])>|<<\/?SYS>>|\[\/?[A-Z][A-Z_]{2,30}\]|<\/?[A-Za-z][A-Za-z0-9_]{0,62}>|^[ \t]*#{2,}[ \t]*(?:system|assistant|user)[ \t]*:/gim;
// This family alone is case-sensitive: [sic] and [AP] are ordinary prose.
const bracketControl = /^\[\/?[A-Z][A-Z_]{2,30}\]$/;

export function sanitizeText(text: string): string {
  return text
    .replace(/<!--.*?-->/gs, " ")
    .replace(/[\u00ad\u200b-\u200f\u2028-\u202e\u2060-\u2064\ufeff\u{e0000}-\u{e007f}]/gu, "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g, " ")
    .replace(/<<<(?:END_)?UNTRUSTED_SOURCE_TEXT>>>/gi, " ")
    .replace(chatControl, match => match.startsWith("[") && !bracketControl.test(match) ? match : " ")
    .replace(/(?<![\p{L}\p{N}_])(?:https?:\/\/|www\.|data:)[^\s<>"']+/giu, "[link]")
    .replace(/(?<![\p{L}\p{N}_])[A-Za-z0-9+/]{40,}={0,2}/gu, "[omitted]")
    .replace(/[^\S\n]+/gu, " ")
    .split("\n").map(line => line.trim()).join("\n")
    .replace(/\n{3,}/g, "\n\n").trim();
}
