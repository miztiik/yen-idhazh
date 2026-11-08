/** Bind shared server evidence to the real native profile validator for every machine and feed reader. */
import { createCurrentServerEvidenceSchema, createServerEvidenceSchema } from "@idhazh/serve-pipeline-apis/evidence";
import { readServerEvidence } from "@idhazh/serve-pipeline-apis/read-evidence";
import { TaskProfileSchema } from "../task-profile/profile-schema";
import type { z } from "zod";

export const MachineServerEvidenceSchema = createServerEvidenceSchema(TaskProfileSchema);
export const CurrentMachineServerEvidenceSchema = createCurrentServerEvidenceSchema(TaskProfileSchema);
export type MachineServerEvidence = z.infer<typeof MachineServerEvidenceSchema>;

export function readMachineServerEvidence(directory: string, expected?: { run_id: string; attempt: number }) {
  return readServerEvidence(directory, MachineServerEvidenceSchema, expected);
}
