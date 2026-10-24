/** How are optional LLC counters attached to one owned PID for an actual bounded interval? */
import { arch, release } from "node:os";
import { OwnedProcessSchema } from "../task-profile/profile-schema";
import type { OwnedProcess } from "../task-profile/profile-schema";
import type { ProbeContext } from "../probe/proc-reader";
import type { CacheProbeConfig } from "./cache-config";
import { CACHE_API_VERSION, CacheCountersSchema } from "./cache-schema";
import type { CacheCounters, CacheReason } from "./cache-schema";
import { startBoundedTool } from "./bounded-tool";
import { classifyPerfFailure, parsePerfCounters, unavailableCounter } from "./perf-output";
import { validateCounterTarget } from "./owned-target";

export type CounterSession = {
  initial: CacheCounters | null;
  close: (cancelled?: boolean) => Promise<CacheCounters>;
};
export async function startCacheCounters(
  config: CacheProbeConfig, rawTarget: OwnedProcess, maxProcBytes: number,
  context: ProbeContext = {}, signal?: AbortSignal,
): Promise<CounterSession> {
  const target = OwnedProcessSchema.parse(rawTarget);
  const base: CacheCounters = {
    version: CACHE_API_VERSION, kind: "last_level_cache_counters", status: "disabled",
    reason: "configured_off", measurement_obtained: false, target, host: null, interval: null,
    completion: null, scope: "existing_pid_threads_user_space_without_descendants",
    scaled: false, enabled_time_precision: "derived_from_running_percent_rounded_to_0.01_percent",
    events: config.counters.events.map(event => unavailableCounter(event, "configured_off")),
  };
  const unavailable = (reason: CacheReason): CacheCounters => CacheCountersSchema.parse({
    ...base, status: reason === "configured_off" ? "disabled" : "unavailable", reason,
    measurement_obtained: false, events: config.counters.events.map(event => unavailableCounter(event, reason)),
  });
  const stopped = (result: CacheCounters): CounterSession => ({ initial: result, close: async () => result });
  if (!config.counters.enabled) return stopped(unavailable("configured_off"));
  if ((context.platform ?? process.platform) !== "linux") return stopped(unavailable("unsupported_platform"));
  if (signal?.aborted) return stopped(unavailable("cancelled"));
  const refusal = validateCounterTarget(target, maxProcBytes, context);
  if (refusal) return stopped(unavailable(refusal));
  base.host = { platform: "linux", arch: arch(), release: release() };
  const tool = startBoundedTool("perf", [
    "stat", "--no-big-num", "--no-scale", "--no-inherit", "--no-metric-only",
    "--field-separator=;", `--event={${config.counters.events.join(",")}}`,
    `--pid=${target.pid}`, "--delay=-1", "--control=fd:0,1",
    `--timeout=${config.counters.max_duration_ms}`,
  ], {
    max_output_bytes: config.max_output_bytes,
    timeout_ms: config.counters.max_duration_ms + config.lifecycle_timeout_ms,
  }, signal);
  const started_at = new Date().toISOString(), started = performance.now();
  let finished_at = started_at, elapsed_ms = 0;
  const exited = tool.finished.then(output => {
    finished_at = new Date().toISOString();
    elapsed_ms = performance.now() - started;
    return output;
  });
  if (!await tool.control("enable", config.lifecycle_timeout_ms)) {
    if (tool.running) tool.cancel("timeout");
    const output = await exited;
    return stopped(unavailable(output.reason ?? classifyPerfFailure(output.stderr)));
  }
  const afterStart = validateCounterTarget(target, maxProcBytes, context);
  if (afterStart) {
    tool.cancel(afterStart);
    await exited;
    return stopped(unavailable(afterStart));
  }
  let closing: Promise<CacheCounters> | undefined;
  return {
    initial: null,
    close(cancelled = false) {
      closing ??= (async () => {
        let completion: CacheCounters["completion"] = "duration_limit";
        if (cancelled || signal?.aborted) { completion = "cancelled"; tool.cancel(); }
        else if (tool.running) {
          if (await tool.control("disable", config.lifecycle_timeout_ms)) {
            completion = "stopped";
            finished_at = new Date().toISOString();
            elapsed_ms = performance.now() - started;
            tool.interrupt();
          } else if (tool.running) tool.cancel("timeout");
        }
        const boundary = { started_at, finished_at, elapsed_ms };
        const output = await exited;
        base.interval = completion === "stopped" ? boundary : { started_at, finished_at, elapsed_ms };
        base.completion = completion;
        const refusal = validateCounterTarget(target, maxProcBytes, context);
        if (refusal) return unavailable(refusal);
        if (output.reason) return unavailable(output.reason);
        if (output.code !== 0) return unavailable(classifyPerfFailure(output.stderr));
        try {
          const events = parsePerfCounters(output.stderr, config.counters.events);
          const measured = events.some(event => event.support === "measured");
          return CacheCountersSchema.parse({
            ...base, events, status: measured ? "measured" : "unavailable",
            reason: measured ? null : events[0]!.reason, measurement_obtained: measured,
          });
        } catch { return unavailable("invalid_output"); }
      })();
      return closing;
    },
  };
}
