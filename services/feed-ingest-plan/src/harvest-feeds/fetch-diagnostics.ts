/** Translate actual fetch outcomes into bounded evidence and the production failure vocabulary. */
import { HarvestDiagnosticsSchema } from "@idhazh/common-contracts";
import type { HarvestDiagnostics } from "@idhazh/common-contracts";
import type { FetchResult } from "./robots-policy";

function failureCode(result: FetchResult): HarvestDiagnostics["failure_code"] {
  switch (result.failure) {
    case null: return null;
    case "robots-denied": return "robots_denied";
    case "robots-unknown": return "robots_unreachable";
    case "unsafe-target": return "blocked_address";
    case "http":
      if (result.http_status === 429) return "http_rate_limited";
      if (result.http_status !== null && result.http_status >= 500) return "http_server_error";
      if (result.http_status !== null && result.http_status >= 400) return "http_client_error";
      return "unknown";
    case "dns": case "network": case "timeout": return "network_error";
    case "body-too-large": case "redirect-loop": return "unknown";
  }
}

export function fetchDiagnostics(result: FetchResult, fetch_ms: number | null): HarvestDiagnostics {
  return HarvestDiagnosticsSchema.parse({
    http_status: result.http_status, robots: result.robots, fetch_failure: result.failure,
    robots_failure: result.robots_failure ?? null, robots_http_status: result.robots_http_status ?? null,
    body_limit: result.body_limit ?? null,
    error_code: result.error_code ?? null,
    failure_code: failureCode(result), stopped_stage: result.failure === null ? null : "fetch",
    detail: result.failure, fetch_ms,
  });
}
