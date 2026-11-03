/** Carry an API refusal code without discarding its original safe execution evidence. */
import type { PlannerFailure } from "@idhazh/common-contracts";

export class PlanError extends Error {
  readonly failure: PlannerFailure | null;
  constructor(readonly code: string, message: string, readonly field: string | null = null,
    options?: ErrorOptions & { failure?: PlannerFailure | null }) {
    super(message, options);
    this.name = "PlanError";
    this.failure = options?.failure ?? null;
  }
}
