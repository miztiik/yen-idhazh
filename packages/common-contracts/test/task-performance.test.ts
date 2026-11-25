/** Can the native writer distinguish available task measurements from missing ones? */
import { expect, test } from "bun:test";
import { TASK_PERFORMANCE_VERSION, TaskPerformanceRowSchema } from "../src/index";

const terminal = {
  version: TASK_PERFORMANCE_VERSION, date: "2026-11-25",
  run_id: "2026-11-25-1", pipeline_name: "digest", task_name: "serve-summary", shard: 2,
  task_kind: "model-serving", outcome: "error", subject_id: "summary",
};

test("retains an observed zero without inventing its other serving total", () => {
  expect(TaskPerformanceRowSchema.parse({ ...terminal, server_prompt_tokens: 0 })).toMatchObject({
    server_prompt_tokens: 0,
    server_prompt_seconds: null,
    elapsed_ms: null,
    host_unit_id: null,
  });
});

test("refuses nonfinite measurements before the record can be written", () => {
  for (const seconds of [Infinity, -Infinity, NaN]) {
    expect(TaskPerformanceRowSchema.safeParse({ ...terminal, server_prompt_seconds: seconds }).success).toBe(false);
  }
});
