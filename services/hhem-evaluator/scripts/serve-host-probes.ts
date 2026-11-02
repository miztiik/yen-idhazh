/** How does the existing host server follow one private caller's lifetime? */
import { z } from "../../host-probes/node_modules/zod";
import { loadConfig } from "../../host-probes/src/config";
import { serveSamples } from "../../host-probes/src/api/server";

const startupSchema = z.strictObject({
  version: z.literal("2026-11-02"), startup_id: z.uuidv4(),
  context: z.strictObject({
    run_id: z.string().nullable(), pipeline_name: z.string().nullable(), task_name: z.string().nullable(),
  }),
});
const manualSchema = z.object({ control_max_bytes: z.int().positive() });
const manual = manualSchema.parse(await Bun.file(
  new URL("../../../config/hhem-evaluator/workflow.json", import.meta.url),
).json());
let startup: z.infer<typeof startupSchema> | undefined;
let service: ReturnType<typeof serveSamples> | undefined;
let closing: Promise<void> | undefined;
let deadline: ReturnType<typeof setTimeout> | undefined;
let lifecycleMs: number | undefined;

function emit(packet: object): void {
  process.stdout.write(JSON.stringify(packet) + "\n");
}

function stop(): Promise<void> {
  closing ??= (async () => {
    let clean = true;
    if (lifecycleMs !== undefined) deadline = setTimeout(() => process.exit(1), lifecycleMs);
    try { await service?.stop(true); }
    catch { clean = false; process.exitCode = 1; }
    finally { clearTimeout(deadline); }
    if (startup !== undefined) emit({
      version: startup.version, kind: "stopped", service: "host", startup_id: startup.startup_id,
      pid: process.pid, clean, worker_exit_confirmed: null,
    });
    process.stdin.destroy();
  })();
  return closing;
}

process.once("SIGTERM", () => { void stop(); });
process.once("SIGINT", () => { void stop(); });

try {
  let first = Buffer.alloc(0);
  for await (const chunk of process.stdin) {
    if (startup !== undefined) throw new Error("Unexpected private control data");
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    if (first.length + bytes.length > manual.control_max_bytes) throw new Error("Startup packet too large");
    first = Buffer.concat([first, bytes]);
    const newline = first.indexOf("\n");
    if (newline < 0) continue;
    if (newline !== first.length - 1) throw new Error("Unexpected private control data");
    startup = startupSchema.parse(JSON.parse(first.toString("utf8")));
    first = Buffer.alloc(0);
    const config = await loadConfig(new URL(
      "../../../config/hhem-evaluator/host-probes.json", import.meta.url,
    ));
    lifecycleMs = Math.max(config.task_profile.lifecycle_timeout_ms, config.cache_probe.lifecycle_timeout_ms);
    service = serveSamples(config);
    emit({
      version: startup.version, kind: "ready", service: "host",
      startup_id: startup.startup_id, pid: process.pid,
      host: config.listen_host, port: config.listen_port, lifecycle_timeout_ms: lifecycleMs,
    });
  }
  await stop();
} catch {
  if (startup !== undefined) emit({
    version: startup.version, kind: "failed", service: "host",
    startup_id: startup.startup_id, pid: process.pid,
  });
  process.exitCode = 1;
  await stop();
}
