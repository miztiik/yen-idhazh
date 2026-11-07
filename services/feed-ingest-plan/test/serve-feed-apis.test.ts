/** Does the planning-only listener retain native source operations and close its owned resources? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { createRootContext, DELIVERY_API_PATHS, PLANNER_API_PATHS, PLANNER_API_PREFIX, PlannerSavedResponseSchema, writeTraceContext } from "@idhazh/common-contracts";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { SAMPLE_PATH } from "@idhazh/host-probes/api";
import { recordedPlan } from "./plan-recordings";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { operationLink } from "../src/api/operation-context";
import { PlannerReadySchema } from "../src/config/planner-startup";
import { API_HEALTH_PATH, ApiReadySchema } from "@idhazh/serve-pipeline-apis/startup";
import { serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import { readApiReadiness } from "@idhazh/serve-pipeline-apis/readiness";
import { createFeedApiApp } from "../scripts/create-feed-api-app";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import { PlanError } from "../src/api/plan-request";
import { FeedApiStartupSchema } from "../scripts/read-feed-api-startup";
import { readFeedApiReadiness } from "../scripts/read-feed-api-readiness";
import { captureFeedApiFailure } from "../scripts/capture-feed-api-failure";

const json = (body: unknown, carrier = {}) => ({
  method: "POST", headers: { "content-type": "application/json", ...carrier }, body: JSON.stringify(body),
});

async function listenerSettings() {
  const config = await loadHonoSettings(fileURLToPath(new URL("../../../", import.meta.url)), "planning");
  const reservation = Bun.serve({ hostname: config.hostname, port: 0, fetch: () => new Response() });
  const port = reservation.port!;
  await reservation.stop(true);
  return { ...config, port };
}

test("the actual planning listener returns fetch and parse results without machine routes", async () => {
  const recorded = await recordedPlan();
  const settings = await listenerSettings();
  const parent = createRootContext();
  const identity = ApiReadySchema.parse({
    event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid, port: settings.port,
    group: "planning", modules: ["planning"], enabled: true,
  });
  const plannerIdentity = PlannerReadySchema.parse({
    event: "planner_ready", nonce: identity.nonce, pid: process.pid, port: settings.port,
    runtime: { ...parent, git_sha: recorded.runtime.git_sha, run_number: "700",
      attempt: 1, captured_at: "2026-10-21T23:59:59Z" },
  });
  const server = await serveApiApp(settings, createFeedApiApp({
    identity,
    planner: { inputs: recorded.inputs, runtime: recorded.runtime, identity: plannerIdentity },
  }));
  const origin = `http://${settings.hostname}:${server.port}`;
  let unrelatedRequests = 0;
  const unrelated = Bun.serve({ hostname: settings.hostname, port: 0, fetch() {
    unrelatedRequests++;
    return Response.json({ code: "UNRELATED_LISTENER" }, { status: 400 });
  } });
  try {
    expect(await (await fetch(`${origin}${API_HEALTH_PATH}`)).json()).toEqual({ identity });
    const readiness = {
      server: settings, context: parent, kind: "TYPESCRIPT_API" as const,
      signal: AbortSignal.timeout(settings.supervision.readiness_timeout_ms),
      failure: { create: (code: string, message: string) => new PlanError(code, message) },
    };
    expect(await readApiReadiness({ ...readiness, message: identity, expected: identity })).toEqual({ origin, identity });
    const startup = FeedApiStartupSchema.parse({
      group: "planning", server: settings, directory: "evidence",
      run: { run_id: "700", attempt: 1, started_at: plannerIdentity.runtime.captured_at, context: parent },
      planner: {
        nonce: identity.nonce, settings: recorded.inputs.settings, planning: recorded.inputs.harvest.config,
        output_root: "state", runtime: plannerIdentity.runtime,
      },
    });
    if (startup.group !== "planning") throw new Error("The native planner readiness test requires planning startup");
    const nativeReadiness = {
      message: identity, pid: process.pid, startup, kind: "PLANNER" as const,
      signal: readiness.signal, failure: captureFeedApiFailure({ operation: "workflow" }),
    };
    expect(await readFeedApiReadiness(nativeReadiness)).toEqual({ origin, identity });
    for (const runtime of [
      { ...startup.planner.runtime, run_number: "701" },
      { ...startup.planner.runtime, attempt: 2 },
      { ...startup.planner.runtime, captured_at: "2026-10-22T00:00:00Z" },
      { ...startup.planner.runtime, git_sha: "b".repeat(40) },
      { ...startup.planner.runtime, ...createRootContext() },
    ]) {
      const wrong = FeedApiStartupSchema.parse({ ...startup, planner: { ...startup.planner, runtime } });
      await expect(readFeedApiReadiness({ ...nativeReadiness, startup: wrong }))
        .rejects.toMatchObject({ code: "PLANNER_READY_IDENTITY" });
    }
    recorded.inputs.settings.enabled = false;
    try {
      await expect(readFeedApiReadiness(nativeReadiness)).rejects.toMatchObject({ code: "PLANNER_READY_IDENTITY" });
    } finally { recorded.inputs.settings.enabled = true; }
    for (const overrides of [
      { nonce: randomUUID() }, { pid: identity.pid + 1 },
      { port: identity.port === 65535 ? identity.port - 1 : identity.port + 1 },
      { group: "delivery", modules: ["delivery"] }, { enabled: false },
    ]) {
      const wrong = ApiReadySchema.parse({ ...identity, ...overrides });
      await expect(readApiReadiness({ ...readiness, message: wrong, expected: wrong }))
        .rejects.toMatchObject({ code: "TYPESCRIPT_API_READY_IDENTITY" });
      await expect(readFeedApiReadiness({ ...nativeReadiness, message: wrong }))
        .rejects.toMatchObject({ code: "PLANNER_READY_IDENTITY" });
    }
    expect(ApiReadySchema.safeParse({ ...identity, modules: ["machine"] }).success).toBe(false);
    expect(ApiReadySchema.safeParse({ ...identity, modules: ["planning", "machine"] }).success).toBe(false);
    expect((await fetch(`${origin}/health`)).status).toBe(404);
    expect((await fetch(`${origin}${PLANNER_API_PREFIX}/health`)).status).toBe(404);
    expect((await fetch(`${origin}${PLANNER_API_PREFIX}${DELIVERY_API_PATHS.health}`)).status).toBe(404);
    expect((await fetch(`${origin}${FINGERPRINT_PATH}`, json({}))).status).toBe(404);
    expect((await fetch(`${origin}${SAMPLE_PATH}`)).status).toBe(404);
    const source = recorded.inputs.harvest.sources[0]!;
    const response = await fetch(`${origin}${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`, json({
      feed_id: source.id, fetch_item_type: "feed",
    }, writeTraceContext(parent)));
    expect(response.status).toBe(200);
    const fetched = FetchResponseSchema.parse(await response.json());
    expect(fetched.failure).toBeNull();
    expect(fetched.traceId).toBe(parent.traceId);
    const parsedResponse = await fetch(`${origin}${PLANNER_API_PREFIX}${PLANNER_API_PATHS.parse}`, json({
      links: [operationLink(fetched)],
    }, writeTraceContext(parent)));
    expect(parsedResponse.status).toBe(200);
    const parsed = ParseResponseSchema.parse(await parsedResponse.json());
    expect(parsed.failure).toBeNull();
    expect(parsed.parsed_count).toBeGreaterThan(0);
    expect(parsed.traceId).toBe(parent.traceId);
    expect(parsed.links).toEqual([operationLink(fetched)]);
    expect(fetched).not.toHaveProperty("body");
    expect(parsed).not.toHaveProperty("body");
    expect(recorded.transport.requests.map(request => request.url.href)).toEqual([source.url]);
    const planning = await fetch(`${origin}${PLANNER_API_PREFIX}${PLANNER_API_PATHS.plan}`, json({}, {
      host: `${settings.hostname}:${unrelated.port}`,
    }));
    const planned = PlannerSavedResponseSchema.parse(await planning.json());
    expect(planned).toHaveProperty("planning_complete");
    expect(unrelatedRequests).toBe(0);
  } finally {
    await server.stop();
    await server.stop();
    await unrelated.stop(true);
    const replacement = Bun.serve({ hostname: settings.hostname, port: settings.port, fetch: () => new Response() });
    await replacement.stop(true);
    await recorded.close();
  }
});

test("readiness cannot advertise missing native modules", async () => {
  const settings = await listenerSettings();
  expect(() => createFeedApiApp({ identity: {
    event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid, port: settings.port,
    group: "machine", modules: ["machine"], enabled: true,
  } })).toThrow("actual enabled API modules");
});
