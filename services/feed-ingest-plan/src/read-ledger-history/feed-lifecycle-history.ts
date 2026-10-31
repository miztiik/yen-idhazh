/** Reuse supported lifecycle fields and recover only a missing lifecycle calculation. */
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import {
  FeedLifecycleFieldsSchema, FeedHealthRestFieldsSchema, observationGroups, RecordedInstantSchema,
} from "@idhazh/common-contracts";
import type { FeedLifecycleFields, FeedLifecyclePolicy, FeedHealthStateRow } from "@idhazh/common-contracts";
import { applyFeedCheck, resolveFeedEligibility, createUnknownFeedLifecycle } from "../availability/feed-lifecycle";
import type { FeedCheck } from "../availability/feed-lifecycle";
import { selectNewestCalculation } from "./saved-calculation";

const partialRest = z.object(FeedHealthRestFieldsSchema.shape).partial();
type Evidence = z.infer<typeof partialRest>;
const partialLifecycle = FeedLifecycleFieldsSchema.partial();

export function reuseFeedLifecycle(
  rows: readonly Evidence[], now: string, policy: FeedLifecyclePolicy,
  onGap: (reason: string) => void,
): FeedLifecycleFields {
  const snapshots = rows.flatMap(row => {
    const parsed = partialLifecycle.safeParse(row);
    if (!parsed.success || Object.keys(parsed.data).length === 0) return [];
    const at = row.availability_updated_at ?? row.checked_at ?? null;
    if (at !== null && !RecordedInstantSchema.safeParse(at).success) return [];
    return [{ at, value: parsed.data }];
  });
  const selected = selectNewestCalculation(snapshots, now);
  if (selected.conflicting.length) {
    onGap("availability-order-ambiguous");
    const common: Partial<FeedLifecycleFields> = {};
    for (const field of Object.keys(FeedLifecycleFieldsSchema.shape) as (keyof FeedLifecycleFields)[]) {
      const value = selected.conflicting[0]![field];
      if (value !== undefined && selected.conflicting.every(row => isDeepStrictEqual(row[field], value))) {
        Object.assign(common, { [field]: value });
      }
    }
    return supportedLifecycle({ ...createUnknownFeedLifecycle(), ...common, availability_complete: false }, now);
  }
  if (selected.value !== null && FeedLifecycleFieldsSchema.safeParse(selected.value).success) {
    const saved = FeedLifecycleFieldsSchema.parse(selected.value);
    const knownFailure = rows.some(row => row.check_request_id != null && row.checked_at != null
      && row.check_result != null && row.check_result !== "valid-feed" && row.check_result !== "interrupted"
      && Date.parse(row.checked_at) <= Date.parse(now));
    if (saved.strikes === null && knownFailure) {
      onGap("observed-failure-count-missing");
      const recovered = recoverFeedLifecycle(rows, now, policy, onGap);
      return supportedLifecycle({
        ...saved, strikes: recovered.strikes,
        availability: saved.availability === "unknown" ? recovered.availability : saved.availability,
        rest_until: saved.rest_until ?? recovered.rest_until,
        retired_at: saved.retired_at ?? recovered.retired_at,
        retirement_reason: saved.retirement_reason ?? recovered.retirement_reason,
        first_confirmed_failure_at: saved.first_confirmed_failure_at ?? recovered.first_confirmed_failure_at,
        failed_recovery_checks: saved.failed_recovery_checks ?? recovered.failed_recovery_checks,
        availability_updated_at: saved.availability_updated_at ?? recovered.availability_updated_at,
        availability_complete: false,
      }, now);
    }
    return supportedLifecycle(saved, now);
  }
  onGap("availability-calculation-missing");
  const recovered = recoverFeedLifecycle(rows, now, policy, onGap);
  return supportedLifecycle(FeedLifecycleFieldsSchema.parse({ ...recovered, ...selected.value,
    availability_complete: selected.value?.availability_complete === false ? false : recovered.availability_complete }), now);
}

function supportedLifecycle(value: FeedLifecycleFields, now: string): FeedLifecycleFields {
  if (value.retired_at === null || value.retirement_reason === null) {
    value = { ...value, retired_at: null, retirement_reason: null };
  }
  return { ...value, availability: resolveFeedEligibility(value, now) };
}

export function recoverFeedLifecycle(
  rows: readonly Evidence[], now: string, policy: FeedLifecyclePolicy, onGap: (reason: string) => void,
): FeedLifecycleFields {
  const checks = new Map<string, FeedCheck & { date: string; run_id: string; checked_at: string }>();
  const conflicted = new Set<string>();
  for (const row of rows) {
    const parsed = partialRest.safeParse(row);
    if (!parsed.success || row.run_id === undefined || row.date === undefined
      || row.check_request_id == null || row.check_result == null || row.checked_at == null
      || row.status === undefined || !RecordedInstantSchema.safeParse(row.checked_at).success
      || Date.parse(row.checked_at) > Date.parse(now)) continue;
    const fact = { check_request_id: row.check_request_id, check_result: row.check_result,
      checked_at: row.checked_at, status: row.status };
    const previous = checks.get(row.check_request_id);
    if (previous !== undefined && !isDeepStrictEqual({
      check_request_id: previous.check_request_id, check_result: previous.check_result,
      checked_at: previous.checked_at, status: previous.status,
    }, fact)) conflicted.add(row.check_request_id);
    else checks.set(row.check_request_id, { ...fact, date: row.date, run_id: row.run_id });
  }
  if (conflicted.size) onGap("logical-check-conflict");
  let value = createUnknownFeedLifecycle();
  const ordered = observationGroups([...checks.values()].filter(row => !conflicted.has(row.check_request_id!)));
  for (const group of ordered) {
    if (group.length > 1) {
      onGap("availability-order-ambiguous");
      value = createUnknownFeedLifecycle();
      continue;
    }
    value = applyFeedCheck(value, group[0]!, policy);
  }
  return value;
}

export function updateFeedLifecycle(
  prior: FeedLifecycleFields, rows: readonly FeedHealthStateRow[], policy: FeedLifecyclePolicy,
): FeedLifecycleFields {
  let value = prior;
  const seen = new Set<string>();
  for (const row of [...rows].sort((a, b) => (a.checked_at ?? "").localeCompare(b.checked_at ?? ""))) {
    if (row.check_request_id === null || seen.has(row.check_request_id)) continue;
    seen.add(row.check_request_id);
    value = applyFeedCheck(value, row, policy);
  }
  return value;
}
