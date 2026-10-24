/** Route sampler lifecycle messages on an event loop independent of the task. */
import { parentPort, workerData } from "node:worker_threads";
import { CollectorCommandSchema, CollectorInputSchema } from "./profile-schema";
import type { TaskEndReason, TaskOutcome } from "./profile-schema";
import { TaskCollector } from "./task-collector";
import { ProcessPinError } from "./process-stat";

if (parentPort === null) throw new Error("Task collector requires its owning worker port");
const port = parentPort;
const input = CollectorInputSchema.parse(workerData);
const openedAt = performance.now();
const deadline = input.expires_after_ms === null ? null : openedAt + input.expires_after_ms;
const expires_at = input.expires_after_ms === null ? null : new Date(Date.now() + input.expires_after_ms).toISOString();

try {
  const collector = new TaskCollector(input);
  let closed = false;
  let expiry: ReturnType<typeof setTimeout> | undefined;
  const close = (outcome: TaskOutcome, reason: TaskEndReason) => {
    if (closed) return;
    closed = true;
    clearInterval(timer);
    clearTimeout(expiry);
    try { port.postMessage({ type: "complete", profile: collector.close(outcome, reason) }); }
    finally { port.close(); }
  };
  const timer = setInterval(() => {
    collector.poll();
    if (collector.ownerEndReason !== null) close("cancelled", collector.ownerEndReason);
    else if (deadline !== null && performance.now() >= deadline) close("cancelled", "expired");
  }, input.config.poll_interval_ms);
  if (deadline !== null) {
    const expire = () => {
      const remaining = deadline - performance.now();
      if (remaining <= 0) close("cancelled", "expired");
      else expiry = setTimeout(expire, remaining);
    };
    expiry = setTimeout(expire, Math.max(0, deadline - performance.now()));
  }
  port.once("message", (raw: unknown) => {
    const { outcome, end_reason } = CollectorCommandSchema.parse(raw);
    if (deadline !== null && performance.now() >= deadline) close("cancelled", "expired");
    else close(outcome, end_reason);
  });
  port.postMessage({ type: "ready", target: collector.target, expires_at });
} catch (error) {
  if (!(error instanceof ProcessPinError)) throw error;
  port.postMessage({ type: "rejected", reason: error.reason });
  port.close();
}
