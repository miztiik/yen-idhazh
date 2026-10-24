/** How does a resource cell state its unit or why its value is unavailable? */
export function measurement(value: number | null, unit: string, reason?: string): string {
  return value === null ? `Unavailable${reason === undefined ? "" : ` (${reason.replaceAll("_", " ")})`}`
    : `${Number.isInteger(value) ? value : value.toFixed(3)} ${unit}`;
}
