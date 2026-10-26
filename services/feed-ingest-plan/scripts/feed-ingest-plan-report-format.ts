/** How are Markdown cells and GitHub workflow notices escaped? */
export function escapeCommand(value: string): string {
  return value.replaceAll("%", "%25").replaceAll("\r", "%0D").replaceAll("\n", "%0A");
}

export function escapeParameter(value: string): string {
  return escapeCommand(value).replaceAll(":", "%3A").replaceAll(",", "%2C");
}

export function escapeMarkdown(value: string): string {
  return value.replace(/[\u0000-\u0020\u007f-\u009f\u2028\u2029]/g, " ")
    .replace(/[&<>"'\\`*_{}[\]()#+.!|:=-]/g, character => `&#${character.charCodeAt(0)};`);
}

export function resourceNotice(value: string): string {
  return `::notice title=${escapeParameter("Feed ingest resource profile")}::${escapeCommand(value)}`;
}
