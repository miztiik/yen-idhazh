/** Return exact native receipts to the offline workflow publisher oracles. */
import { z } from "zod";
import { loadConfig, loadTaskPerformanceSettings, TaskPerformanceExecutionSchema } from "../src/config";
import {
  createSampleHandler, RECORD_TASK_PERFORMANCE_PATH, RecordTaskPerformanceRequestSchema,
} from "../src/api/server";

const batches = z.array(z.strictObject({
  state: z.string(), execution: TaskPerformanceExecutionSchema,
  requests: z.array(RecordTaskPerformanceRequestSchema),
})).parse(JSON.parse(await Bun.stdin.text()));
const settings = await loadTaskPerformanceSettings();
const config = await loadConfig();
for (const { state, execution, requests } of batches) {
  const handler = createSampleHandler(config, undefined, undefined, undefined, {
    outputRoot: state, execution, settings,
  });
  try {
    for (const input of requests) {
      const reply = await handler(new Request(`http://localhost${RECORD_TASK_PERFORMANCE_PATH}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
      }));
      if (!reply.ok) throw new Error(`${reply.status}: ${await reply.text()}`);
      console.log(await reply.text());
    }
  } finally {
    await handler.close();
  }
}
