/** Identify default and declared browser icon downloads before dispatch. */
import type { RequestSession } from "./browser-request-gate";

export async function isBrowserIconRequest(session: RequestSession, url: string, resourceType: unknown) {
  if (resourceType === "Document") return false;
  if (new URL(url).pathname === "/favicon.ico") return true;
  // Browser icons use Other; pages can also load declared icons as images.
  if (resourceType !== "Other" && resourceType !== "Image") return false;
  const evaluated = await session.send("Runtime.evaluate", {
    expression: `Array.from(document.querySelectorAll('link[rel]'))
      .filter(link => link.rel.toLowerCase().split(/\\s+/).includes('icon')).map(link => link.href)`,
    returnByValue: true,
  });
  if (evaluated.exceptionDetails) throw new Error("Could not identify source page icons");
  const result = evaluated.result;
  if (!result || typeof result !== "object" || !("value" in result) || !Array.isArray(result.value)
    || !result.value.every((value: unknown) => typeof value === "string")) {
    throw new Error("Chromium supplied no source page icon addresses");
  }
  return result.value.includes(url);
}
