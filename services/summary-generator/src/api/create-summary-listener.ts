/** Which Bun options preserve the handler's JSON refusals and committed listener settings? */
import { createSummaryHandler, type SummaryHandlerOptions } from "./serve-http-api.js";

// Keep Bun's pre-handler ceiling at the largest exact JS byte count; the handler owns admission.
const BUN_REQUEST_BODY_CAPACITY = Number.MAX_SAFE_INTEGER;
// The handler's body and selected-model deadlines replace Bun's shorter idle timeout.
const HANDLER_OWNED_IDLE_TIMEOUT = 0;

export function createSummaryListener(options: SummaryHandlerOptions) {
  return {
    hostname: options.config.hostname,
    port: options.config.port,
    maxRequestBodySize: BUN_REQUEST_BODY_CAPACITY,
    idleTimeout: HANDLER_OWNED_IDLE_TIMEOUT,
    fetch: createSummaryHandler(options),
  };
}
