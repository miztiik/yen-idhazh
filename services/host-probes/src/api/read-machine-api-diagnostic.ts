/** Project native machine diagnostics without forwarding bodies or duplicating profile measurements. */
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { FingerprintEventSchema } from "@idhazh/host-fingerprints/diagnostic";
import type { FingerprintDiagnosticData } from "@idhazh/host-fingerprints/diagnostic";
import { ProbeEventSchema } from "./create-probe-event";
import type { ProbeDiagnosticData } from "./create-probe-event";
import { TaskProfileSchema } from "../task-profile/profile-schema";
import type { TaskProfile } from "../task-profile/profile-schema";

export type MachineDiagnosticData = FingerprintDiagnosticData | ProbeDiagnosticData;

export function readMachineApiDiagnostic(raw: unknown): ApiDiagnostic<TaskProfile, MachineDiagnosticData> {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return { kind: "invalid" };
  if ("specversion" in raw) {
    if ("type" in raw && (raw.type === "host_fingerprint_completed" || raw.type === "host_fingerprint_failed")) {
      const event = FingerprintEventSchema.safeParse(raw);
      return event.success ? { kind: "native_event", createEvent: () => event.data } : { kind: "invalid" };
    }
    if ("type" in raw && typeof raw.type === "string" && [
      "host_probe_completed", "host_probe_failed", "host_probe_cleanup_failed",
      "host_probe_body_cleanup_failed", "task_profile_failed",
    ].includes(raw.type)) {
      const event = ProbeEventSchema.safeParse(raw);
      return event.success ? { kind: "native_event", createEvent: () => event.data } : { kind: "invalid" };
    }
    return { kind: "invalid" };
  }
  if ("event" in raw && raw.event === "task_profile") {
    const profile = TaskProfileSchema.safeParse("profile" in raw ? raw.profile : undefined);
    return profile.success
      ? { kind: "profile", profile: profile.data, operation: profile.data }
      : { kind: "invalid" };
  }
  return { kind: "invalid" };
}
