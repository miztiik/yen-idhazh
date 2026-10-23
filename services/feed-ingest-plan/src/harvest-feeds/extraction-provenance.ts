/** Fingerprint the exact extraction and sanitization implementations used by this process. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { z } from "zod";

function fingerprint(paths: readonly string[]): string {
  const digest = createHash("sha256");
  for (const path of paths) {
    digest.update(path).update("\0")
      .update(readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n")).update("\0");
  }
  return digest.digest("hex");
}

const require = createRequire(import.meta.url);
function libraryVersion(name: "defuddle" | "linkedom"): string {
  // Both pinned libraries export their entry point from one directory below their manifest.
  return z.object({ version: z.string().min(1) }).parse(JSON.parse(
    readFileSync(resolve(dirname(require.resolve(name)), "..", "package.json"), "utf8"),
  )).version;
}

export const EXTRACTOR_VERSION = `defuddle-${libraryVersion("defuddle")}-linkedom-${libraryVersion("linkedom")}-idhazh-${fingerprint([
  "dom-extractor.ts", "corroborated-words.ts", "extraction-quality.ts", "extraction-controls.ts",
  "parse-document.ts", "extraction-provenance.ts",
])}`;
export const SANITIZER_FINGERPRINT = `idhazh-typescript-sanitizer-3-${fingerprint(["sanitize-text.ts"])}`;
