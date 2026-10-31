/** What supported lifecycle decision follows one completed logical feed check? */
import { definitelyAfter, FeedLifecycleFieldsSchema } from "@idhazh/common-contracts";
import type { FeedCheckResult, FeedHealthStateRow, FeedLifecycleFields, FeedLifecyclePolicy } from "@idhazh/common-contracts";
import type { FetchResult } from "../harvest-feeds/robots-policy";

const millisecondsPerHour = 3_600_000;
export type FeedCheck = Pick<FeedHealthStateRow, "check_request_id" | "check_result" | "checked_at" | "status">;

export function createUnknownFeedLifecycle(): FeedLifecycleFields {
  return {
    availability: "unknown", strikes: null, rest_until: null,
    first_confirmed_failure_at: null, failed_recovery_checks: null,
    retired_at: null, retirement_reason: null, availability_updated_at: null,
    availability_complete: false,
  };
}

export function resolveFeedEligibility(lifecycle: FeedLifecycleFields, at: string): FeedLifecycleFields["availability"] {
  if (lifecycle.retired_at !== null && lifecycle.retirement_reason !== null) return "retired";
  if (lifecycle.rest_until !== null && Date.parse(at) < Date.parse(lifecycle.rest_until)) return "resting";
  return lifecycle.availability === "unknown" ? "unknown" : "eligible";
}

export function applyFeedCheck(
  prior: FeedLifecycleFields, check: FeedCheck, policy: FeedLifecyclePolicy,
): FeedLifecycleFields {
  if (check.check_result === null || check.check_request_id === null || check.checked_at === null) return { ...prior };
  const at = check.checked_at;
  if (prior.availability_updated_at !== null && !definitelyAfter(at, prior.availability_updated_at)) {
    return { ...prior, availability_complete: false };
  }
  if (check.check_result === "confirmed-http-failure"
    && !(check.status === 404 || check.status === 410 || (check.status !== null && check.status >= 500))) {
    throw new Error("Only confirmed target HTTP 404, 410 or 5xx can advance retirement");
  }
  if (check.check_result === "valid-feed") return {
    availability: "eligible", strikes: 0, rest_until: null,
    first_confirmed_failure_at: null, failed_recovery_checks: 0,
    retired_at: null, retirement_reason: null, availability_updated_at: at, availability_complete: true,
  };
  if (check.check_result === "interrupted") {
    return { ...prior, availability_complete: false };
  }
  const next = { ...prior, availability_updated_at: at };
  const recovery = prior.rest_until !== null && Date.parse(at) >= Date.parse(prior.rest_until);
  next.strikes = prior.strikes === null ? 1 : prior.strikes + 1;
  if (check.check_result === "confirmed-http-failure") {
    if (prior.first_confirmed_failure_at === null) {
      next.first_confirmed_failure_at = at;
      next.failed_recovery_checks = recovery ? 1 : 0;
    } else if (recovery) {
      next.failed_recovery_checks = prior.failed_recovery_checks === null ? 1 : prior.failed_recovery_checks + 1;
    }
  }
  if (recovery || (next.strikes !== null && next.strikes >= policy.consecutive_failed_checks_before_rest)) {
    const hours = recovery ? policy.recovery_rest_hours : policy.rest_hours;
    next.rest_until = new Date(Date.parse(at) + hours * millisecondsPerHour).toISOString();
  }
  if (check.check_result === "confirmed-http-failure" && recovery
    && next.failed_recovery_checks !== null && next.first_confirmed_failure_at !== null
    && next.failed_recovery_checks >= policy.failed_recovery_checks_before_retirement
    && Date.parse(at) - Date.parse(next.first_confirmed_failure_at) >= policy.retirement_minimum_age_hours * millisecondsPerHour) {
    next.retired_at = at;
    next.retirement_reason = "confirmed-recovery-failures";
    next.rest_until = null;
  }
  next.availability = resolveFeedEligibility({ ...next, availability: next.strikes === null ? "unknown" : "eligible" }, at);
  return FeedLifecycleFieldsSchema.parse(next);
}

export function classifyFeedFetchFailure(fetched: Pick<FetchResult, "failure" | "http_status">): FeedCheckResult {
  if (fetched.failure === "http") {
    return fetched.http_status === 404 || fetched.http_status === 410
      || (fetched.http_status !== null && fetched.http_status >= 500)
      ? "confirmed-http-failure" : "other-http-failure";
  }
  if (fetched.failure === "timeout") return "timeout";
  if (fetched.failure === "robots-denied" || fetched.failure === "robots-unknown") return "robots";
  return fetched.failure === "unsafe-target" ? "local-failure" : "transport-unknown";
}

export function classifyParserResult(failure: string | null): FeedCheckResult {
  if (failure === null) return "valid-feed";
  if (failure === "parser-timeout") return "timeout";
  if (failure === "parser-cancelled") return "interrupted";
  return "local-failure";
}
