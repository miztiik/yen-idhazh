/** Which exact LLC events and scheduling times did perf stat actually report? */
import { CacheCounterSchema } from "./cache-schema";
import type { CacheCounter, CacheEvent, CacheReason } from "./cache-schema";

export function unavailableCounter(event: CacheEvent, reason: CacheReason): CacheCounter {
  return CacheCounterSchema.parse({
    event, support: reason === "event_unsupported" ? "unsupported" : reason === "not_counted" ? "not_counted" : "unavailable",
    reason, count: null, time_running_ns: null, time_enabled_ns_estimate: null,
    running_percent: null, multiplexing: "unknown",
  });
}

export function classifyPerfFailure(output: string): CacheReason {
  if (/perf not found for kernel|you may need to install.*linux-tools/i.test(output)) return "tool_missing";
  if (/permission|access to performance monitoring|perf_event_paranoid|operation not permitted/i.test(output)) return "permission_denied";
  if (/not supported|no such device|cannot find pmu|event syntax error|unknown tracepoint/i.test(output)) return "event_unsupported";
  return "tool_failed";
}

export function parsePerfCounters(output: string, events: readonly CacheEvent[]): CacheCounter[] {
  const found = new Map<CacheEvent, CacheCounter>();
  for (const line of output.split("\n").map(line => line.trim()).filter(Boolean)) {
    // perf's control messages and comment header are not counter rows.
    if (line.startsWith("#") || /^(Events (enabled|disabled)|Control fd closed)$/.test(line)) continue;
    const cells = line.split(";").map(cell => cell.trim());
    const event = events.find(event => event === cells[2]);
    // Later columns are perf's derived metrics; they do not define or replace raw event counts.
    if (!event || found.has(event) || cells.length < 5 || cells[1] !== "") throw new Error("Invalid perf counter output");
    if (cells[0] === "<not supported>" || cells[0] === "<not counted>") {
      found.set(event, unavailableCounter(event, cells[0] === "<not supported>" ? "event_unsupported" : "not_counted"));
      continue;
    }
    if (!/^\d+$/.test(cells[0]!) || !/^\d+$/.test(cells[3]!)
      || !/^\d+(?:\.\d{1,2})?$/.test(cells[4]!)) throw new Error("Invalid perf counter units or numbers");
    const count = Number(cells[0]), running = Number(cells[3]), percent = Number(cells[4]);
    found.set(event, CacheCounterSchema.parse({
      event, support: "measured", reason: null, count,
      time_running_ns: running, time_enabled_ns_estimate: running / (percent / 100),
      running_percent: percent, multiplexing: percent < 100 ? "reported" : "not_reported",
    }));
  }
  if (found.size !== events.length) throw new Error("Missing perf event output");
  return events.map(event => found.get(event)!);
}
