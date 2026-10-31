/** Prove configured timed lifecycle decisions without remote state or invented evidence. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { FeedLifecyclePolicySchema } from "@idhazh/common-contracts";
import type { FeedLifecycleFields } from "@idhazh/common-contracts";
import { applyFeedCheck, resolveFeedEligibility, createUnknownFeedLifecycle } from "../src/availability/feed-lifecycle";

async function policy() {
  const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  return FeedLifecyclePolicySchema.parse(config.availability);
}
const at = (hours: number) => new Date(Date.parse("2026-10-01T00:00:00.000Z") + hours * 3_600_000).toISOString();
const check = (hours: number, result: "valid-feed" | "confirmed-http-failure" | "timeout" | "interrupted" = "confirmed-http-failure") => ({
  check_request_id: randomUUID(), check_result: result, checked_at: at(hours),
  status: result === "confirmed-http-failure" ? 503 : null,
});

test("the fifth failure rests for 24 hours and the exact UTC deadline permits recovery", async () => {
  const settings = await policy();
  let value = applyFeedCheck(createUnknownFeedLifecycle(), check(0, "valid-feed"), settings);
  for (let hour = 1; hour <= 5; hour++) value = applyFeedCheck(value, check(hour), settings);
  expect(value).toMatchObject({ strikes: 5, rest_until: at(29), failed_recovery_checks: 0, availability_complete: true });
  expect(resolveFeedEligibility(value, at(28.999))).toBe("resting");
  expect(resolveFeedEligibility(value, at(29))).toBe("eligible");
  value = applyFeedCheck(value, check(29), settings);
  expect(value).toMatchObject({ rest_until: at(53), failed_recovery_checks: 1, retired_at: null });
});

test("retirement needs both seven confirmed recovery failures and the configured episode age", async () => {
  const settings = await policy();
  let value = applyFeedCheck(createUnknownFeedLifecycle(), check(0, "valid-feed"), settings);
  for (let hour = 1; hour <= 5; hour++) value = applyFeedCheck(value, check(hour), settings);
  for (let recovery = 1; recovery <= 7; recovery++) {
    const hour = 5 + recovery * settings.recovery_rest_hours;
    value = applyFeedCheck(value, check(hour), settings);
    expect(value.retired_at).toBe(recovery === 7 ? at(hour) : null);
  }
  expect(value).toMatchObject({ availability: "retired", rest_until: null, retirement_reason: "confirmed-recovery-failures" });
  const younger: FeedLifecycleFields = { ...value, retired_at: null, retirement_reason: null,
    availability: "resting", rest_until: at(200), failed_recovery_checks: 6, first_confirmed_failure_at: at(199) };
  expect(applyFeedCheck(younger, check(200), settings).retired_at).toBeNull();
});

test("timeout cannot advance retirement; a valid empty feed resets even incomplete history", async () => {
  const settings = await policy();
  const prior: FeedLifecycleFields = { ...createUnknownFeedLifecycle(), strikes: 5, rest_until: at(24),
    first_confirmed_failure_at: at(0), failed_recovery_checks: 6, availability_updated_at: at(0), availability: "resting" };
  const timed = applyFeedCheck(prior, check(24, "timeout"), settings);
  expect(timed).toMatchObject({ strikes: 6, failed_recovery_checks: 6, retired_at: null, rest_until: at(48) });
  const reset = applyFeedCheck(timed, check(48, "valid-feed"), settings);
  expect(reset).toMatchObject({ availability: "eligible", strikes: 0, rest_until: null,
    first_confirmed_failure_at: null, failed_recovery_checks: 0, availability_complete: true });
});

test("supported rest survives missing counts and interruption never invents source failure or retirement", async () => {
  const settings = await policy();
  const prior = { ...createUnknownFeedLifecycle(), availability: "resting" as const,
    rest_until: at(24), availability_updated_at: at(0) };
  expect(resolveFeedEligibility(prior, at(1))).toBe("resting");
  const interrupted = applyFeedCheck(prior, check(1, "interrupted"), settings);
  expect(interrupted).toEqual(prior);
  const failed = applyFeedCheck(prior, check(24), settings);
  expect(failed).toMatchObject({ strikes: 1, failed_recovery_checks: 1, retired_at: null, availability_complete: false });
  expect(resolveFeedEligibility(createUnknownFeedLifecycle(), at(0))).toBe("unknown");
  expect(() => applyFeedCheck(prior, { ...check(24), status: 403 }, settings)).toThrow("confirmed target HTTP");
});

test("uncertain transport failures advance observed logical rest counts but never confirmed retirement", async () => {
  const settings = await policy();
  let value = createUnknownFeedLifecycle();
  for (let hour = 0; hour < settings.consecutive_failed_checks_before_rest; hour++) {
    value = applyFeedCheck(value, { ...check(hour), check_result: "transport-unknown", status: null }, settings);
    expect(value.strikes).toBe(hour + 1);
    expect(value.availability_complete).toBe(false);
    expect(value.first_confirmed_failure_at).toBeNull();
    expect(value.failed_recovery_checks).toBeNull();
    expect(value.retired_at).toBeNull();
  }
  expect(value.availability).toBe("resting");
  expect(value.rest_until).toBe(at(4 + settings.rest_hours));
  const recovery = applyFeedCheck(value, {
    ...check(4 + settings.rest_hours), check_result: "transport-unknown", status: null,
  }, settings);
  expect(recovery).toMatchObject({ strikes: 6, failed_recovery_checks: null, retired_at: null });
});
