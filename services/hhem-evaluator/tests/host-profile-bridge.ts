/** How do offline Python cases call the actual native host handler without a listener? */
import { z } from "../../host-probes/node_modules/zod";
import { createInterface } from "node:readline";
import { loadConfig, ProbeConfigSchema } from "../../host-probes/src/config";
import {
  createSampleHandler, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
} from "../../host-probes/src/api/server";
import {
  StartTaskProfileResponseSchema, StopTaskProfileResponseSchema,
} from "../../host-probes/src/api/task-command-schema";
import { TaskProfileSchema } from "../../host-probes/src/task-profile/profile-schema";
import type { TaskProfile } from "../../host-probes/src/task-profile/profile-schema";

function emit(value: unknown): void { process.stdout.write(JSON.stringify(value) + "\n"); }

if (Bun.argv[2] === "schemas") {
  emit({
    start: z.toJSONSchema(StartTaskProfileResponseSchema),
    stop: z.toJSONSchema(StopTaskProfileResponseSchema),
  });
} else if (Bun.argv[2] === "workflow") {
  emit(Bun.YAML.parse(await Bun.file(new URL(
    "../../../.github/workflows/hhem-evaluation-api-test.yml", import.meta.url,
  )).text()));
} else {
  const bootstrap = z.strictObject({
    proc_root: z.string(), platform: z.string(),
    task_profile: z.record(z.string(), z.union([z.boolean(), z.number()])).default({}),
    report_mode: z.enum(["normal", "pending"]).default("normal"),
  });
  const command = z.discriminatedUnion("kind", [
    z.strictObject({
      kind: z.literal("request"), path: z.enum([START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH]),
      body: z.string(),
    }),
    z.strictObject({ kind: z.literal("wait_profile") }),
    z.strictObject({ kind: z.literal("close") }),
  ]);
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  let handler: ReturnType<typeof createSampleHandler> | undefined;
  let profile: TaskProfile | undefined;
  let reported: (() => void) | undefined;
  const completed = new Promise<void>(resolve => { reported = resolve; });
  let clean = true;
  try {
    for await (const line of lines) {
      if (handler === undefined) {
        const input = bootstrap.parse(JSON.parse(line));
        const authored = await loadConfig(new URL(
          "../../../config/hhem-evaluator/host-probes.json", import.meta.url,
        ));
        const config = ProbeConfigSchema.parse({
          ...authored, task_profile: { ...authored.task_profile, ...input.task_profile },
        });
        handler = createSampleHandler(
          config, { platform: input.platform, procRoot: input.proc_root },
          value => {
            profile = TaskProfileSchema.parse(value);
            reported!();
            if (input.report_mode === "pending") return new Promise<void>(() => {});
          },
        );
        emit({ kind: "ready" });
        continue;
      }
      const input = command.parse(JSON.parse(line));
      if (input.kind === "close") break;
      if (input.kind === "wait_profile") {
        await completed;
        emit({ kind: "profile", profile });
        continue;
      }
      const response = await handler(new Request(`http://127.0.0.1${input.path}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: input.body,
      }));
      emit({ kind: "response", status: response.status, body: await response.text() });
    }
  } catch {
    clean = false;
  } finally {
    try { await handler?.close(); }
    catch { clean = false; }
    emit({
      kind: "closed", clean, end_reason: profile?.end_reason ?? null,
      outcome: profile?.outcome ?? null,
    });
    lines.close();
    process.stdin.destroy();
    if (!clean) process.exitCode = 1;
  }
}
