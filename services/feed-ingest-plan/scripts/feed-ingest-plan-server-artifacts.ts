/** Preserve available server evidence and logs independently of planner or metadata success. */
import { copyFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { readMachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import { serverEvidenceFilename } from "../../serve-pipeline-apis/src/server-evidence";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";

// This fixed directory is a workflow artifact boundary, not a retention policy.
export const SERVER_LOG_ARTIFACT_DIRECTORY = "server-logs";

export async function prepareServerArtifacts(input: {
  directory: string; runNumber: string; attempt: number; outputPath?: string;
}): Promise<Record<string, string>> {
  const evidence = await readMachineServerEvidence(input.directory, { run_id: input.runNumber, attempt: input.attempt });
  const outputs: Record<string, string> = {};
  const logs = new Set(evidence.map(server => server.log_filename));
  for (const server of evidence) {
    const name = serverEvidenceFilename(server.group);
    await mkdir(join(input.directory, "artifacts"), { recursive: true });
    await copyFile(join(input.directory, name), join(input.directory, "artifacts", name));
    outputs.artifact_directory = "artifacts";
  }
  for (const name of logs) {
    if (!await Bun.file(join(input.directory, name)).exists()) continue;
    await mkdir(join(input.directory, SERVER_LOG_ARTIFACT_DIRECTORY), { recursive: true });
    await copyFile(join(input.directory, name), join(input.directory, SERVER_LOG_ARTIFACT_DIRECTORY, name));
    outputs.server_logs = SERVER_LOG_ARTIFACT_DIRECTORY;
  }
  if (input.outputPath !== undefined && Object.keys(outputs).length) await writeGitHubOutputs(input.outputPath, outputs);
  return outputs;
}
