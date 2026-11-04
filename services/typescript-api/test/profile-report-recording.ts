/** What does the actual machine API's default reporter emit after a successful recorded profile? */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig as loadFingerprintConfig, loadSettings } from "@idhazh/host-fingerprints/config";
import { START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "@idhazh/host-probes/api";
import { loadConfig as loadProbeConfig } from "@idhazh/host-probes/config";
import { parseProcessStat } from "../../host-probes/src/task-profile/process-stat";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../../host-probes/src/api/task-command-schema";
import { serveApiApp } from "../src/create-api-app";
import { loadHonoSettings } from "../src/load-settings";

async function recordProfileReport() {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const directory = await mkdtemp(join(tmpdir(), "api-profile-report-"));
  let server: Awaited<ReturnType<typeof serveApiApp>> | undefined;
  try {
    const config = await loadProbeConfig(join(root, "config", "host-probes.json"));
    config.task_profile.enabled = true;
    const recorded = await Bun.file(join(root, "tests", "fixtures", "host-probes", "process-inputs.json")).json();
    const stat = recorded.stat.replace("4242 ", `${process.pid} `);
    await mkdir(join(directory, String(process.pid)));
    await writeFile(join(directory, String(process.pid), "stat"), stat);
    const pin = parseProcessStat(process.pid, stat);
    if (pin.reason !== null) throw new Error("The named process recording must contain its PID pin");
    const listener = await loadHonoSettings(root);
    const reservation = Bun.serve({ hostname: listener.hostname, port: 0, fetch: () => new Response() });
    const port = reservation.port!;
    await reservation.stop(true);
    server = await serveApiApp({ ...listener, port }, {
      identity: { event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid,
        port, group: "machine", modules: ["machine"], enabled: true },
      fingerprint: {
        config: await loadFingerprintConfig(join(root, "config", "host-fingerprints.json")),
        settings: await loadSettings(join(root, "config", "idhazh.json")),
        options: { outputRoot: join(directory, "state"), registryPath: join(root, "config", "ledgers.json") },
      },
      probes: { config, context: { platform: "linux", procRoot: directory } },
    });
    const origin = `http://${listener.hostname === "::1" ? "[::1]" : listener.hostname}:${port}`;
    const post = (path: string, body: unknown) => fetch(new URL(path, origin), {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const start = await post(START_TASK_PROFILE_PATH, {
      identity: { pipeline_name: "recorded-work", task_name: "profile-report-regression", run_id: "recorded-run" },
      target: { pid: process.pid, start_ticks: pin.value.start_ticks },
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
  } finally { await server?.stop(true); await rm(directory, { recursive: true, force: true }); }
}

if (import.meta.main) await recordProfileReport();
