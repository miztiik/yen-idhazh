/** Render concise human stderr and optional JSON stdout for feed-probe reports. */
import { FEED_PROBE_VERSION } from "@idhazh/common-contracts";
import { FeedProbeReportSummarySchema, type FeedProbeReport } from "./feed-probe-report";

export type FeedProbeLogOutput = "INFO" | "DEBUG" | "WARN" | "ERROR";

function visible(value: number | null): string {
  return value === null ? "-" : String(value);
}

export function writeHumanFeedTable(
  stderr: (line: string) => void,
  reports: readonly FeedProbeReport[],
  logLevel: FeedProbeLogOutput,
  failedCount: number,
  totalCount: number,
): void {
  if (logLevel === "ERROR") {
    stderr(`failed/total: ${failedCount}/${totalCount}`);
    return;
  }
  if (logLevel !== "WARN" && logLevel !== "DEBUG" && logLevel !== "INFO") return;

  if (logLevel !== "WARN") {
    const rows = reports.map(report => [
      report.feed_id,
      visible(report.http_status),
      String(report.counts.entries),
      String(report.counts.dated_entries),
      report.counts.max_words === null ? "-" : String(report.counts.max_words),
      String(report.timings_ms.total),
      report.verdict,
    ]);
    const header = ["feed", "http", "entries", "dated", "max words", "total ms", "verdict"];
    const widths = header.map((value, column) => Math.max(
      value.length,
      ...rows.map(row => row[column]!.length),
    ));
    const formatRow = (row: readonly string[]) => row.map((value, column) => value.padEnd(widths[column]!)).join(" | ");
    stderr(formatRow(header));
    stderr(widths.map(width => "-".repeat(width)).join("-+-"));
    for (const row of rows) stderr(formatRow(row));

    const evidenceCounts = new Map<string, number>([
      ["json-ld", 0],
      ["configured-marker", 0],
      ["none", 0],
      ["not-observed", 0],
    ]);
    for (const report of reports) {
      for (const sample of report.samples) {
        evidenceCounts.set(
          sample.paywall_evidence,
          (evidenceCounts.get(sample.paywall_evidence) ?? 0) + 1,
        );
      }
    }
    stderr(
      `paywall evidence: json-ld=${evidenceCounts.get("json-ld") ?? 0} `
      + `configured-marker=${evidenceCounts.get("configured-marker") ?? 0} `
      + `none=${evidenceCounts.get("none") ?? 0} `
      + `not-observed=${evidenceCounts.get("not-observed") ?? 0}`,
    );
  }

  if (logLevel === "DEBUG") {
    for (const report of reports) {
      report.samples.forEach((sample, index) => {
        const words = sample.diagnostics?.quality?.word_count ?? null;
        stderr(
          `article ${index + 1} ${report.feed_id}: readable=${sample.readable} dated=${sample.dated ?? false} `
          + `paywall=${sample.paywall ?? false} evidence=${sample.paywall_evidence} `
          + `http=${sample.diagnostics?.http_status ?? "-"} words=${visible(words)} `
          + `fetch_ms=${sample.diagnostics?.fetch_ms ?? "-"} extract_ms=${sample.diagnostics?.extract_ms ?? "-"}`,
        );
      });
    }
  } else if (logLevel === "INFO") {
    for (const report of reports) {
      if (report.verdict === "pass" && !report.samples.some(sample => sample.paywall === true)) continue;
      report.samples.forEach((sample, index) => {
        stderr(
          `article ${index + 1} ${report.feed_id}: readable=${sample.readable} dated=${sample.dated ?? false} `
          + `paywall=${sample.paywall ?? false} evidence=${sample.paywall_evidence}`,
        );
      });
    }
  }
  stderr(`failed/total: ${failedCount}/${totalCount}`);
}

export function writeJsonSummary(
  stdout: (line: string) => void,
  reports: readonly FeedProbeReport[],
): void {
  const passed = reports.filter(report => report.passed).length;
  const summary = FeedProbeReportSummarySchema.parse({
    version: reports[0]?.version ?? FEED_PROBE_VERSION,
    total: reports.length,
    passed,
    failed: reports.length - passed,
    reports: [...reports],
  });
  stdout(JSON.stringify(summary));
}
