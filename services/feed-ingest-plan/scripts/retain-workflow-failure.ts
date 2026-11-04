/** Preserve workflow failure evidence in the existing response file, not a second history. */
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { PlannerSavedResponseSchema } from "@idhazh/common-contracts";
import type { PlannerRunResponse } from "@idhazh/common-contracts";
import { writeAtomically } from "@idhazh/ledger-file-writer";
import { describePlanError } from "../src/api/plan-request";
import { combinePlannerFailures, withPlannerFailure } from "../src/api/plan-failure";
import type { FailureCaptureOptions } from "../src/api/plan-failure";

export async function retainWorkflowFailure(input: {
  directory: string; error: unknown; capture: FailureCaptureOptions; response?: PlannerRunResponse;
}) {
  await mkdir(input.directory, { recursive: true });
  const path = join(input.directory, "response.json");
  const file = Bun.file(path);
  const saved = input.response ?? (await file.exists() ? PlannerSavedResponseSchema.parse(await file.json()) : undefined);
  const capture = saved !== undefined && "planning_complete" in saved ? {
    ...input.capture, execution: {
      run_id: saved.run_id, attempt: saved.attempt,
      traceId: input.capture.execution?.traceId ?? null, spanId: input.capture.execution?.spanId ?? null,
      git_sha: input.capture.execution !== undefined && "writer" in input.capture.execution
        ? input.capture.execution.writer.git_sha : input.capture.execution?.git_sha ?? saved.failure?.execution.git_sha ?? null,
    },
  } : input.capture;
  const received = describePlanError(withPlannerFailure(input.error, capture), undefined, capture);
  const failure = saved?.failure === null || saved?.failure === undefined ? received.failure
    : received.failure === null ? saved.failure
    : combinePlannerFailures(saved.failure, received.failure, capture.limits);
  const response = PlannerSavedResponseSchema.parse({ ...(saved ?? received), failure });
  await writeAtomically(path, Buffer.from(JSON.stringify(response), "utf8"));
  return response;
}
