/** Who owns each bounded, transient HTTP task profile until it closes? */
import { randomUUID } from "node:crypto";
import { ProbeConfigSchema } from "../config";
import type { ProbeConfig } from "../config";
import type { ProbeContext } from "../probe/proc-reader";
import type { CacheProbeController } from "../cache-probe/cache-controller";
import type { CounterSession } from "../cache-probe/cache-counters";
import { CACHE_API_VERSION } from "../cache-probe/cache-schema";
import type { CacheCounters } from "../cache-probe/cache-schema";
import { ProcessPinError } from "../task-profile/process-stat";
import { startTaskProfile } from "../task-profile/task-profiler";
import type { TaskProfileResult, TaskProfileSession, TaskProfiling } from "../task-profile/task-profiler";
import type { TaskEndReason, TaskOutcome, TaskProfile } from "../task-profile/profile-schema";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "./task-command-schema";
import type {
  StartTaskProfile, StartTaskProfileResponse, StopTaskProfile, StopTaskProfileResponse,
} from "./task-command-schema";

type Entry = {
  abort: AbortController;
  starting: Promise<TaskProfileSession | null> | null;
  startupSettled: Promise<void>;
  session: TaskProfileSession | null;
  closing: Promise<TaskProfile> | null;
  result: TaskProfileResult | null;
  cacheStarting: Promise<CounterSession> | null;
  cache: CounterSession | null;
  cacheResult: CacheCounters | null;
  retainUntil: number | null;
};

export class TaskProfileCommandError extends Error {
  constructor(readonly status: 400 | 404 | 409 | 429 | 503, message: string) { super(message); }
}

export class TaskProfileManager {
  private readonly config: ProbeConfig;
  private readonly entries = new Map<string, Entry>();
  private stopping = false;
  private shutdownPromise: Promise<void> | undefined;

  constructor(private readonly options: {
    config: ProbeConfig; context?: ProbeContext; report: TaskProfiling["report"]; cache: CacheProbeController;
  }) { this.config = ProbeConfigSchema.parse(options.config); }

  private prune(): void {
    const now = performance.now();
    for (const [handle, entry] of this.entries) {
      if (entry.retainUntil !== null && now >= entry.retainUntil) this.entries.delete(handle);
    }
  }

  private reserve(): string {
    this.prune();
    if (this.entries.size >= this.config.task_profile.max_profile_handles) {
      const completed = [...this.entries].find(([, entry]) => entry.result !== null);
      if (completed) this.entries.delete(completed[0]);
    }
    if (this.entries.size >= this.config.task_profile.max_profile_handles) {
      throw new TaskProfileCommandError(429, "max_profile_handles is occupied by active profiles");
    }
    return randomUUID();
  }

  private closeEntry(entry: Entry, outcome: TaskOutcome, reason: TaskEndReason): Promise<TaskProfile> {
    entry.closing ??= (async () => {
      const session = entry.session ?? await entry.starting;
      if (session === null) throw new Error("Enabled task profile has no collector");
      const results = await Promise.allSettled([
        session.close(outcome, reason),
        (async () => {
          const cache = entry.cache ?? await entry.cacheStarting;
          if (cache !== null) entry.cacheResult = await cache.close(outcome === "cancelled");
        })(),
      ]);
      const errors = results.filter(result => result.status === "rejected").map(result => result.reason);
      if (errors.length) throw new AggregateError(errors, "Task and cache profile cleanup failed");
      const profile = results[0]!;
      if (profile.status !== "fulfilled") throw new Error("Task profile closed without a result");
      return profile.value;
    })();
    return entry.closing;
  }

