/** Can one named proc input be read within its configured byte limit? */
import { closeSync, openSync, readSync } from "node:fs";
import { join } from "node:path";

export type UnavailableReason =
  | "unsupported_platform" | "missing_file" | "permission_denied"
  | "too_large" | "invalid_data" | "missing_field" | "counter_reset" | "no_ticks";

export type Observation<T> =
  | { value: T; reason: null }
  | { value: null; reason: UnavailableReason };

export interface ProbeContext {
  platform?: string;
  procRoot?: string;
}

export function readProcFile(
  name: "stat" | "meminfo" | "vmstat",
  maxBytes: number,
  context: ProbeContext,
): Observation<string> {
  if ((context.platform ?? process.platform) !== "linux") {
    return { value: null, reason: "unsupported_platform" };
  }
  let descriptor: number | undefined;
  try {
    descriptor = openSync(join(context.procRoot ?? "/proc", name), "r");
    const buffer = Buffer.alloc(maxBytes + 1);
    let size = 0;
    while (size < buffer.length) {
      const count = readSync(descriptor, buffer, size, buffer.length - size, null);
      if (count === 0) break;
      size += count;
    }
    if (size > maxBytes) return { value: null, reason: "too_large" };
    return { value: buffer.toString("utf8", 0, size), reason: null };
  } catch (error) {
    const code = error instanceof Error && "code" in error ? error.code : undefined;
    if (code === "ENOENT" || code === "ENOTDIR") return { value: null, reason: "missing_file" };
    if (code === "EACCES" || code === "EPERM") return { value: null, reason: "permission_denied" };
    throw new Error(`Cannot read proc ${name}${typeof code === "string" ? ` (${code})` : ""}`, { cause: error });
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
  }
}
