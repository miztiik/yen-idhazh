/** Which settled first-sight observations exist in the caller's named files? */
import { resolve } from "node:path";
import { readLedgerParquet } from "./read-parquet";
import { SeenRowSchema, indexSeenEvidence } from "../screen-article-candidates/seen-evidence";
import type { SeenEvidence } from "../screen-article-candidates/seen-evidence";

// The recorded SeenRow wire version, not a planning or retention control.
const seenSchemaVersion = "2026-08-31";

export async function readSeenEvidence(root: string, files: readonly string[]): Promise<{
  evidence: SeenEvidence;
  global_absence: "unavailable";
  files: readonly string[];
}> {
  if (new Set(files).size !== files.length) throw new Error("seen_files must name distinct files");
  if (files.length === 0) return {
    evidence: { availability: "unavailable" }, global_absence: "unavailable", files,
  };
  const loaded = await Promise.all(files.map(file => readLedgerParquet(
    resolve(root, file), "seen", { schema: SeenRowSchema, schemaVersion: seenSchemaVersion },
  )));
  const evidence: SeenEvidence = {
    availability: "available", rows: loaded.flatMap(file => file.rows.map(row => row.row)),
  };
  indexSeenEvidence(evidence);
  return { evidence, global_absence: "unavailable", files };
}
