import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  FeedAvailabilityEnrollmentSchema,
  FeedAvailabilityStateSchema,
} from "../src/index";

test("durable availability state and its permanent enrollment marker use the stamped contracts", async () => {
  const root = resolve(import.meta.dir, "../../../tests/fixtures/contracts/feed-availability-state");
  const [stateText, enrollmentText] = await Promise.all([
    readFile(resolve(root, "one-enrolled-feed.json"), "utf8"),
    readFile(resolve(root, "initial-enrollment.json"), "utf8"),
  ]);
  const state = FeedAvailabilityStateSchema.parse(JSON.parse(stateText));
  const enrollment = FeedAvailabilityEnrollmentSchema.parse(JSON.parse(enrollmentText));
  expect(state.version).toBe("2026-10-30");
  expect(state.feeds[0]?.reservation?.status).toBe("unknown");
  expect(enrollment.initial_feed_ids).toEqual(["abc-feed"]);
});

test("availability state refuses duplicate feeds, unsorted feeds and retired reservations", () => {
  const base = {
    version: "2026-10-30",
    changelog: [{ version: "2026-10-30", change: "A stamped change." }],
    sequence: 0,
    updated_at: "2026-10-30T12:00:00Z",
    feeds: [{
      feed_id: "abc-feed",
      endpoint_key: "a".repeat(64),
      consecutive_failed_checks: 0,
      rest_until: null,
      retired_at: null,
      episode: null,
      reservation: null,
      last_completion: null,
      operator_enrollment_id: null,
    }],
  };
  expect(FeedAvailabilityStateSchema.safeParse({ ...base, feeds: [base.feeds[0], base.feeds[0]] }).success).toBe(false);
  expect(FeedAvailabilityStateSchema.safeParse({
    ...base,
    feeds: [{
      ...base.feeds[0],
      retired_at: "2026-10-30T12:00:00Z",
      reservation: {
        request_id: "7251dc83-a947-4333-a885-7b6fc84fcb49",
        run_id: "2026-10-30-1",
        attempt: 1,
        reserved_at: "2026-10-30T12:00:00Z",
        phase: "parse",
        status: "unknown",
      },
    }],
  }).success).toBe(false);
});
