/** How is one named host input read without unbounded allocation? */
import { open } from "node:fs/promises";
import { join } from "node:path";
import type { ServiceConfig } from "../config";

export type Inspection = {
  platform?: NodeJS.Platform;
  root?: string;
  environment?: NodeJS.ProcessEnv;
  unavailable?: Record<string, string>;
  metadata?: Response;
};
export function unavailable(context: Inspection, field: string, reason: string): null {
  if (context.unavailable) context.unavailable[field] = reason;
  return null;
}
export function hostPath(context: Inspection, path: string): string {
  return context.root ? join(context.root, ...path.split("/").filter(Boolean)) : path;
}
export async function readInput(path: string, config: ServiceConfig, context: Inspection): Promise<string | null> {
  let file;
  try {
    file = await open(hostPath(context, path), "r");
  } catch (error) {
    if (error instanceof Error && "code" in error && ["ENOENT", "EACCES", "EPERM", "ENOTDIR"].includes(String(error.code))) return unavailable(context, path, String(error.code));
    throw error;
  }
  try {
    const bytes = Buffer.alloc(config.max_input_bytes + 1);
    let used = 0;
    while (used < bytes.length) {
      const { bytesRead } = await file.read(bytes, used, bytes.length - used, null);
      if (!bytesRead) break;
      used += bytesRead;
    }
    if (used > config.max_input_bytes) return unavailable(context, path, "input_too_large");
    return bytes.subarray(0, used).toString("utf8");
  } finally {
    await file.close();
  }
}
export function parseInteger(text: string | null | undefined): number | null {
  if (!text || !/^-?\d+$/.test(text.trim())) return null;
  const value = Number(text.trim());
  return Number.isSafeInteger(value) ? value : null;
}
export function parsePositive(text: string | null | undefined): number | null {
  if (!text?.trim() || !/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(text.trim())) return null;
  const value = Number(text.trim());
  return Number.isFinite(value) && value > 0 ? value : null;
}
