/** Read current terminal article diagnostics only from the same run's explicitly named mirrors. */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  ArticleFailureDiagnosticSchema, isArticleFailureDiagnostic, PositiveCountSchema, RunIdSchema,
  TraceIdSchema, readTraceContext,
} from "@idhazh/common-contracts";
import type { ArticleFailureDiagnostic } from "@idhazh/common-contracts";
import type { MachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import { distinctArticleDiagnostics } from "../src/reporting/article-failure-evidence";
import type { ReportDiagnosticIdentity } from "../src/reporting/article-failure-evidence";

export async function readArticleFailureDiagnostics(input: {
  directory: string; servers: readonly MachineServerEvidence[]; expected: ReportDiagnosticIdentity;
}) {
  const gaps: [string, string, string][] = [];
  const gap = (problem: string, impact: string) => {
    if (!gaps.some(row => row[1] === problem)) gaps.push(["Article diagnostics", problem, impact]);
  };
  const { run_id, attempt, traceId } = input.expected;
  if (run_id !== undefined) RunIdSchema.parse(run_id);
  if (attempt !== undefined) PositiveCountSchema.parse(attempt);
  if (traceId !== undefined) TraceIdSchema.parse(traceId);
  if (input.servers.length === 0) gap("Article diagnostic mirror unavailable", "No named server log was captured");
  if (run_id === undefined || attempt === undefined) {
    gap("Article diagnostic identity unavailable", "Run and attempt are required; no article diagnostics were attributed");
    return { article_diagnostics: [], gaps };
  }
  if (traceId === undefined) gap("Article diagnostic execution identity unavailable",
    "Only the explicit run and attempt can be checked; unrelated requests with the same identity cannot be distinguished");
  const filenames = new Set<string>();
  for (const server of input.servers) {
    if (server.run_id !== run_id.slice(11) || server.attempt !== attempt) {
      throw new Error("Article diagnostic mirror belongs to another run or attempt");
    }
    filenames.add(server.log_filename);
    if (!server.log_available) gap("Article diagnostic mirror is partial or unavailable",
      "Complete validated records remain usable; missing records cannot be recovered");
  }
  const events: ArticleFailureDiagnostic[] = [];
  for (const filename of filenames) {
    let text: string;
    try { text = await readFile(join(input.directory, filename), "utf8"); }
    catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
      gap("Article diagnostic log missing", "The named mirror could not supply terminal article details");
      continue;
    }
    if (text !== "" && !text.endsWith("\n")) gap("Article diagnostic log is incomplete",
      "Complete validated records remain usable; the final line may be unfinished");
    for (const line of text.split("\n")) {
      if (line.trim() === "") continue;
      let raw: unknown;
      try { raw = JSON.parse(line); }
      catch (error) {
        if (!(error instanceof SyntaxError)) throw error;
        gap("Article diagnostic log contains an unreadable line", "Terminal article evidence may be incomplete");
        continue;
      }
      if (!isArticleFailureDiagnostic(raw)) {
        if (raw !== null && typeof raw === "object" && "data" in raw
          && raw.data !== null && typeof raw.data === "object" && "code" in raw.data
          && raw.data.code === "CHILD_DIAGNOSTIC_INVALID") {
          gap("A child diagnostic was rejected", "Terminal article evidence may be incomplete");
        }
        continue;
      }
      const parsed = ArticleFailureDiagnosticSchema.safeParse(raw);
      if (!parsed.success) {
        gap("Malformed terminal article diagnostic", "The invalid record was excluded; complete validated records remain usable");
        continue;
      }
      const event = parsed.data;
      if (event.data.run_id !== run_id || event.data.details.attempt !== attempt
        || (traceId !== undefined && readTraceContext({
          traceparent: event.traceparent, tracestate: event.tracestate,
        })?.traceId !== traceId)) {
        gap("Unrelated article diagnostic excluded", "Its run, attempt or captured execution does not match this report");
        continue;
      }
      events.push(event);
    }
  }
  return { article_diagnostics: distinctArticleDiagnostics(events, input.expected), gaps };
}
