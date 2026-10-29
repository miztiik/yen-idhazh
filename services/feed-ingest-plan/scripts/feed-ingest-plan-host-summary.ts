/** How does the planner report its actual host fingerprint without a live task profile? */
import { WorkflowHostFingerprintSchema } from "./feed-ingest-plan-host-fingerprint";
import { escapeMarkdown } from "../src/reporting/markdown-format";
import { measurement } from "./feed-ingest-plan-resource-values";

const BYTES_PER_MIB = 2 ** 20;

export function formatHostFingerprintSummary(input: unknown) {
  const evidence = input === undefined ? undefined : WorkflowHostFingerprintSchema.parse(input);
  const rows: { measurement: string; value: string }[] = [];
  let notice = "Host fingerprint unavailable (no evidence was saved)";
  const host = evidence?.host;
  if (host?.status === "recorded") {
    const { row, unavailable } = host;
    const reason = (field: string) => unavailable[field] ?? unavailable.platform ?? "not observed";
    const cpu = row.cpu_model ?? `Unavailable (${unavailable.cpu_model ?? unavailable.platform ?? "not observed"})`;
    const cache = row.l3_cache_bytes === null ? `Unavailable (${reason("l3_cache_bytes")})`
      : `${(row.l3_cache_bytes / BYTES_PER_MIB).toFixed(2)} MiB`;
    const capacity = measurement(row.machine_memory_total_mib, "MiB", reason("machine_memory_total_mib"));
    rows.push(
      { measurement: "CPU", value: cpu },
      { measurement: "Logical / allowed processors",
        value: `${measurement(row.cpu_logical_processors, "processors", reason("cpu_logical_processors"))} / ${measurement(row.cpu_allowed_processors, "processors", reason("cpu_allowed_processors"))}` },
      { measurement: "L3 cache", value: cache },
      { measurement: "Total machine RAM capacity", value: capacity },
      { measurement: "Measurement time (UTC)",
        value: row.measured_at === null ? "Unavailable" : row.measured_at },
    );
    notice = `Host fingerprint recorded: ${cpu}; ${measurement(row.cpu_allowed_processors, "allowed processors", reason("cpu_allowed_processors"))}; L3 ${cache}; total RAM ${capacity}`;
  } else {
    const status = host?.status ?? "unavailable";
    const reason = host?.reason ?? "no host evidence was saved";
    rows.push({ measurement: "Collection", value: `${status} (${reason})` });
    notice = `Host fingerprint ${status} (${reason})`;
  }
  return {
    notice,
    summary: [
      "## Table G - Host fingerprint", "",
      "| Id | Measurement | Recorded value |", "| --- | --- | --- |",
      ...rows.map((entry, index) =>
        `| G${index + 1} | ${escapeMarkdown(entry.measurement)} | ${escapeMarkdown(entry.value)} |`),
      "",
    ].join("\n"),
  };
}
