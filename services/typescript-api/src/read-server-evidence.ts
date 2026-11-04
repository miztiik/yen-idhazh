/** Read only the three named current-task outcomes, never discover a growing log directory. */
import { join } from "node:path";
import { ApiGroupSchema, ServerEvidenceSchema, serverEvidenceFilename } from "./server-evidence";
import type { ServerEvidence } from "./server-evidence";

export async function readServerEvidence(directory: string, expected?: { run_id: string; attempt: number }): Promise<ServerEvidence[]> {
  const results: ServerEvidence[] = [];
  for (const group of ApiGroupSchema.options) {
    const file = Bun.file(join(directory, serverEvidenceFilename(group)));
    if (!await file.exists()) continue;
    const evidence = ServerEvidenceSchema.parse(await file.json());
    if (evidence.group !== group || (expected !== undefined
      && (evidence.run_id !== expected.run_id || evidence.attempt !== expected.attempt))) {
      throw new Error("Server evidence does not belong to this task and invocation");
    }
    results.push(evidence);
  }
  return results;
}
