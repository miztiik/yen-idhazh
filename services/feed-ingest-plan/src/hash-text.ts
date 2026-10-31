/** Compute the native SHA-256 identity of one text payload. */
import { createHash } from "node:crypto";

export function hashText(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}
