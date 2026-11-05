/** Adapt native feed startup, readiness and failure evidence to the shared task supervisor. */
import { fileURLToPath } from "node:url";
import { superviseApiTask } from "@idhazh/serve-pipeline-apis/supervisor";
import { MachineServerEvidenceSchema } from "@idhazh/host-probes/machine-evidence";
import type { FailureCaptureOptions } from "../src/api/plan-failure";
import { captureFeedApiFailure } from "./capture-feed-api-failure";
import { FeedApiStartupSchema } from "./read-feed-api-startup";
import type { FeedApiStartup } from "./read-feed-api-startup";
import { readFeedApiReadiness } from "./read-feed-api-readiness";
import { readFeedApiDiagnostic } from "./read-feed-api-diagnostic";

export function superviseFeedApiTask<T>(input: {
  root: string; startup: FeedApiStartup; capture: FailureCaptureOptions;
  serverEntry?: string; signal?: AbortSignal;
  request: (origin: string, signal: AbortSignal) => Promise<T>;
}): Promise<T> {
  const startup = FeedApiStartupSchema.parse(input.startup);
  const kind = startup.group === "planning" ? "PLANNER" : "SAFE_PERSIST";
  const failure = captureFeedApiFailure(input.capture);
  return superviseApiTask({
    ...input, startup, kind, failure,
    serverEntry: input.serverEntry ?? fileURLToPath(new URL("./serve-feed-apis.ts", import.meta.url)),
    supervision: startup.server.supervision,
    maxControlBytes: (startup.group === "planning" ? startup.planner : startup.delivery).settings.listener.max_body_bytes,
    evidenceSchema: MachineServerEvidenceSchema, decodeDiagnostic: readFeedApiDiagnostic,
    ready: (message, pid, signal) => readFeedApiReadiness({ message, pid, signal, startup, kind, failure }),
  });
}
