/** Distinguish refused native history from unexpected implementation errors. */
import { z } from "zod";
import { PlannerLedgerFileError } from "@idhazh/ledger-file-writer";
import { LedgerHistoryReadError } from "./ledger-history-error";

export function classifyPlannerHistoryGap(error: unknown): string | null {
  if (error instanceof z.ZodError) return "schema_refused";
  if (error instanceof LedgerHistoryReadError || error instanceof PlannerLedgerFileError) return "native_refused";
  if (error instanceof Error && "code" in error && typeof error.code === "string"
    && ["ENOENT", "EACCES", "EPERM", "EISDIR", "ENOTDIR"].includes(error.code)) {
    return error.code === "ENOENT" ? "missing" : "file_refused";
  }
  return null;
}
