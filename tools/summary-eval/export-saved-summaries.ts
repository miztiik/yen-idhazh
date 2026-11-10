/** How do existing generation captures supply unchanged native scoring requests? */
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import {
  PipelineInputError, readPipelineEvents, selectStructuredOutputs,
} from "../ai-pipeline-experiment/read-pipeline-events.ts";

export type SavedSummaryFormat = "pipeline" | "summary-api";

function createRequest(source: string, summary: string) {
  if (!source.trim() || !summary.trim()) {
    throw new PipelineInputError("INVALID_SAVED_INFERENCE_RESULT");
  }
  return {
    source_text: source,
    summary_text: summary,
    hhem_full: false,
    request_id: randomUUID(),
    correlation_id: randomUUID(),
  };
}

export async function readSavedSummaryRequests(
  format: SavedSummaryFormat, input: string, expectedRunId?: string,
) {
  if (format === "summary-api") {
    const { readSummaryWorkflowEvent } = await import(
      "../summary-generator-caller/contracts/summary-workflow.schema.ts"
    );
    const event = readSummaryWorkflowEvent(JSON.parse(readFileSync(input, "utf8")));
    return [createRequest(event.data.request.input_text, event.data.result.data.executive_summary)];
  }
  const events = selectStructuredOutputs(readPipelineEvents(input));
  if (!events.length) throw new PipelineInputError("MISSING_SAVED_INFERENCE_RESULT");
  return events.map(event => {
    const result = event.data.result;
    if (result.error_flag || (expectedRunId !== undefined && result.runner_metadata.runId !== expectedRunId)) {
      throw new PipelineInputError("INVALID_SAVED_INFERENCE_RESULT");
    }
    return createRequest(result.input_text, result.analytic_synthesis);
  });
}

export async function exportSavedSummaries(
  format: SavedSummaryFormat, input: string, output: string, expectedRunId?: string,
): Promise<number> {
  const requests = await readSavedSummaryRequests(format, input, expectedRunId);
  mkdirSync(path.dirname(output), { recursive: true });
  const temporary = `${output}.tmp`;
  writeFileSync(temporary, requests.map(request => JSON.stringify(request) + "\n").join(""), "utf8");
  renameSync(temporary, output);
  return requests.length;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { values } = parseArgs({
      options: {
        format: { type: "string" },
        input: { type: "string" },
        output: { type: "string" },
      },
    });
    if ((values.format !== "pipeline" && values.format !== "summary-api") || !values.input || !values.output) {
      throw new PipelineInputError("INVALID_SAVED_SUMMARY_ARGUMENTS");
    }
    const count = await exportSavedSummaries(
      values.format, values.input, values.output, process.env.GITHUB_RUN_ID,
    );
    console.log(JSON.stringify({ code: "SAVED_SUMMARIES_EXPORTED", count }));
  } catch (error) {
    console.error(JSON.stringify({
      code: error instanceof PipelineInputError ? error.code : "SAVED_SUMMARIES_INVALID",
    }));
    process.exitCode = 1;
  }
}
