/** Who owns optional native cache work, its shared capacity bound and service shutdown? */
import type { ProbeContext } from "../probe/proc-reader";
import type { OwnedProcess } from "../task-profile/profile-schema";
import { CacheProbeConfigSchema } from "./cache-config";
import type { CacheProbeConfig } from "./cache-config";
import { refuseCacheCounters, startCacheCounters, stoppedCounterSession } from "./cache-counters";
import type { CounterSession } from "./cache-counters";
import { measureWorkingSetLatency, refuseCacheLatency } from "./working-set-latency";

export class CacheProbeController {
  private readonly config: CacheProbeConfig;
  private readonly cancellation = new AbortController();
  private readonly operations = new Set<Promise<unknown>>();

  constructor(
    config: CacheProbeConfig, private readonly maxProcBytes: number,
    private readonly context: ProbeContext = {},
  ) {
    this.config = CacheProbeConfigSchema.parse(config);
  }

  private retain<T>(operation: Promise<T>): Promise<T> {
    this.operations.add(operation);
    const release = () => { this.operations.delete(operation); };
    operation.then(release, release);
    return operation;
  }

  async startCounters(target: OwnedProcess, signal?: AbortSignal): Promise<CounterSession> {
    if (!this.config.counters.enabled) return startCacheCounters(this.config, target, this.maxProcBytes, this.context);
    if (this.cancellation.signal.aborted) return stoppedCounterSession(refuseCacheCounters(this.config, target, "cancelled"));
    if (this.operations.size >= this.config.max_concurrent) {
      return stoppedCounterSession(refuseCacheCounters(this.config, target, "concurrency_limit"));
    }
    const combined = signal ? AbortSignal.any([signal, this.cancellation.signal]) : this.cancellation.signal;
    const opening = startCacheCounters(this.config, target, this.maxProcBytes, this.context, combined);
    this.retain(opening.then(session => session.settled));
    return opening;
  }

  async measureLatency(signal?: AbortSignal) {
    if (!this.config.latency.enabled) return measureWorkingSetLatency(this.config, this.maxProcBytes, this.context);
    if (this.cancellation.signal.aborted) return refuseCacheLatency("cancelled");
    if (this.operations.size >= this.config.max_concurrent) return refuseCacheLatency("concurrency_limit");
    const combined = signal ? AbortSignal.any([signal, this.cancellation.signal]) : this.cancellation.signal;
    return this.retain(measureWorkingSetLatency(this.config, this.maxProcBytes, this.context, combined));
  }

  async shutdown(): Promise<void> {
    const pending = [...this.operations];
    this.cancellation.abort();
    const results = await Promise.allSettled(pending);
    const errors = results.filter(result => result.status === "rejected").map(result => result.reason);
    if (errors.length) throw new AggregateError(errors, "Cache probe service cleanup failed");
  }
}
