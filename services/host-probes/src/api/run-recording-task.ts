/** Run one workflow command once, inside the owned machine listener's lifetime when available. */
import { randomUUID } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { join, relative } from "node:path";
import { createRootContext } from "@idhazh/common-contracts";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import { loadConfig, TaskPerformanceExecutionSchema } from "../config";
import { superviseMachineApiTask } from "./supervise-machine-api-task";

async function run() {
  const [days, runId, attempt, pipeline, shard, gitSha, memory, ...command] = Bun.argv.slice(2);
  if (command.length === 0) throw new Error("A trusted workflow command is required");
  const root = process.cwd();
  const env: NodeJS.ProcessEnv = { ...process.env };
  delete env.IDHAZH_MACHINE_API_ORIGIN;
  delete env.IDHAZH_MACHINE_API_STATE_ROOT;
  const legacy = env.IDHAZH_MACHINE_LEGACY_OPENING_WRITER;
  delete env.IDHAZH_MACHINE_LEGACY_OPENING_WRITER;
  const cancellation = new AbortController();
  let signalChild: ((signal: NodeJS.Signals) => void) | undefined;
  let commandExit: Promise<number> | undefined;
  const interrupt = () => {
    if (signalChild === undefined) cancellation.abort(new Error("Workflow cancelled before work started"));
    else signalChild("SIGINT");
  };
  const terminate = () => {
    if (signalChild === undefined) cancellation.abort(new Error("Workflow stopped before work started"));
    else signalChild("SIGTERM");
  };
  process.on("SIGINT", interrupt);
  process.on("SIGTERM", terminate);
  const execute = (settings: Record<string, string> = {}) => {
    if (commandExit !== undefined) throw new Error("The workflow command already started");
    const owned = Bun.spawn(command, {
      cwd: root, env: { ...env, ...settings }, stdin: "inherit", stdout: "inherit", stderr: "inherit",
    });
    signalChild = signal => { if (owned.exitCode === null) owned.kill(signal); };
    commandExit = owned.exited.then(code => {
      if (owned.signalCode === "SIGINT") return 130;
      if (owned.signalCode === "SIGTERM") return 143;
      return code;
    });
    return commandExit;
  };
  const warn = (stage: string, error: unknown) => {
    const code = error instanceof Error && "code" in error && typeof error.code === "string"
      && /^[A-Z0-9_]+$/.test(error.code) ? error.code : "MACHINE_RECORDING_UNAVAILABLE";
    console.error(`::warning title=Task Performance::${stage}: ${code}`);
  };
  let privateDir: string | undefined;
  try {
    const task_performance = TaskPerformanceExecutionSchema.parse({
      run_id: runId, attempt: Number(attempt), pipeline_name: pipeline, shard: Number(shard),
      git_sha: gitSha, accounting_days: days?.split(","),
      ...(env.GITHUB_JOB === undefined ? {} : { runner_job: env.GITHUB_JOB }),
      ...(legacy === undefined ? {} : { legacy_opening_writer: JSON.parse(legacy) }),
    });
    if (memory !== "on" && memory !== "off") throw new Error("Invalid resolved memory selection");
    const [server, probes] = await Promise.all([
      loadHonoSettings(root, "machine"), loadConfig(join(root, "config", "host-probes.json")),
    ]);
    privateDir = await mkdtemp(join(root, "backend", "var", "machine-task-"));
    const directory = relative(root, privateDir).replaceAll("\\", "/");
    const state_root = `${directory}/state`;
    return await superviseMachineApiTask({
      root, signal: cancellation.signal,
      startup: {
        group: "machine", nonce: randomUUID(), server, directory, state_root, task_performance,
        task_profile_memory_enabled: memory === "on",
        run: {
          run_id: process.env.GITHUB_RUN_ID ?? task_performance.run_id, attempt: task_performance.attempt,
          started_at: new Date().toISOString(), context: createRootContext(),
        },
      },
      request: origin => execute({
        IDHAZH_MACHINE_API_ORIGIN: origin,
        IDHAZH_MACHINE_API_STATE_ROOT: state_root,
        IDHAZH_MACHINE_API_TIMEOUT_MS: String(Math.max(
          server.supervision.readiness_timeout_ms, probes.task_profile.lifecycle_timeout_ms,
        )),
        IDHAZH_MACHINE_API_MAX_RESPONSE_BYTES: String(
          probes.max_request_body_bytes * (probes.task_profile.max_retained_samples + 1),
        ),
      }),
    });
  } catch (error) {
    warn(commandExit === undefined ? "listener unavailable before work" : "listener failed after work started", error);
    if (cancellation.signal.aborted && commandExit === undefined) return 130;
    return commandExit === undefined ? await execute() : await commandExit;
  } finally {
    process.off("SIGINT", interrupt);
    process.off("SIGTERM", terminate);
    if (privateDir !== undefined) {
      try { await rm(privateDir, { recursive: true }); }
      catch (error) { warn("private state cleanup failed", error); }
    }
  }
}

if (import.meta.main) process.exitCode = await run();
