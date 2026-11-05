/** Preserve safe machine process codes and both work and cleanup causes without planner diagnostics. */
import { z } from "zod";
import type { HttpChildFailurePolicy } from "@idhazh/serve-pipeline-apis/child-failure";
import { MachineApiStartupFailureSchema } from "./read-machine-api-startup";

export class MachineApiError extends Error {
  constructor(readonly code: string, message: string, cause?: unknown) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = "MachineApiError";
  }
}

export function captureMachineApiFailure(): HttpChildFailurePolicy<MachineApiError> {
  const capture = (error: unknown) => {
    if (error instanceof MachineApiError) return error;
    // PLAN_FAILED is the existing evidence code for an uncoded caller failure.
    const code = error instanceof z.ZodError ? "INVALID_INPUT" : "PLAN_FAILED";
    return new MachineApiError(code, `${code}: Machine API operation did not complete`, error);
  };
  return {
    create: (code, message, cause) => new MachineApiError(code, message, cause),
    capture,
    async retainCleanup(error, close) {
      try { await close(); }
      catch (cleanup) {
        return new MachineApiError(error.code, error.message,
          new AggregateError([error, cleanup], "Machine API execution and cleanup failed"));
      }
      return error;
    },
    startup(error, kind) {
      const code = error instanceof MachineApiError ? error.code : `${kind}_STARTUP_FAILED`;
      const retained = new MachineApiError(code, "HTTP child operation did not complete", error);
      return { error: retained, packet: MachineApiStartupFailureSchema.parse({
        event: `${kind.toLowerCase()}_startup_failed`, code,
        message: `${code}: HTTP child operation did not complete`, failure: null,
      }) };
    },
    describe: error => ({ code: capture(error).code }),
  };
}
