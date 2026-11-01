/** Converts a writer exception into fixed diagnostic values without retaining its text. */
import { z } from "zod";
import {
  PLANNER_MAINTENANCE_FAILURE_VERSION, PlannerMaintenanceFailureSchema,
} from "@idhazh/common-contracts";
import type { PlannerMaintenanceFailure } from "@idhazh/common-contracts";

function failureCode(error: unknown): PlannerMaintenanceFailure["code"] {
  if (error instanceof z.ZodError) return "invalid-contract";
  if (error instanceof Error && "code" in error) {
    switch (error.code) {
      case "ENOENT": return "missing-local-member";
      case "EACCES": case "EPERM": return "permission-denied";
      case "ENOSPC": return "no-space";
      case "EIO": return "io-error";
    }
  }
  return "unexpected-error";
}

export class PlannerMaintenanceFailureError extends Error {
  readonly detail: PlannerMaintenanceFailure;

  constructor(stage: PlannerMaintenanceFailure["stage"], error: unknown,
    code?: PlannerMaintenanceFailure["code"]) {
    super("Planner maintenance failed");
    this.detail = PlannerMaintenanceFailureSchema.parse({
      version: PLANNER_MAINTENANCE_FAILURE_VERSION, status: "failed",
      stage, code: code ?? failureCode(error),
    });
  }
}
