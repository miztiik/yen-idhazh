/** Supervise a real machine API task with native startup, diagnostics and profile validation. */
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { superviseApiTask } from "@idhazh/serve-pipeline-apis/supervisor";
import { readApiReadiness } from "@idhazh/serve-pipeline-apis/readiness";
import { loadConfig } from "../config";
import { MachineApiStartupSchema, MachineApiStartupFailureSchema, readMachineApiIdentity } from "./read-machine-api-startup";
import type { MachineApiStartup } from "./read-machine-api-startup";
import { captureMachineApiFailure, MachineApiError } from "./capture-machine-api-failure";
import { MachineServerEvidenceSchema } from "./create-machine-server-evidence";
import { readMachineApiDiagnostic } from "./read-machine-api-diagnostic";

export async function superviseMachineApiTask<T>(input: {
  root: string; startup: MachineApiStartup; serverEntry?: string; signal?: AbortSignal;
  request: (origin: string, signal: AbortSignal) => Promise<T>;
}): Promise<T> {
  const startup = MachineApiStartupSchema.parse(input.startup);
  const config = await loadConfig(join(input.root, "config", "host-probes.json"));
  const failure = captureMachineApiFailure();
  return superviseApiTask({
    ...input, startup, kind: "TYPESCRIPT_API", failure,
    serverEntry: input.serverEntry ?? fileURLToPath(new URL("./serve-machine-apis.ts", import.meta.url)),
    supervision: startup.server.supervision, maxControlBytes: config.max_request_body_bytes,
    evidenceSchema: MachineServerEvidenceSchema, decodeDiagnostic: readMachineApiDiagnostic,
    ready: (message, pid, signal) => {
      const failed = MachineApiStartupFailureSchema.safeParse(message);
      if (failed.success) throw new MachineApiError(failed.data.code, failed.data.message);
      return readApiReadiness({
        message, signal, kind: "TYPESCRIPT_API", failure,
        expected: readMachineApiIdentity(startup, pid), server: startup.server, context: startup.run.context,
      });
    },
  });
}
