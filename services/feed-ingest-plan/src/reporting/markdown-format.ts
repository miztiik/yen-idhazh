/** How are untrusted values escaped before they enter a Markdown table? */
export function escapeMarkdown(value: string): string {
  return value.replace(/[\u0000-\u0020\u007f-\u009f\u2028\u2029]/g, " ")
    .replace(/[&<>"'\\`*_{}[\]()#+.!|:=-]/g, character => `&#${character.charCodeAt(0)};`);
}
