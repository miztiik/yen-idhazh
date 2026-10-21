/** Remove the same injection machinery as idhazh-sanitizer-3, without changing prose. */
export const SANITIZER_VERSION = "idhazh-sanitizer-3";

// Python's case-insensitive ASCII letter classes also match these four Unicode letters.
const chatControl = /<[|\uff5c][^|\uff5c>\n]{0,64}[|\uff5c]>|<(?:[|\uff5c][A-Za-z\u0130\u0131\u017f\u212a][A-Za-z0-9_\u0130\u0131\u017f\u212a]{0,62}|[A-Za-z\u0130\u0131\u017f\u212a][A-Za-z0-9_\u0130\u0131\u017f\u212a]{0,62}[|\uff5c])>|<<\/?[S\u017f]Y[S\u017f]>>|\[\/?[A-Z][A-Z_]{2,30}\]|<\/?[A-Za-z\u0130\u0131\u017f\u212a][A-Za-z0-9_\u0130\u0131\u017f\u212a]{0,62}>|^[ \t]*#{2,}[ \t]*(?:[s\u017f]y[s\u017f]tem|a[s\u017f][s\u017f][i\u0130\u0131][s\u017f]tant|u[s\u017f]er)[ \t]*:/gim;
// This family alone is case-sensitive: [sic] and [AP] are ordinary prose.
const bracketControl = /^\[\/?[A-Z][A-Z_]{2,30}\]$/;

export function sanitizeText(text: string): string {
  return text
    .replace(/<!--.*?-->/gs, " ")
    .replace(/[\u00ad\u200b-\u200f\u2028-\u202e\u2060-\u2064\ufeff\u{e0000}-\u{e007f}]/gu, "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g, " ")
    .replace(/<<<(?:END_)?UNTRU[S\u017f]TED_[S\u017f]OURCE_TEXT>>>/gi, " ")
    .replace(chatControl, match => match.startsWith("[") && !bracketControl.test(match) ? match : " ")
    .replace(/(?<![\p{L}\p{N}_])(?:https?:\/\/|www\.|data:)[^\s<>"']+/giu, "[link]")
    .replace(/(?<![\p{L}\p{N}_])[A-Za-z0-9+/]{40,}={0,2}/gu, "[omitted]")
    .replace(/[^\S\n]+/gu, " ")
    .split("\n").map(line => line.trim()).join("\n")
    .replace(/\n{3,}/g, "\n\n").trim();
}
