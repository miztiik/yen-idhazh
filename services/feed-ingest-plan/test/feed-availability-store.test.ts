/** Exercise durable reservations and completion through a generated local Git remote. */
import { randomUUID } from "node:crypto";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test } from "bun:test";
import { compare_and_swap_data, read_git_data } from "@idhazh/data-delivery";
import { FeedAvailabilityStateSchema } from "@idhazh/common-contracts";
import { PlanError } from "../src/api/plan-request";
import { completeFeedCheck, readFeedAvailability, reserveFeedCheck } from "../src/availability/feed-availability";
import { recordedPlan } from "./plan-recordings";

async function git(directory: string, args: string[]) {
  const environment: Record<string, string | undefined> = { ...process.env };
  for (const key of ["GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE"]) delete environment[key];
  environment.GIT_AUTHOR_NAME = "Availability test";
  environment.GIT_AUTHOR_EMAIL = "availability@example.test";
  environment.GIT_COMMITTER_NAME = "Availability test";
  environment.GIT_COMMITTER_EMAIL = "availability@example.test";
  const child = Bun.spawn(["git", ...args], { cwd: directory, env: environment, stdout: "pipe", stderr: "pipe" });
  const [stdout, stderr, status] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  if (status !== 0) throw new Error(`Generated availability repository refused ${args[0]}: ${stderr}`);
  return stdout.trim();
}

async function replaceAvailabilityFile(inputs: Awaited<ReturnType<typeof recordedPlan>>["inputs"],
  relativePath: string, bytes: Uint8Array, expectedRevision: string) {
  const directory = await mkdtemp(join(tmpdir(), "availability-edit-"));
  try {
    await mkdir(join(directory, "completed"));
    await writeFile(join(directory, "completed", "state.json"), bytes);
    return await compare_and_swap_data({
      sourceRoot: directory, destination: { kind: "git", repository: inputs.root },
      expected_revision: expectedRevision, max_bytes: inputs.availability.max_state_bytes,
      files: [{ sourcePath: "completed/state.json", targetPath: relativePath,
        sha256: createHash("sha256").update(bytes).digest("hex") }],
      permittedPaths: ["state/raw/planner/feed-availability"],
      committer: inputs.availabilityCommitter, message: "Prepare availability state test",
    });
  } finally { await rm(directory, { recursive: true, force: true }); }
}

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

    const firstCompletion = {
      ...winners[0]!, completed_at: at, result: "timeout", http_status: null,
    } as const;
    await completeFeedCheck(recorded.inputs, source, firstCompletion);
    await completeFeedCheck(recorded.inputs, source, firstCompletion);
    await expect(completeFeedCheck(recorded.inputs, source, {
      ...firstCompletion, result: "confirmed-http-failure", http_status: 404,
    })).rejects.toMatchObject({ code: "REQUEST_CONFLICT" });

    const next = { request_id: randomUUID(), run_id: "2026-10-21-701", attempt: 1 };
    await reserveFeedCheck(recorded.inputs, source, next, at);
    await expect(completeFeedCheck(recorded.inputs, source, firstCompletion))
      .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    await completeFeedCheck(recorded.inputs, source, {
      ...next, completed_at: at, result: "timeout", http_status: null,
    });

    const restartRoot = join(recorded.directory, "availability-restart");
    await git(recorded.directory, ["clone", "--quiet", join(recorded.directory, "availability-origin.git"), restartRoot]);
    const restartedInputs = { ...recorded.inputs, root: restartRoot };
    const snapshot = await readFeedAvailability(restartedInputs, at);
    expect(snapshot.feeds.find(feed => feed.feed_id === source.id)?.status).toBe("eligible");

    const paths = [recorded.inputs.availability.state_path, recorded.inputs.availability.enrollment_path];
    const saved = await read_git_data({ repository: restartRoot, max_bytes: recorded.inputs.availability.max_state_bytes,
      paths: paths.map(path => ({ path })) });
    const state = FeedAvailabilityStateSchema.parse(JSON.parse(
      Buffer.from(saved.files[0]!.content!, "base64").toString("utf8"),
    ));
    const retired = state.feeds.find(feed => feed.feed_id === source.id)!;
    retired.retired_at = at;
    retired.rest_until = null;
    retired.reservation = null;
    const retiredBytes = new TextEncoder().encode(`${JSON.stringify(FeedAvailabilityStateSchema.parse(state))}\n`);
    const retirement = await replaceAvailabilityFile(recorded.inputs, paths[0]!, retiredBytes, saved.revision);
    expect(retirement.status).toBe("published");
    const retiredView = await readFeedAvailability(restartedInputs, at);
    expect(retiredView.feeds.find(feed => feed.feed_id === source.id)?.status).toBe("retired");

    recorded.inputs.availability.operator_enrollments = [{
      feed_id: source.id, enrollment_id: randomUUID(),
    }];
    const reenrolled = await readFeedAvailability(restartedInputs, at);
    expect(reenrolled.feeds.find(feed => feed.feed_id === source.id)).toMatchObject({
      status: "eligible", consecutive_failed_checks: 0, retired_at: null, first_confirmed_failure_at: null,
    });

    await git(restartRoot, ["fetch", "--quiet", "origin", "refs/heads/main"]);
    await git(restartRoot, ["reset", "--hard", "FETCH_HEAD"]);
    await git(restartRoot, ["rm", "--", ...paths]);
    await git(restartRoot, ["commit", "--quiet", "-m", "Remove established availability state"]);
    await git(restartRoot, ["push", "--quiet", "origin", "HEAD:refs/heads/main"]);
    await expect(readFeedAvailability(restartedInputs, at)).rejects.toMatchObject({
      code: "FEED_AVAILABILITY_STATE_INVALID",
    });
  } finally { await recorded.close(); }
}, 120000);
