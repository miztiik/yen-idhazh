/** Can one named proc input be read within its configured byte limit? */
import { closeSync, openSync, readSync } from "node:fs";
import { join } from "node:path";

export const UNAVAILABLE_REASONS = [
  "unsupported_platform", "missing_file", "permission_denied", "too_large",
  "invalid_data", "missing_field", "counter_reset", "no_ticks",
] as const;
export type UnavailableReason = typeof UNAVAILABLE_REASONS[number];

export type Observation<T, Reason extends string = UnavailableReason> =
  | { value: T; reason: null }
  | { value: null; reason: Reason };

export interface ProbeContext {
  platform?: string | undefined;
  procRoot?: string | undefined;
}

export function readProcFile(
  name: "stat" | "meminfo" | "vmstat" | `${number}/stat` | `${number}/status`,
  maxBytes: number,
  context: ProbeContext,
  scratch?: Buffer,
): Observation<string> {
  if (!/^(stat|meminfo|vmstat|[1-9]\d*\/(stat|status))$/.test(name)) {
    throw new Error("Invalid named proc input");
  }
  if ((context.platform ?? process.platform) !== "linux") {
    return { value: null, reason: "unsupported_platform" };
  }
  let descriptor: number | undefined;
  try {
    descriptor = openSync(join(context.procRoot ?? "/proc", name), "r");
    const buffer = scratch ?? Buffer.alloc(maxBytes + 1);
    if (buffer.length !== maxBytes + 1) throw new Error("Proc buffer differs from the configured byte limit");
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
