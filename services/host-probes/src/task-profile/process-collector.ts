/** Which bounded CPU and RAM observations belong to one pinned process throughout a task? */
import type { Observation } from "../probe/proc-reader";
import { calculateCounterDifference } from "./counter-difference";
import { calculateProcessCpu } from "./process-cpu";
import { readProcessMemory, unavailableProcess } from "./process-memory";
import { readPinnedProcess } from "./process-stat";
import type { ProcessCpuCounters } from "./process-stat";
import type {
  CollectorInput, OwnedProcess, ProcessSample, ProcessSummary, TaskEndReason, TaskUnavailableReason,
} from "./profile-schema";

type Point = { at: number; cpu: Observation<ProcessCpuCounters, TaskUnavailableReason>; sample: ProcessSample };

export class ProcessCollector {
  private readonly history: Point[] = [];
  private opening: Point | undefined;
  private closing: Point | undefined;
  private previous: ProcessCpuCounters | undefined;
  private identityFailure: TaskUnavailableReason | null = null;
  private observedIdentityReason: TaskUnavailableReason | null = null;
  private cpuFailure: TaskUnavailableReason | null = null;
  private rssMax: number | null = null;
  private cpuMin: number | null = null;
  private cpuMax: number | null = null;

  constructor(
    private readonly input: CollectorInput,
    readonly pin: Observation<OwnedProcess, TaskUnavailableReason>,
    private readonly pid: number | null,
    private readonly scratch: Buffer,
  ) {}

  get ownerEndReason(): TaskEndReason | null {
    return this.identityFailure === "process_exited" ? "owner_exited"
      : this.identityFailure === "pid_reused" ? "pid_reused" : null;
  }

  get identityReason(): TaskUnavailableReason | null { return this.identityFailure ?? this.observedIdentityReason; }

  capture(): ProcessSample {
    const { config, max_proc_bytes, context, clock_ticks_per_second } = this.input;
    const stat = this.pin.reason !== null ? this.pin
      : this.identityFailure !== null ? { value: null, reason: this.identityFailure }
      : readPinnedProcess(this.pin.value, max_proc_bytes, context, this.scratch);
    const at = performance.now();
    this.observedIdentityReason = stat.reason;
    let cpu = stat.reason === null ? stat.value.cpu : { value: null, reason: stat.reason };
    const memory = !config.memory_enabled ? unavailableProcess(this.pid, this.pin.value?.start_ticks ?? null, "configured_off")
      : this.pin.reason !== null ? unavailableProcess(this.pid, null, this.pin.reason)
      : this.identityFailure !== null ? unavailableProcess(this.pid, this.pin.value.start_ticks, this.identityFailure)
      : readProcessMemory(this.pin.value, max_proc_bytes, context, this.scratch);
    const identityReason = stat.reason ?? memory.unavailable.major_faults;
    if (identityReason === "process_exited" || identityReason === "pid_reused") this.identityFailure = identityReason;
    if (cpu.reason === null) {
      if (this.previous && (cpu.value.user < this.previous.user || cpu.value.system < this.previous.system)) {
        this.cpuFailure = "counter_reset";
      }
      this.previous = cpu.value;
    }
    if (this.identityFailure !== null || this.cpuFailure !== null) {
      cpu = { value: null, reason: this.identityFailure ?? this.cpuFailure! };
    }
    const cutoff = at - config.cpu_window_ms;
    while (this.history.length > 1 && this.history[1]!.at <= cutoff) this.history.shift();
    const start = this.history[0];
    const interval_ms = start === undefined ? 0 : at - start.at;
    const window = calculateProcessCpu(start?.cpu ?? cpu, cpu, interval_ms, clock_ticks_per_second);
    const sample: ProcessSample = {
      ...memory,
      cpu_window: { interval_ms, full_window: interval_ms >= config.cpu_window_ms, cpu: window },
    };
    const point = { at, cpu, sample };
    this.opening ??= point;
    this.closing = point;
    this.history.push(point);
    if (this.history.length > config.max_retained_samples) this.history.shift();
    if (memory.memory_kb.rss !== null) this.rssMax = Math.max(this.rssMax ?? 0, memory.memory_kb.rss);
    if (window.reason === null) {
      this.cpuMin = Math.min(this.cpuMin ?? window.value.percent_one_core, window.value.percent_one_core);
      this.cpuMax = Math.max(this.cpuMax ?? window.value.percent_one_core, window.value.percent_one_core);
    }
    return sample;
  }

  summarize(): ProcessSummary {
    if (this.opening === undefined || this.closing === undefined) throw new Error("Process collector has no endpoints");
    const start = this.opening.sample;
    const closing = this.closing.sample;
    const faults = calculateCounterDifference(start.major_faults, closing.major_faults,
      start.unavailable.major_faults ?? closing.unavailable.major_faults ?? "missing_field");
    const unavailable: ProcessSummary["unavailable"] = {};
    if (faults.reason !== null) unavailable.major_faults_delta = faults.reason;
    if (this.rssMax === null) unavailable.sampled_rss_max_kb = closing.unavailable["memory_kb.rss"] ?? "missing_field";
    const cpu_interval_ms = this.closing.at - this.opening.at;
    const cpu = calculateProcessCpu(this.opening.cpu, this.closing.cpu, cpu_interval_ms, this.input.clock_ticks_per_second);
    if (this.cpuMin === null) {
      unavailable.sampled_cpu_min_percent_one_core = cpu.reason ?? "no_interval";
      unavailable.sampled_cpu_max_percent_one_core = unavailable.sampled_cpu_min_percent_one_core;
    }
    return {
      closing, sampled_rss_max_kb: this.rssMax, major_faults_delta: faults.value, unavailable,
      cpu_interval_ms, cpu, sampled_cpu_min_percent_one_core: this.cpuMin, sampled_cpu_max_percent_one_core: this.cpuMax,
    };
  }
}
