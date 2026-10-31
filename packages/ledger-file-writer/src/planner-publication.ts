/** Exclude unsupported planner publication files without changing their historical inputs. */
import {
  PlannerPublicationRequestSchema, PlannerPublicationResultSchema,
} from "@idhazh/common-contracts";
import type { CompactIndex, PlannerPublicationResult } from "@idhazh/common-contracts";
import { PlannerUnsupportedFormatError } from "./read-planner-file";
import { readNamedPlannerFile } from "./validate-planner-files";

function periodFile(ledger: string, period: CompactIndex["period"], covers: string) {
  const suffix = period === "yearly" ? `${covers}/${covers}` : covers.replaceAll("-", "/");
  return `compact/feed-ingest-plan/${ledger}/${period}/${suffix}.parquet`;
}
function coveredDays(period: CompactIndex["period"], covers: string): string[] {
  const from = `${covers}${period === "yearly" ? "-01-01" : period === "monthly" ? "-01" : ""}`;
  const start = new Date(`${from}T00:00:00Z`);
  const end = new Date(start);
  if (period === "yearly") end.setUTCFullYear(end.getUTCFullYear() + 1);
  else if (period === "monthly") end.setUTCMonth(end.getUTCMonth() + 1);
  else end.setUTCDate(end.getUTCDate() + 1);
  const days: string[] = [];
  for (const date = new Date(start); date < end; date.setUTCDate(date.getUTCDate() + 1)) {
    days.push(date.toISOString().slice(0, 10));
  }
  return days;
}
export async function selectPlannerPublication(root: string, raw: unknown): Promise<PlannerPublicationResult> {
  const request = PlannerPublicationRequestSchema.parse(raw);
  const result: PlannerPublicationResult = { files: [], indexes: structuredClone(request.indexes), refused: [] };
  const refused = new Set<string>();
  for (const file of request.files) {
    try {
      await readNamedPlannerFile(root, file.path, file.ledger);
      result.files.push(file.path);
    } catch (error) {
      if (!(error instanceof PlannerUnsupportedFormatError)) throw error;
      refused.add(file.path);
      result.refused.push({ ...file, envelope_version: error.envelopeVersion, row_schema_version: error.rowSchemaVersion });
    }
  }
  for (const index of Object.values(result.indexes)) for (const entry of index.entries) {
    if (!refused.has(periodFile(index.ledger, index.period, entry.covers))) continue;
    entry.state = index.period === "daily" ? "lost" : "empty";
    entry.rows = 0;
    entry.bytes = 0;
    entry.file_sha256 = null;
    if (index.period !== "daily") {
      entry.lost_days = coveredDays(index.period, entry.covers);
      entry.set_aside++;
    }
  }
  return PlannerPublicationResultSchema.parse(result);
}
