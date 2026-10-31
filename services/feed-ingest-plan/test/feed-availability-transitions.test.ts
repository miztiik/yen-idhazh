/** Prove availability deadlines and retirement count only completed recovery checks. */
import { randomUUID } from "node:crypto";
import { expect, test } from "bun:test";
import { FeedAvailabilityRecordSchema } from "@idhazh/common-contracts";
import { FeedAvailabilityConfigSchema } from "../src/availability/availability-config";
import { applyAvailabilityCompletion } from "../src/availability/feed-availability";

const start = "2026-10-01T00:00:00.000Z";
const config = FeedAvailabilityConfigSchema.parse({
  state_path: "state/raw/planner/feed-availability/state.json",
  enrollment_path: "state/raw/planner/feed-availability/enrollment.json",
  initial_enrollment: "all-active-configured-sources-once",
  max_enrolled_feeds: 256,
  max_state_bytes: 1048576,
  consecutive_failed_checks_before_rest: 5,
  rest_hours: 24,
  recovery_rest_hours: 24,
  failed_recovery_checks_before_retirement: 7,
  retirement_minimum_age_hours: 36,
  max_cas_refresh_attempts: 8,
  operator_enrollments: [],
});

function record() {
  return FeedAvailabilityRecordSchema.parse({
    feed_id: "recorded-feed",
    endpoint_key: "a".repeat(64),
    consecutive_failed_checks: 0,
    rest_until: null,
    retired_at: null,
    retirement_reason: null,
    episode: null,
    reservation: null,
    last_completion: null,
    operator_enrollment_id: null,
  });
}

function atHours(hours: number) {
  return new Date(Date.parse(start) + hours * 60 * 60 * 1000).toISOString();
}

function complete(result: "confirmed-http-failure" | "timeout" | "valid-feed", completed_at: string) {
  return {
    request_id: randomUUID(),
    run_id: "2026-10-01-1",
    attempt: 1,
    completed_at,
    result,
    http_status: result === "confirmed-http-failure" ? 404 : null,
  } as const;
}

test("the fifth logical failure starts a 24-hour rest and the recovery boundary is inclusive", () => {
  const state = record();
  for (let count = 1; count <= 4; count++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", start), config);
    expect(state.rest_until).toBeNull();
  }
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", start), config);
  expect(state.rest_until).toBe(atHours(24));
  expect(state.episode?.failed_recovery_checks).toBe(0);

  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(24)), config);
  expect(state.episode?.failed_recovery_checks).toBe(1);
  expect(state.rest_until).toBe(atHours(48));
});

test("retirement requires seven failed recovery checks and the independent 36-hour age", () => {
  const state = record();
  for (let count = 0; count < 5; count++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", start), config);
  }
  for (let recovery = 1; recovery <= 6; recovery++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(recovery * 24)), config);
    expect(state.retired_at).toBeNull();
    expect(state.episode?.failed_recovery_checks).toBe(recovery);
  }
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(168)), config);
  expect(state.retired_at).toBe(atHours(168));
  expect(state.retirement_reason).toBe("confirmed-recovery-failures");
  expect(state.rest_until).toBeNull();
});

test("timeout recovery rests without advancing retirement and a valid empty feed clears the episode", () => {
  const state = record();
  for (let count = 0; count < 5; count++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", start), config);
  }
  applyAvailabilityCompletion(state, complete("timeout", atHours(24)), config);
  expect(state.episode?.failed_recovery_checks).toBe(0);
  expect(state.retired_at).toBeNull();
  expect(state.retirement_reason).toBeNull();
  expect(state.rest_until).toBe(atHours(48));

  applyAvailabilityCompletion(state, complete("valid-feed", atHours(48)), config);
  expect(state.episode).toBeNull();
  expect(state.consecutive_failed_checks).toBe(0);
  expect(state.rest_until).toBeNull();
});

test("a long episode with fewer than seven failed recovery checks is not retired", () => {
  const shortEpisodeConfig = FeedAvailabilityConfigSchema.parse({
    ...config,
    failed_recovery_checks_before_retirement: 7,
  });
  const state = record();
  for (let count = 0; count < 5; count++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", start), shortEpisodeConfig);
  }
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(24)), shortEpisodeConfig);
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(48)), shortEpisodeConfig);
  expect(Date.parse(atHours(48)) - Date.parse(state.episode!.first_confirmed_failure_at)).toBeGreaterThanOrEqual(36 * 60 * 60 * 1000);
  expect(state.episode?.failed_recovery_checks).toBe(2);
  expect(state.retired_at).toBeNull();
});

test("configured rest intervals preserve the elapsed gate anchored before rest entry", () => {
  const hourly = FeedAvailabilityConfigSchema.parse({ ...config, rest_hours: 1, recovery_rest_hours: 1 });
  const state = record();
  for (let count = 0; count < 4; count++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", start), hourly);
  }
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(10)), hourly);
  expect(state.rest_until).toBe(atHours(11));
  for (let hour = 11; hour <= 17; hour++) {
    applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(hour)), hourly);
  }
  expect(state.episode?.failed_recovery_checks).toBe(7);
  expect(state.episode?.first_confirmed_failure_at).toBe(start);
  expect(state.retired_at).toBeNull();
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(35)), hourly);
  expect(state.retired_at).toBeNull();
  expect(state.rest_until).toBe(atHours(36));
  applyAvailabilityCompletion(state, complete("confirmed-http-failure", atHours(36)), hourly);
  expect(state.retired_at).toBe(atHours(36));
  expect(() => FeedAvailabilityConfigSchema.parse({ ...config, recovery_rest_hours: 0 })).toThrow();
});
