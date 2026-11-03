/** Explain a validated execution failure without rendering exception messages or raw stacks. */
import { PlannerFailureSchema } from "@idhazh/common-contracts";
import type { PlannerFailure, PlannerFailureDetail, PlannerFailureOperation } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

const causes: Readonly<Record<PlannerFailureDetail["safe_cause"], string>> = {
  "invalid-input": "Input failed contract validation", "invalid-state": "The requested state was unavailable",
  "undefined-value": "Code accessed a missing value", "invalid-type": "Code used an incompatible value",
  "invalid-syntax": "Code could not parse its input", "out-of-range": "A value exceeded its permitted range",
  "missing-reference": "Code referred to an unavailable value", cancelled: "The operation was cancelled",
  "system-error": "An operating system request failed", "execution-error": "The operation failed; message text is withheld",
};
const operations: Readonly<Record<PlannerFailureOperation, string>> = {
  plan: "Run the article plan", fetch: "Download source content", parse: "Extract source content",
  select: "Choose articles", partition: "Assign article workers", persist: "Save selected output",
  "collection-start": "Start feed and article work", "collection-complete": "Complete feed and article work",
  "collection-cancel": "Cancel feed and article work", "collection-finalize": "Save work totals",
  "collection-release": "Release completed work", "record-run": "Save the run outcome",
  "feed-health-before-fetch": "Read feed health before requests",
  "feed-health-for-selection": "Read fresh feed health for selection",
  "feed-health-state": "Read or save feed health", "feed-health-summary": "Read the feed health summary",
  "recognize-entities": "Find article names", "write-entities": "Save article names",
  "write-document-failures": "Save failed-input metadata",
  "listener-start": "Start the local API", "listener-close": "Close the local API",
  workflow: "Run workflow tasks", "verify-output": "Check saved output",
  "commit-ledgers": "Commit completed metadata", "write-report": "Write the run report",
  "prepare-artifacts": "Prepare download files", "artifact-upload": "Upload download files",
};

export function renderExecutionFailure(input: PlannerFailure | null): string {
  if (input === null) return "Detailed execution failure evidence was not recorded.";
  const failure = PlannerFailureSchema.parse(input);
  const details = [failure, ...failure.causes];
  return [
    "## Table K - Execution failure", "",
    "| Id | Role | Operation | Error type | Safe cause | Source file and line |",
    "| --- | --- | --- | --- | --- | --- |",
    ...details.map((detail, index) => {
      const source = detail.source === null ? "Not recorded" : `${escapeMarkdown(detail.source.file)}:${detail.source.line}`;
      const cause = `${causes[detail.safe_cause]}${detail.system_code === null ? "" : ` (${detail.system_code})`}`;
      return `| K${index + 1} | ${index === 0 ? "Original failure" : "Related failure"} | ${operations[detail.operation]} | ${detail.error_type} | ${cause} | ${source} |`;
    }),
    "", "Error type is the runtime error category. Source locations were captured where the operation failed; unavailable locations are not guessed.",
    "", `Run: ${failure.execution.run_id ?? "Not recorded"}; attempt: ${failure.execution.attempt ?? "Not recorded"}; code revision: ${failure.execution.git_sha ?? "Not recorded"}.`,
    ...(failure.omitted_causes > 0 ? ["", `${failure.omitted_causes} further causes were omitted by the configured limit.`] : []),
    "", "Exception messages, article text and raw stacks are not included.",
  ].join("\n");
}
