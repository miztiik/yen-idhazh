/** Route sampler lifecycle messages on an event loop independent of the task. */
import { parentPort, workerData } from "node:worker_threads";
import { CollectorCommandSchema, CollectorInputSchema } from "./profile-schema";
import { TaskCollector } from "./task-collector";

if (parentPort === null) throw new Error("Task collector requires its owning worker port");
const port = parentPort;
const input = CollectorInputSchema.parse(workerData);
const collector = new TaskCollector(input);
const timer = setInterval(() => collector.poll(), input.config.poll_interval_ms);
port.once("message", (raw: unknown) => {
  clearInterval(timer);
  try {
    const { outcome } = CollectorCommandSchema.parse(raw);
    port.postMessage({ type: "complete", profile: collector.close(outcome) });
  } finally { port.close(); }
});
port.postMessage({ type: "ready" });
