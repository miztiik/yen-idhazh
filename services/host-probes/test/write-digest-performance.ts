/** Feed the ordinary publisher exact receipts from the native in-memory handlers. */
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { loadConfig, loadTaskPerformanceSettings, TaskPerformanceExecutionSchema } from "../src/config";
import {
  createSampleHandler, RECORD_TASK_PERFORMANCE_PATH, RecordTaskPerformanceResponseSchema,
  RecordTaskPerformanceRequestSchema, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
} from "../src/api/server";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../src/api/task-command-schema";
import { summarizeClosedTaskProfile } from "../src/task-profile/summarize-closed-profile";

const input = z.strictObject({
  private_root: z.string(), execution: TaskPerformanceExecutionSchema,
  serving: RecordTaskPerformanceRequestSchema.shape.measurement,
  profile_reply: z.string(),
  host_unit_id: z.uuid().nullable(),
}).parse(JSON.parse(await Bun.stdin.text()));
const { accounting_days, run_id, attempt, pipeline_name, shard, git_sha } = input.execution;
const writer = { run_id, attempt, pipeline_name, shard, git_sha };
const [day] = accounting_days;
if (day === undefined) throw new Error("The recording requires a day");
const probes = await loadConfig();
const procRoot = join(input.private_root, "proc");
const pid = process.pid;
const worker = join(procRoot, String(pid));
await mkdir(worker, { recursive: true });
const stat = (cpu: number) => {
  const cells = Array.from({ length: 20 }, () => "0");
  cells[0] = "R"; cells[11] = String(cpu); cells[19] = "42";
  return `${pid} (digest test) ${cells.join(" ")}\n`;
};
await Bun.write(join(worker, "stat"), stat(2));
await Bun.write(join(procRoot, "stat"), "cpu 2 0 2 2 0 0 0 0 0 0\n");
const handler = createSampleHandler(probes, { platform: "linux", procRoot }, undefined, undefined, {
  outputRoot: input.private_root, execution: input.execution,
  settings: await loadTaskPerformanceSettings(),
});
async function call<T>(path: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
  const reply = await handler(new Request(`http://localhost${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }));
  if (!reply.ok) throw new Error(`Native ${path} returned ${reply.status}: ${await reply.text()}`);
  return schema.parse(await reply.json());
}
try {
  const identity = { pipeline_name: writer.pipeline_name, task_name: "work", run_id: writer.run_id };
  const opened = await call(START_TASK_PROFILE_PATH, {
    identity, target: { pid, start_ticks: "42" },
  }, StartTaskProfileResponseSchema);
  if (opened.status !== "started") throw new Error("The native collector did not open");
  await Bun.write(join(worker, "stat"), stat(5));
  await Bun.write(join(procRoot, "stat"), "cpu 5 0 5 5 0 0 0 0 0 0\n");
  const closed = await call(STOP_TASK_PROFILE_PATH, { handle: opened.handle, outcome: "success" },
    StopTaskProfileResponseSchema);
  if (closed.status !== "stopped") throw new Error("The native collector did not close");
  await Bun.write(input.profile_reply, JSON.stringify(closed));
  const rows = [
    ["work", { task_kind: "workflow-task", ...summarizeClosedTaskProfile(closed.profile) }],
    ["serve-summarizer", input.serving],
  ] as const;
  for (const [task_name, measurement] of rows) {
    const written = await call(RECORD_TASK_PERFORMANCE_PATH, {
      date: day, writer: { ...writer, task_name },
      measurement: { ...measurement, host_unit_id: input.host_unit_id },
    }, RecordTaskPerformanceResponseSchema);
    if (written.status !== "written") throw new Error("The native recorder did not write");
    console.log(JSON.stringify(written));
  }
} finally {
  await handler.close();
}
