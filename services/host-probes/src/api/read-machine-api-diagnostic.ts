/** Project native machine diagnostics without forwarding bodies or duplicating profile measurements. */
import type { ApiDiagnostic } from "@idhazh/serve-pipeline-apis/events";
import { TaskProfileSchema } from "../task-profile/profile-schema";
import type { TaskProfile } from "../task-profile/profile-schema";

export function readMachineApiDiagnostic(raw: unknown): ApiDiagnostic<TaskProfile> {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw) || "specversion" in raw) return { kind: "invalid" };
  if ("event" in raw && raw.event === "task_profile") {
    const profile = TaskProfileSchema.safeParse("profile" in raw ? raw.profile : undefined);
    return profile.success
      ? { kind: "profile", profile: profile.data, operation: profile.data }
      : { kind: "invalid" };
  }
  const code = "code" in raw && typeof raw.code === "string" && /^[A-Z][A-Z0-9_]*$/.test(raw.code)
    ? raw.code : "API_OPERATION_FAILED";
  return { kind: "event", data: { phase: "module_failed", severity: "error", code } };
}
