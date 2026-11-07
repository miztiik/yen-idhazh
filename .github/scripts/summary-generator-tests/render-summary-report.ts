/** Which summary and explicit missing readings belong in a private summary-only job report? */
import { readSummaryWorkflowEvent, type SummaryWorkflowEvent } from "./contracts/summary-workflow.schema.js";

function escapeText(value: string): string {
  return value.replace(/([\\`*_{}[\]()#+.!|<>])/g, "\\$1");
}
function tokenReading(value: number | null): string {
  return value === null ? "Not provided by the native model" : `${value} tokens reported by the native model`;
}

export function renderSummaryReport(input: SummaryWorkflowEvent): string {
  const event = readSummaryWorkflowEvent(input);
  const data = event.data;
  const result = data.result;
  const submittedWords = data.request.input_text.split(/\s+/).filter(Boolean).length;
  return [
    "# Summary generation",
    "",
    `## ${escapeText(result.data.headline)}`,
    "",
    escapeText(result.data.executive_summary),
    "",
    "### Key points",
    "",
    ...(result.data.key_points.length ? result.data.key_points.map(point => `- ${escapeText(point)}`) :
      ["No separate key points were returned."]),
    "",
    "## Generation evidence",
    "",
    "**Table A - This summary request**",
    "",
    "| Id | Reading | Observation |",
    "| --- | --- | --- |",
    `| A1 | Selected model | ${escapeText(data.model_name)} |`,
    `| A2 | Effective prompt | ${result.prompt_source === "default" ? "Configured default" : "Complete request override"} |`,
    `| A3 | Prompt SHA-256 | \`${result.prompt_sha256}\` |`,
    `| A4 | Input token count | ${tokenReading(result.usage.prompt_tokens)} |`,
    `| A5 | Output token count | ${tokenReading(result.usage.completion_tokens)} |`,
    "| A6 | Classification readings | Not collected; this call generates a summary only |",
    "| A7 | Machine readings | Not collected; this workflow makes no host measurement call |",
    "",
    "Token counts describe this native request, not a throughput comparison or a quality score.",
    "",
    "## Source and trace",
    "",
    `Source: ${escapeText(data.source_audit.sourceTitle)} (${escapeText(data.source_audit.sourceType)}).`,
    `Preparation retained ${data.source_audit.extractedWordCount} source words and submitted ${submittedWords} words.`,
    ...(data.source_audit.scrapeError === undefined ? [] :
      ["URL extraction failed; the caller used the supplied direct-text fallback."]),
    "",
    `Input SHA-256: \`${data.input_sha256}\`.`,
    `Completed at ${event.time} UTC.`,
    `Caller occurrence: \`${event.id}\`.`,
    `Caller operation: \`${event.traceparent}\`.`,
    `API operation: \`${data.api_traceparent}\`.`,
    "",
  ].join("\n");
}