  async start(input: StartTaskProfile, signal?: AbortSignal): Promise<StartTaskProfileResponse> {
    if (this.stopping) throw new TaskProfileCommandError(503, "Host probe is stopping");
    if (!this.config.task_profile.enabled) return { status: "disabled", reason: "configured_off" };
    if (signal?.aborted) throw new TaskProfileCommandError(400, "Task profile start aborted");
    const handle = this.reserve();
    let finishStartup: () => void;
    const startupSettled = new Promise<void>(resolve => { finishStartup = resolve; });
    const entry: Entry = {
      abort: new AbortController(), starting: null, startupSettled, session: null, closing: null,
      result: null, retainUntil: null, cacheStarting: null, cache: null, cacheResult: null,
    };
    this.entries.set(handle, entry);
    try {
      entry.starting = startTaskProfile({
        config: this.config, context: this.options.context ?? {}, report: this.options.report,
        target: input.target, ...(input.server === undefined ? {} : { server: input.server }),
      }, input.identity, {
        signal: signal === undefined ? entry.abort.signal : AbortSignal.any([signal, entry.abort.signal]),
        expiresAfterMs: this.config.task_profile.profile_handle_ttl_ms,
      });
      const session = await entry.starting;
      if (session === null) throw new Error("Enabled task profile did not start");
      entry.session = session;
      const abortCacheStart = () => entry.abort.abort();
      signal?.addEventListener("abort", abortCacheStart, { once: true });
      let cache: CounterSession;
      try {
        if (signal?.aborted) abortCacheStart();
        entry.cacheStarting = this.options.cache.startCounters(input.target, entry.abort.signal);
        cache = await entry.cacheStarting;
        entry.cache = cache;
      } finally { signal?.removeEventListener("abort", abortCacheStart); }
      void session.settled.then(async original => {
        let result = original;
        try { entry.cacheResult = await cache.close("error" in result || result.profile.outcome === "cancelled"); }
        catch (error) {
          result = { error: new AggregateError("error" in result ? [result.error, error] : [error], "Cache counter cleanup failed") };
        }
        entry.result = result;
        entry.retainUntil = performance.now() + this.config.task_profile.profile_handle_ttl_ms;
        if ("error" in result) console.error(JSON.stringify({ event: "task_profile_failed", error: result.error.name }));
      });
      if (this.stopping || signal?.aborted) throw new TaskProfileCommandError(400, "Task profile start aborted");
      return StartTaskProfileResponseSchema.parse({
        status: "started", handle, expires_at: session.expires_at, target: session.target,
        cache_counters: cache.initial ?? {
          version: CACHE_API_VERSION, kind: "last_level_cache_counters", status: "started",
          measurement_obtained: false, target: input.target, events: this.config.cache_probe.counters.events,
        },
      });
    } catch (error) {
      try {
        if (entry.session !== null) await this.closeEntry(entry, "cancelled", this.stopping ? "service_stopped" : "start_aborted");
      } catch (cleanup) {
        throw new AggregateError([error, cleanup], "Task profile startup and cleanup failed");
      } finally { this.entries.delete(handle); }
      if (this.stopping || signal?.aborted) throw new TaskProfileCommandError(400, "Task profile start aborted");
      if (error instanceof ProcessPinError) throw new TaskProfileCommandError(409, error.message);
      throw error;
    } finally { finishStartup!(); }
  }

  async stop(input: StopTaskProfile): Promise<StopTaskProfileResponse> {
    if (!this.config.task_profile.enabled) return { status: "disabled", reason: "configured_off" };
    this.prune();
    const entry = this.entries.get(input.handle);
    if (entry === undefined) throw new TaskProfileCommandError(404, "Unknown or removed task profile handle");
    const profile = await this.closeEntry(entry, input.outcome, "explicit_stop");
    return StopTaskProfileResponseSchema.parse({
      status: "stopped", handle: input.handle, end_reason: profile.end_reason, profile,
      cache_counters: entry.cacheResult,
    });
  }

  shutdown(): Promise<void> {
    this.shutdownPromise ??= (async () => {
      this.stopping = true;
      const entries = [...this.entries.values()];
      for (const entry of entries) entry.abort.abort();
      const results = await Promise.allSettled(entries.map(async entry => {
        await entry.startupSettled;
        if (entry.session !== null) await this.closeEntry(entry, "cancelled", "service_stopped");
      }));
      this.entries.clear();
      const errors = results.filter(result => result.status === "rejected").map(result => result.reason);
      if (errors.length) throw new AggregateError(errors, "Task profile service cleanup failed");
    })();
    return this.shutdownPromise;
  }
}
