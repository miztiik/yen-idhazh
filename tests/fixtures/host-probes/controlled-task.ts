/** Run a real, bounded CPU and touched-RAM task in an independently observed Bun process. */
import { createHash } from "node:crypto";
import { z } from "../../../services/host-probes/node_modules/zod";

const ControlsSchema = z.strictObject({
  cpu_work_ms: z.number().finite().positive(), buffer_bytes: z.int().positive(),
  minimum_periodic_samples: z.int().positive(),
});
const CommandSchema = z.strictObject({ command: z.enum(["work", "close"]) });
const controls = ControlsSchema.parse(await Bun.file(new URL("./controlled-task.json", import.meta.url)).json());
if (process.send === undefined || process.disconnect === undefined) throw new Error("Controlled task requires its owning IPC channel");
const send = process.send.bind(process);
const disconnect = process.disconnect.bind(process);
let buffer: Buffer | undefined;
let worked = false;

process.on("message", (raw: unknown) => {
  const { command } = CommandSchema.parse(raw);
  if (command === "close") {
    buffer = undefined;
    disconnect();
    return;
  }
  if (worked) throw new Error("Controlled task accepts one actual work command");
  worked = true;
  const start = performance.now();
  const deadline = start + controls.cpu_work_ms;
  buffer = Buffer.alloc(controls.buffer_bytes, 1);
  let batches = 0;
  let digest = "";
  do {
    digest = createHash("sha256").update(buffer).digest("hex");
    batches++;
  } while (performance.now() < deadline);
  send({
    type: "complete", allocated_bytes: buffer.byteLength, elapsed_ms: performance.now() - start, batches, digest,
  });
});
send({ type: "ready", pid: process.pid });
