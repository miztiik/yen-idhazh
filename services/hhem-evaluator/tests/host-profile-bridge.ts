/** How do offline cases compose native host collection without a TCP listener? */
import { z } from "../../host-probes/node_modules/zod";
import { createInterface } from "node:readline";
import { loadConfig, ProbeConfigSchema } from "../../host-probes/src/config";
import { startTaskProfile } from "../../host-probes/src/task-profile/task-profiler";
import type { TaskProfileSession } from "../../host-probes/src/task-profile/task-profiler";
import { TaskProfileSchema } from "../../host-probes/src/task-profile/profile-schema";
import type { TaskProfile } from "../../host-probes/src/task-profile/profile-schema";
import { HostFingerprintRowSchema } from "../../../packages/common-contracts/src/schemas/host-fingerprint.schema";
import { createFingerprintHandler, FINGERPRINT_PATH } from "../../host-fingerprints/src/api/server";
import { fixture } from "../../host-fingerprints/test/fixture";
import { join } from "node:path";
import { mkdir } from "node:fs/promises";
import { projectMachineProfile } from "../../../.github/scripts/summary-eval-hhem/project-profile";
import { HardwareSchema } from "../../../.github/scripts/summary-eval-hhem/hardware";

function emit(value: unknown): void { process.stdout.write(JSON.stringify(value) + "\n"); }

if (Bun.argv[2] === "schemas") {
  emit({
    hardware: z.toJSONSchema(HostFingerprintRowSchema),
    machine: z.toJSONSchema(TaskProfileSchema),
  });
} else if (Bun.argv[2] === "workflow") {
  emit(Bun.YAML.parse(await Bun.file(new URL(
    "../../../.github/workflows/hhem-evaluation-api-test.yml", import.meta.url,
  )).text()));
} else {
  const bootstrap = z.strictObject({
    proc_root: z.string(), platform: z.string(),
    task_profile: z.record(z.string(), z.union([z.boolean(), z.number()])).default({}),
    fail_report: z.boolean().default(false),
  });
  const command = z.strictObject({ kind: z.literal("stop"), outcome: z.enum(["success", "error"]) });
  let session: TaskProfileSession | null = null;
  let started = false;
  let profile: TaskProfile | undefined;
  let clean = true;
  const f = await fixture();
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  try {
    for await (const line of lines) {
      if (!started) {
        started = true;
        const input = bootstrap.parse(JSON.parse(line));
        const authored = await loadConfig();
        const config = ProbeConfigSchema.parse({
          ...authored, task_profile: {
            ...authored.task_profile, enabled: true, machine_memory_enabled: true,
            memory_enabled: false, ...input.task_profile,
          },
        });
        const handler = createFingerprintHandler(f.config, f.settings, {
          outputRoot: join(f.directory, "state"), inspection: f.inspection,
        });
        const response = await handler(new Request(`http://127.0.0.1${FINGERPRINT_PATH}`, {
          method: "POST", body: JSON.stringify(f.apiInput),
        }));
        const hardware = z.object({
          status: z.literal("written"), row: HostFingerprintRowSchema,
          unavailable: z.record(z.string(), z.string()),
        }).parse(await response.json());
        if (response.status !== 200) throw new Error("Native hardware handler failed");
        const recorded = z.object({
          pid: z.int().positive(), stat: z.string(),
        }).parse(await Bun.file(new URL(
          "../../../tests/fixtures/host-probes/process-inputs.json", import.meta.url,
        )).json());
        const processRoot = join(input.proc_root, String(process.pid));
        await mkdir(processRoot, { recursive: true });
        await Bun.write(join(processRoot, "stat"),
          recorded.stat.replace(`${recorded.pid} `, `${process.pid} `));
        session = await startTaskProfile({
          config, context: { platform: input.platform, procRoot: input.proc_root },
          report(value) {
            profile = value;
            if (input.fail_report) throw new Error("Profile reporting failed after collection");
          },
        }, {
          pipeline_name: "summary-eval-hhem", task_name: "summary-eval-hhem",
          run_id: f.capture.writer.run_id,
          request_id: "12345678-1234-4234-8234-123456789abc",
          correlation_id: "12345678-1234-4234-8234-123456789abd",
        });
        emit({
          kind: "ready", profile_started: session !== null,
          hardware: HardwareSchema.parse({
            ...hardware.row, status: "collected", unavailable: hardware.unavailable, reason: null,
          }),
        });
        continue;
      }
      const input = command.parse(JSON.parse(line));
      await session?.close(input.outcome, "explicit_stop");
      break;
    }
  } catch {
    clean = false;
  } finally {
    try { if (profile === undefined) await session?.close("cancelled", "service_stopped"); }
    catch { clean = false; }
    emit({
      kind: "closed", clean, profile: profile === undefined ? null : projectMachineProfile(profile),
    });
    lines.close();
    process.stdin.destroy();
    await f.cleanup();
    if (!clean) process.exitCode = 1;
  }
}
