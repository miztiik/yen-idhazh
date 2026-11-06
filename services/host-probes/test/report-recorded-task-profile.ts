/** What does the actual machine API's default reporter emit after a successful recorded profile? */
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "@idhazh/host-probes/api";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../src/api/task-command-schema";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import { serveRecordedMachine } from "./serve-recorded-machine-api";

async function recordProfileReport() {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const listener = await loadHonoSettings(root);
  const reservation = Bun.serve({ hostname: listener.hostname, port: 0, fetch: () => new Response() });
  const port = reservation.port!;
  await reservation.stop(true);
  const server = await serveRecordedMachine(root, { ...listener, port });
  try {
    const origin = `http://${listener.hostname === "::1" ? "[::1]" : listener.hostname}:${port}`;
    const post = (path: string, body: unknown) => fetch(new URL(path, origin), {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const start = await post(START_TASK_PROFILE_PATH, {
      identity: { pipeline_name: "recorded-work", task_name: "profile-report-regression", run_id: "recorded-run" },
      target: server.target,
    });
    assert.equal(start.status, 200);
    const started = StartTaskProfileResponseSchema.parse(await start.json());
    assert.equal(started.status, "started");
    if (started.status !== "started") throw new Error("The configured profile must start its real collector");
    const stop = await post(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "success" });
    assert.equal(stop.status, 200);
    const stopped = StopTaskProfileResponseSchema.parse(await stop.json());
    assert.equal(stopped.status, "stopped");
    if (stopped.status !== "stopped") throw new Error("The configured profile must return its actual completed result");
    assert.equal(stopped.profile.outcome, "success");
    console.log(JSON.stringify({ native_http_status: stop.status, result: stopped.status, task_outcome: stopped.profile.outcome }));
  } finally { await server.stop(true); }
}

if (import.meta.main) await recordProfileReport();
