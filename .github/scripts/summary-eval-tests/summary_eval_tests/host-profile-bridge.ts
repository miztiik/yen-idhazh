/** How do offline cases compose native host collection without a TCP listener? */
import { z } from "../../../../services/host-probes/node_modules/zod";
import { createInterface } from "node:readline";
import { loadConfig, ProbeConfigSchema } from "../../../../services/host-probes/src/config";
import { START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../../../../services/host-probes/src/api/server";
import { createApiApp } from "../../../../services/serve-pipeline-apis/src/create-api-app";
import { createMachineApp } from "../../../../services/host-probes/src/api/create-machine-app";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../../../../services/host-probes/src/api/task-command-schema";
import { startTaskProfile } from "../../../../services/host-probes/src/task-profile/task-profiler";
import type { TaskProfileSession } from "../../../../services/host-probes/src/task-profile/task-profiler";
import { parseProcessStat } from "../../../../services/host-probes/src/task-profile/process-stat";
import { TaskProfileSchema } from "../../../../services/host-probes/src/task-profile/profile-schema";
import type { TaskProfile } from "../../../../services/host-probes/src/task-profile/profile-schema";
import { OperationMetadataSchema } from "../../../../packages/common-contracts/src/schemas/operation-metadata.schema";
import type { OperationMetadata } from "../../../../packages/common-contracts/src/schemas/operation-metadata.schema";
import { HostFingerprintRowSchema } from "../../../../packages/common-contracts/src/schemas/host-fingerprint.schema";
import { FINGERPRINT_PATH } from "../../../../services/host-fingerprints/src/api/server";
import { fixture } from "../../../../services/host-fingerprints/test/fixture";
import { join } from "node:path";
import { mkdir } from "node:fs/promises";
import { projectMachineProfile, HardwareSchema } from "../machine-results";
import { MachineServerEvidenceSchema } from "../../../../services/host-probes/src/api/create-machine-server-evidence";

function emit(value: unknown): void { process.stdout.write(JSON.stringify(value) + "\n"); }

if (Bun.argv[2] === "schemas") {
  emit({
    hardware: z.toJSONSchema(HostFingerprintRowSchema),
    machine: z.toJSONSchema(TaskProfileSchema),
    server: z.toJSONSchema(MachineServerEvidenceSchema),
  });
} else if (Bun.argv[2] === "workflow") {
  emit(Bun.YAML.parse(await Bun.file(new URL(
    "../../../../.github/workflows/summary-eval-tests.yml", import.meta.url,
  )).text()));
} else {
  const bootstrap = z.strictObject({
    proc_root: z.string(), platform: z.string(),
    task_profile: z.record(z.string(), z.union([z.boolean(), z.number()])).default({}),
    fail_report: z.boolean().default(false),
  });
  const command = z.strictObject({ kind: z.literal("stop"), outcome: z.enum(["success", "error"]) });
  let session: TaskProfileSession | null = null;
  let handler: ReturnType<typeof createApiApp> | undefined;
  let handle: string | undefined;
  let operation: OperationMetadata | undefined;
  let started = false;
  let profile: TaskProfile | undefined;
  let clean = true;
  let stage = "input";
  let httpStatus: number | null = null;
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
        const recorded = z.object({
          pid: z.int().positive(), stat: z.string(),
        }).parse(await Bun.file(new URL(
          "../../../tests/fixtures/host-probes/process-inputs.json", import.meta.url,
        )).json());
        const processRoot = join(input.proc_root, String(process.pid));
        await mkdir(processRoot, { recursive: true });
        await Bun.write(join(processRoot, "stat"),
          recorded.stat.replace(`${recorded.pid} `, `${process.pid} `));
        const profiling = {
          config, context: { platform: input.platform, procRoot: input.proc_root },
          report(value: TaskProfile) {
            profile = value;
            if (input.fail_report) throw new Error("Profile reporting failed after collection");
          },
        };
        handler = createApiApp({
          identity: {
            event: "typescript_api_ready", nonce: crypto.randomUUID(), pid: process.pid,
            port: 8787, group: "machine", modules: ["machine"], enabled: true,
          },
          create: () => createMachineApp({
            fingerprint: {
              config: f.config, settings: f.settings,
              options: {
                outputRoot: join(f.directory, "state"), inspection: f.inspection,
                registryPath: new URL("../../../config/ledgers.json", import.meta.url),
              },
            },
            probes: profiling,
          }),
        });
        stage = "fingerprint";
        const response = await handler.fetch(new Request(`http://127.0.0.1${FINGERPRINT_PATH}`, {
          method: "POST", body: JSON.stringify(f.apiInput),
        }));
        httpStatus = response.status;
        const hardware = z.object({
          status: z.literal("written"), row: HostFingerprintRowSchema,
          unavailable: z.record(z.string(), z.string()),
        }).parse(await response.json());
        if (response.status !== 200) throw new Error("Native hardware handler failed");
        const identity = {
          pipeline_name: "summary-eval-tests", task_name: "summary-eval-tests",
          run_id: f.capture.writer.run_id,
        };
        if (input.platform === "linux" || !config.task_profile.enabled) {
          stage = "profile_start";
          httpStatus = null;
          const processInput = parseProcessStat(recorded.pid, recorded.stat);
          if (processInput.reason !== null) throw new Error("Recorded profile target has no valid process identity");
          const response = await handler.fetch(new Request(`http://localhost${START_TASK_PROFILE_PATH}`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ identity, target: { pid: process.pid, start_ticks: processInput.value.start_ticks } }),
          }));
          httpStatus = response.status;
          if (response.status !== 200) throw new Error("Native host profile start failed");
          const result = StartTaskProfileResponseSchema.parse(await response.json());
          if (result.status === "started") {
            handle = result.handle;
            operation = OperationMetadataSchema.strip().parse(result);
          }
        } else {
          // An unsupported host cannot verify the pin required by HTTP; its embedded collector can still report unavailable data.
          session = await startTaskProfile(profiling, identity);
          operation = session?.operation;
        }
        emit({
          kind: "ready", profile_started: handle !== undefined || session !== null,
          hardware: HardwareSchema.parse({
            ...hardware.row, status: "collected", unavailable: hardware.unavailable, reason: null,
          }),
        });
        continue;
      }
      const input = command.parse(JSON.parse(line));
      stage = "profile_stop";
      httpStatus = null;
      if (handler !== undefined && handle !== undefined) {
        const response = await handler.fetch(new Request(`http://localhost${STOP_TASK_PROFILE_PATH}`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ handle, outcome: input.outcome }),
        }));
        httpStatus = response.status;
        if (response.status !== 200) throw new Error("Native host profile stop failed");
        const result = StopTaskProfileResponseSchema.parse(await response.json());
        if (result.status !== "stopped" || result.handle !== handle) throw new Error("Native host profile did not retain its handle");
        profile = result.profile;
      } else {
        await session?.close(input.outcome, "explicit_stop");
      }
      break;
    }
  } catch {
    clean = false;
    process.stderr.write(JSON.stringify({
      event: "summary_host_fixture_failed", stage, http_status: httpStatus,
    }) + "\n");
  } finally {
    try {
      await handler?.close();
      if (profile === undefined) await session?.close("cancelled", "service_stopped");
    }
    catch { clean = false; }
    if (profile !== undefined && JSON.stringify(OperationMetadataSchema.strip().parse(profile)) !== JSON.stringify(operation)) clean = false;
    emit({
      kind: "closed", clean, profile: profile === undefined ? null : projectMachineProfile(profile),
    });
    lines.close();
    process.stdin.destroy();
    await f.cleanup();
    if (!clean) process.exitCode = 1;
  }
}
