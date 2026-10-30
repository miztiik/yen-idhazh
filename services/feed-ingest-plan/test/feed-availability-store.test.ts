/** Exercise durable reservations and completion through a generated local Git remote. */
import { randomUUID } from "node:crypto";
import { expect, test } from "bun:test";
import { PlanError } from "../src/api/plan-request";
import { completeFeedCheck, readFeedAvailability, reserveFeedCheck } from "../src/availability/feed-availability";
import { recordedPlan } from "./plan-recordings";

test("one concurrent reservation wins, its completion survives a fresh planner object", async () => {
  const recorded = await recordedPlan();
  try {
    const source = recorded.inputs.harvest.sources.find(value => value.status === "active")!;
    const at = recorded.runtime.observation_clock!().toISOString();
    const requests = [randomUUID(), randomUUID()].map(request_id => ({
      request_id, run_id: "2026-10-21-700", attempt: 1,
    }));
    const outcomes = await Promise.allSettled(requests.map(request =>
      reserveFeedCheck(recorded.inputs, source, request, at)));
    const winners = outcomes.flatMap((outcome, index) => outcome.status === "fulfilled" ? [requests[index]!] : []);
    const refusals = outcomes.filter((outcome): outcome is PromiseRejectedResult => outcome.status === "rejected");
    expect(winners).toHaveLength(1);
    expect(refusals).toHaveLength(1);
    expect(refusals[0]!.reason).toBeInstanceOf(PlanError);
    expect((refusals[0]!.reason as PlanError).code).toBe("FEED_CHECK_BUSY");

    await completeFeedCheck(recorded.inputs, source, {
      ...winners[0]!, completed_at: at, result: "timeout", http_status: null,
    });
    const restartedInputs = { ...recorded.inputs };
    const snapshot = await readFeedAvailability(restartedInputs, at);
    expect(snapshot.feeds.find(feed => feed.feed_id === source.id)?.status).toBe("eligible");
  } finally { await recorded.close(); }
}, 120000);
