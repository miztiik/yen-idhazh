/** First-use failures enter real timed recovery without fabricating successful history. */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { FeedHealthStateRowContract } from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { readPlannerParquet } from "@idhazh/ledger-file-writer";
import { recordedPlan } from "./plan-recordings";
import { runFeedPlan } from "../src/run-feed-plan";
import { fixtureGit } from "./publication-recordings";

test("fresh HTTP runs reload observed partial failure counts through rest and confirmed recovery retirement", async () => {
  const fixture = await recordedPlan();
  const settings = fixture.inputs.harvest.config.availability;
  const source = fixture.inputs.harvest.sources[0]!;
  fixture.transport.recordings.responses[source.url] = [{ status: 503, body: "Recorded unavailable feed" }];
  let latest: { day: string; raw_files: string[] }[] = [];
  let run = 900;
  let last: FeedHealthStateRow | undefined;
  const initialHead = await fixtureGit(fixture.directory, ["rev-parse", "HEAD"]);
  const initial = Date.parse("2026-10-21T00:00:00.000Z");
  async function attempt(hours: number) {
    const now = new Date(initial + hours * 3_600_000);
    const inputs = { ...fixture.inputs, settings: { ...fixture.inputs.settings, inputs: {
      ...fixture.inputs.settings.inputs, feed_health_days: latest,
    } } };
    const result = await runFeedPlan({}, inputs, {
      ...fixture.runtime, run_number: String(run++), clock: () => now, observation_clock: () => now,
    });
    expect(result.row.status).toBe("completed");
    const files = result.files.feed_health_state!.files;
    const read = await readPlannerParquet(join(inputs.outputRoot, files[0]!.path), "feed-health-state", FeedHealthStateRowContract);
    latest = [{ day: read.rows[0]!.date, raw_files: files.map(file => `state/${file.path}`) }];
    last = read.rows[0]!;
    return last;
  }
  try {
    for (let count = 1; count <= settings.consecutive_failed_checks_before_rest; count++) {
      const row = await attempt(count - 1);
      expect(row).toMatchObject({
        strikes: count, check_result: "confirmed-http-failure", availability_complete: false,
        first_confirmed_failure_at: new Date(initial).toISOString().replace(".000Z", "Z"), failed_recovery_checks: 0,
      });
      expect(row.availability).toBe(count < settings.consecutive_failed_checks_before_rest ? "eligible" : "resting");
    }
    const deadline = settings.consecutive_failed_checks_before_rest - 1 + settings.rest_hours;
    expect(last!.rest_until).toBe(new Date(initial + deadline * 3_600_000).toISOString());
    const requests = fixture.transport.requests.length;
    const skipped = await attempt(deadline - 1);
    expect(skipped).toMatchObject({ check_request_id: null, check_result: null, checked_at: null,
      strikes: settings.consecutive_failed_checks_before_rest, feed_requests: 0, availability_complete: false });
    expect(fixture.transport.requests.length).toBe(requests);
    for (let count = 1; count <= settings.failed_recovery_checks_before_retirement; count++) {
      const row = await attempt(deadline + (count - 1) * settings.recovery_rest_hours);
      expect(row.failed_recovery_checks).toBe(count);
      expect(row.availability_complete).toBe(false);
      expect(row.retired_at).toBe(count === settings.failed_recovery_checks_before_retirement ? row.checked_at : null);
    }
    expect(last).toMatchObject({ availability: "retired", retirement_reason: "confirmed-recovery-failures", rest_until: null });
    expect(await fixtureGit(fixture.directory, ["rev-parse", "HEAD"])).toBe(initialHead);
  } finally { await fixture.close(); }
}, 120_000);

test("real recorded transport failures count for first-use rest without qualifying as confirmed retirement", async () => {
  const fixture = await recordedPlan();
  fixture.transport.recordings.responses[fixture.inputs.harvest.sources[0]!.url] = [{ error: "ECONNRESET" }];
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    const actual = await readPlannerParquet(join(fixture.inputs.outputRoot, result.files.feed_health_state!.files[0]!.path),
      "feed-health-state", FeedHealthStateRowContract);
    expect(actual.rows[0]).toMatchObject({ check_result: "transport-unknown", strikes: 1,
      availability_complete: false, first_confirmed_failure_at: null, failed_recovery_checks: null, retired_at: null });
  } finally { await fixture.close(); }
}, 120_000);
