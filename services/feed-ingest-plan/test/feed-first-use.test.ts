/** Native lifecycle reloads retain observed failures without inventing confirmed history. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema } from "@idhazh/common-contracts";
import { readPlannerParquet } from "@idhazh/ledger-file-writer";
import { recordedPlan } from "./plan-recordings";
import { readPlannerOutputRecording } from "./planner-output-recordings";
import { writeRows } from "./partition-fixtures";
import { applyFeedCheck, classifyFeedFetchFailure, createUnknownFeedLifecycle, resolveFeedEligibility } from "../src/availability/feed-lifecycle";
import { createPermittedFetcher } from "../src/harvest-feeds/robots-policy";

test("native reloads preserve first-use rest and confirmed recovery retirement", async () => {
  const fixture = await recordedPlan();
  try {
    const settings = fixture.inputs.harvest.config.availability;
    const { health } = await readPlannerOutputRecording();
    const base = health.rows[0]!;
    let lifecycle = createUnknownFeedLifecycle();
    let run = 900;
    const initial = Date.parse("2026-10-21T00:00:00.000Z");
    const at = (hours: number) => new Date(initial + hours * 3_600_000).toISOString();
    async function check(hours: number) {
      const now = at(hours);
      const observed = { check_request_id: randomUUID(), check_result: "confirmed-http-failure" as const,
        checked_at: now, status: 503 };
      lifecycle = applyFeedCheck(lifecycle, observed, settings);
      const row = FeedHealthStateRowSchema.parse({ ...base, ...lifecycle, ...observed,
        date: now.slice(0, 10), run_id: `${now.slice(0, 10)}-${run++}`, availability_updated_at: now });
      const written = await writeRows(fixture.inputs.outputRoot, "feed-health-state", row.date, FeedHealthStateRowContract, [row]);
      const actual = await readPlannerParquet(join(fixture.inputs.outputRoot, written.files[0]!.path), "feed-health-state", FeedHealthStateRowContract);
      expect(actual.rows).toEqual([row]);
      lifecycle = actual.rows[0]!;
      return row;
    }
    for (let count = 1; count <= settings.consecutive_failed_checks_before_rest; count++) {
      const row = await check(count - 1);
      expect(row).toMatchObject({ strikes: count, availability_complete: false,
        first_confirmed_failure_at: at(0), failed_recovery_checks: 0 });
      expect(row.availability).toBe(count < settings.consecutive_failed_checks_before_rest ? "eligible" : "resting");
    }
    const deadline = settings.consecutive_failed_checks_before_rest - 1 + settings.rest_hours;
    expect(lifecycle.rest_until).toBe(at(deadline));
    expect(resolveFeedEligibility(lifecycle, at(deadline - 1))).toBe("resting");
    expect(resolveFeedEligibility(lifecycle, at(deadline))).toBe("eligible");
    for (let count = 1; count <= settings.failed_recovery_checks_before_retirement; count++) {
      const row = await check(deadline + (count - 1) * settings.recovery_rest_hours);
      expect(row.failed_recovery_checks).toBe(count);
      expect(row.availability_complete).toBe(false);
      expect(row.retired_at).toBe(count === settings.failed_recovery_checks_before_retirement ? row.checked_at : null);
    }
    expect(lifecycle).toMatchObject({ availability: "retired", retirement_reason: "confirmed-recovery-failures", rest_until: null });
  } finally { await fixture.close(); }
});

test("recorded transport failure counts for first-use rest but not confirmed retirement", async () => {
  const fixture = await recordedPlan();
  try {
    const source = fixture.inputs.harvest.sources[0]!;
    fixture.transport.recordings.responses[source.url] = [{ error: "ECONNRESET" }];
    const fetcher = createPermittedFetcher(fixture.inputs.harvest.config.harvest, fixture.inputs.harvest.extraction, fixture.runtime.boundary);
    const fetched = await fetcher.fetch(source.url);
    expect(fetched.failure).toBe("network");
    const lifecycle = applyFeedCheck(createUnknownFeedLifecycle(), {
      check_request_id: randomUUID(), check_result: classifyFeedFetchFailure(fetched),
      checked_at: "2026-10-21T00:00:00Z", status: fetched.http_status,
    }, fixture.inputs.harvest.config.availability);
    expect(lifecycle).toMatchObject({ strikes: 1, availability_complete: false,
      first_confirmed_failure_at: null, failed_recovery_checks: null, retired_at: null });
  } finally { await fixture.close(); }
});
