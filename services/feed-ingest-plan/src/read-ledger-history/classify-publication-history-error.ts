/** Which named data-read failures make optional publisher history unavailable? */
import { ZodError } from "zod";
import { LedgerHistoryReadError } from "./ledger-history-error";

const FILE_READ_FAILURES = new Set(["ENOENT", "ENOTDIR", "EACCES", "EPERM", "EIO"]);

export function classifyPublicationHistoryError(error: unknown): string | null {
  if (error instanceof LedgerHistoryReadError) return error.message;
  if (error instanceof ZodError) return "invalid_schema";
  if (!(error instanceof Error)) return null;
  if ("code" in error && typeof error.code === "string" && FILE_READ_FAILURES.has(error.code)) {
    return error.code;
  }
  return null;
}
