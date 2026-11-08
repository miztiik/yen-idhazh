/** Do the generation writer, saved-input reader and report preserve each result? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import {
  readTraceContext,
} from "../../../packages/common-contracts/src/index.ts";
import {
  AIEventPipeline, publishStepSummary, resolvePipelinePhase, WORKFLOW_EVENT_SOURCE,
} from "../../../.github/scripts/ai-pipeline.ts";
import { readPipelineEvents, selectStructuredOutputs, type PipelineEvent } from "../read-pipeline-events.ts";

const fixtures = new URL("../../../tests/fixtures/typescript-metadata/", import.meta.url);
const outputPath = fileURLToPath(new URL("workflow-output-event.json", fixtures));

function readSavedOutput() {
  const [event] = selectStructuredOutputs(readPipelineEvents(outputPath));
  if (!event) throw new Error("The named workflow output recording is missing.");
  return event;
}

function readProducer(event: PipelineEvent) {
  const context = readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
  if (!context) throw new Error("The recorded producer context is invalid.");
  return context;
}

async function withDirectory(run: (directory: string) => Promise<void>) {
  const directory = join(fileURLToPath(new URL("../../../backend/var/", import.meta.url)),
    `workflow-handoff-${randomUUID()}`);
  await mkdir(directory, { recursive: true });
  try {
    await run(directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

test("distinct occurrences and producer identities survive saved generation readback", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const path = join(directory, "events.jsonl");
    const first = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const second = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const result = {
      ...saved.data.result,
      source_audit: { ...saved.data.result.source_audit, feedAudit: undefined },
      swap_metrics: { ...saved.data.result.swap_metrics, diagnostics_error: undefined },
    };
    first.logEvent("INPUT_RESOLVED", { wordCount: saved.data.result.source_audit.extractedWordCount });
    const produced = [
      first.logEvent("OUTPUT_STRUCTURED", result),
      first.logEvent("OUTPUT_STRUCTURED", saved.data.result),
      second.logEvent("OUTPUT_STRUCTURED", {
        ...saved.data.result,
        analytic_synthesis: "A separate saved summary.",
        source_audit: { ...saved.data.result.source_audit, extractedText: "A separate saved source." },
      }),
    ];
    expect(new Set(produced.map(event => event.id)).size).toBe(produced.length);
    expect(produced.every(event => event.source === "/workflows/ai-pipeline")).toBe(true);
    expect(produced[0]!.data.result).toEqual(saved.data.result);
    expect(produced[0]!.traceparent).toBe(produced[1]!.traceparent);
    const bytes = await readFile(path, "utf8");
    const selected = selectStructuredOutputs(readPipelineEvents(path));
    expect(produced).toEqual(selected);
    const resumed = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    resumed.loadPriorEvents();
    for (const [index, input] of selected.entries()) {
      const producer = readProducer(input);
      expect(producer).toEqual(readProducer(produced[index]!));
      expect(resumed.context.traceId).not.toBe(producer.traceId);
    }
    expect(readProducer(selected[2]!).traceId).not.toBe(readProducer(selected[0]!).traceId);
    expect(selected[2]!.data.result.source_audit.extractedText)
      .not.toBe(selected[0]!.data.result.source_audit.extractedText);
    const anotherPhase = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    expect(anotherPhase.context.traceId).not.toBe(resumed.context.traceId);
    expect(await readFile(path, "utf8")).toBe(bytes);
  }));

test("retired evaluation fails before reading config or starting generation", async () =>
  withDirectory(async directory => {
    const events = join(directory, "events.jsonl");
    const child = Bun.spawn(
      [process.execPath, fileURLToPath(new URL("../../../.github/scripts/ai-pipeline.ts", import.meta.url)), "--phase=eval"],
      {
        cwd: directory,
        env: { ...process.env, CONFIG_ROOT: join(directory, "absent-config"),
          PIPELINE_EVENTS_PATH: events },
        stdout: "pipe",
        stderr: "pipe",
      },
    );
    const output = await new Response(child.stdout).text();
    expect(await child.exited).toBe(1);
    expect(JSON.parse(output).code).toBe("EVALUATION_RETIRED");
    expect(await Bun.file(events).exists()).toBe(false);
  }));

test("only explicit inference or the unchanged default can select generation", () => {
  expect(resolvePipelinePhase([])).toBe("infer");
  expect(resolvePipelinePhase(["--phase=infer"])).toBe("infer");
  expect(() => resolvePipelinePhase(["--phase=EVAL"])).toThrow("EVALUATION_RETIRED");
  expect(() => resolvePipelinePhase(["--phase=unknown"])).toThrow("INVALID_PIPELINE_PHASE");
});

test("resuming keeps the cumulative counter while each new log gap uses the phase clock", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const path = join(directory, "events.jsonl");
    await copyFile(outputPath, path);
    const pipeline = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const beforeLoad = performance.now();
    pipeline.loadPriorEvents();
    const afterLoad = performance.now();
    const beforeFirst = performance.now();
    const first = pipeline.logEvent("INFERENCE_RESUMED", { articleCount: 1 });
    const afterFirst = performance.now();
    expect(first.data.durationMs).toBeGreaterThanOrEqual(Math.max(0, Math.floor(beforeFirst - afterLoad)));
    expect(first.data.durationMs).toBeLessThanOrEqual(Math.ceil(afterFirst - beforeLoad));
    expect(first.data.cumulativeMs - saved.data.cumulativeMs)
      .toBeGreaterThanOrEqual(Math.floor(beforeFirst - afterLoad));
    expect(first.data.cumulativeMs - saved.data.cumulativeMs)
      .toBeLessThanOrEqual(Math.ceil(afterFirst - beforeLoad));
    const beforeSecond = performance.now();
    const second = pipeline.logEvent("INFERENCE_RESUME_COMPLETED", { generatedCount: 1 });
    const afterSecond = performance.now();
    expect(second.data.durationMs).toBeGreaterThanOrEqual(Math.max(0, Math.floor(beforeSecond - afterFirst)));
    expect(second.data.durationMs).toBeLessThanOrEqual(Math.ceil(afterSecond - beforeFirst));
    expect(readPipelineEvents(path)[0]).toEqual(saved);
  }));

test.each(["json", "carrier", "measurement", "result", "blank"])(
  "a malformed saved %s record fails the real reader and continuation without rewriting the file",
  async failure => withDirectory(async directory => {
    const saved = readSavedOutput();
    const malformed = {
      json: "{",
      carrier: JSON.stringify({ ...saved, traceparent: "invalid" }),
      measurement: JSON.stringify({ ...saved, data: { ...saved.data, durationMs: "invalid" } }),
      result: JSON.stringify({ ...saved, data: {
        ...saved.data, result: { ...saved.data.result, source_audit: {
          ...saved.data.result.source_audit, extractedText: null,
        } },
      } }),
      blank: "",
    }[failure]!;
    const path = join(directory, "events.jsonl");
    const content = `${JSON.stringify(saved)}\n${malformed}\n`;
    await writeFile(path, content);
    expect(() => readPipelineEvents(path)).toThrow("INVALID_PIPELINE_EVENT at line 2");
    const pipeline = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    expect(() => pipeline.loadPriorEvents()).toThrow("INVALID_PIPELINE_EVENT at line 2");
    expect(await readFile(path, "utf8")).toBe(content);
  }),
);

test("empty input selects no work and missing input fails rather than rerunning inference", async () =>
  withDirectory(async directory => {
    const path = join(directory, "empty.jsonl");
    await writeFile(path, "");
    expect(selectStructuredOutputs(readPipelineEvents(path))).toEqual([]);
    expect(() => readPipelineEvents(join(directory, "absent.jsonl"))).toThrow("PIPELINE_EVENTS_READ_FAILED");
  }));

test("the actual report reads the saved event identity and both stored measurements", async () =>
  withDirectory(async directory => {
    const event = readSavedOutput();
    const path = join(directory, "summary.md");
    const previous = process.env.GITHUB_STEP_SUMMARY;
    process.env.GITHUB_STEP_SUMMARY = path;
    try {
      publishStepSummary("recorded-model", [event.data.result], [event], event.data.result.inference_params);
      const report = await readFile(path, "utf8");
      expect(report).toContain(event.id);
      expect(report).toContain(event.time);
      expect(report).toContain(`+${event.data.durationMs} ms`);
      expect(report).toContain(`${event.data.cumulativeMs} ms`);
    } finally {
      if (previous === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previous;
    }
  }));
