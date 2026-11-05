/** Does private and uncached HTTP readiness identify this exact owned listener? */
import { z } from "zod";
import { writeTraceContext } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { API_HEALTH_PATH, ApiReadySchema } from "./api-startup";
import type { ApiReady } from "./api-startup";
import { apiOrigin } from "./load-settings";
import type { HonoServerSettings } from "./load-settings";
import type { HttpChildFailurePolicy, HttpChildKind } from "./http-child-failure";

export async function readApiReadiness(input: {
  message: unknown; expected: ApiReady; server: HonoServerSettings; context: OperationMetadata;
  kind: HttpChildKind; failure: Pick<HttpChildFailurePolicy, "create">; signal: AbortSignal;
}): Promise<string> {
  const { signal, kind } = input;
  const ready = ApiReadySchema.parse(input.message);
  const mismatch = () => input.failure.create(`${kind}_READY_IDENTITY`, "Readiness does not match the owned child and captured module controls");
  if (!ready.enabled || JSON.stringify(ready) !== JSON.stringify(ApiReadySchema.parse(input.expected))) throw mismatch();
  const origin = apiOrigin(input.server);
  const headers = writeTraceContext(input.context);
  const response = await fetch(new URL(API_HEALTH_PATH, origin), { signal, headers, redirect: "error" });
  const health = z.strictObject({ identity: ApiReadySchema }).parse(await response.json());
  if (response.status !== 200 || response.headers.get("cache-control") !== "no-store"
    || JSON.stringify(health.identity) !== JSON.stringify(ready)) throw mismatch();
  return origin;
}
