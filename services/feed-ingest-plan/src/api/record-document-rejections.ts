/** Retain terminal document rejections until their owning run can save one batch. */
import type { CandidateRejectionRecord } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { DocumentState } from "./document-state";
import { recordHarvestFailures } from "../record-harvest-failures";

export async function recordDocumentRejections(rows: readonly CandidateRejectionRecord[], state: DocumentState, inputs: PlanInputs) {
  if (state.plan_owned) {
    (state.harvest_rejections ??= []).push(...rows);
    return;
  }
  await recordHarvestFailures(rows, state.context, inputs);
}
