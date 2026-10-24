/** How do bounded rolling samples and whole-task endpoint measurements accumulate? */
import { calculateCpuPercentages, parseCpuCounters } from "../probe/cpu-sampler";
import type { CpuCounters } from "../probe/cpu-sampler";
import { parseMemoryInfo, parseVmstat } from "../probe/memory-probe";
import { readProcFile } from "../probe/proc-reader";
import type { Observation } from "../probe/proc-reader";
import { calculateCounterDifference } from "./counter-difference";
import { ProcessCollector } from "./process-collector";
import { ProcessPinError, readProcessIdentity } from "./process-stat";
import { TaskProfileSchema } from "./profile-schema";
import type { CollectorInput, OwnedProcess, TaskEndReason, TaskOutcome, TaskProfile, TaskSample, TaskUnavailableReason } from "./profile-schema";

type Point = { at: number; cpu: Observation<CpuCounters>; sample: TaskSample };

export class TaskCollector {
  private readonly scratch: Buffer;
  private readonly worker: ProcessCollector;
  private readonly server: ProcessCollector;
  private readonly opening: Point;
  private readonly history: Point[] = [];
  private readonly samples: TaskSample[] = [];
  private sampleCount = 0;
  private periodicCount = 0;
  private fullWindowCount = 0;
  private busyMin: number | null = null;
  private busyMax: number | null = null;
  private availableMin: number | null = null;
  private resetAt: number | null = null;
  private closed: TaskProfile | undefined;

  constructor(private readonly input: CollectorInput) {
    this.scratch = Buffer.alloc(input.max_proc_bytes + 1);
    const observed = readProcessIdentity(input.worker_pid, input.max_proc_bytes, input.context, this.scratch);
    const worker: Observation<OwnedProcess, TaskUnavailableReason> = input.target !== null
      ? { value: input.target, reason: null }
      : observed.reason !== null ? observed
      : { value: { pid: observed.value.pid, start_ticks: observed.value.start_ticks }, reason: null };
    this.worker = new ProcessCollector(input, worker, input.worker_pid, this.scratch);
    this.server = new ProcessCollector(input, input.server === null
      ? { value: null, reason: "not_configured" } : { value: input.server, reason: null }, input.server?.pid ?? null, this.scratch);
    this.opening = this.capture("opening");
    if (input.target !== null && this.worker.identityReason !== null) throw new ProcessPinError(this.worker.identityReason);
  }

  get target(): OwnedProcess | null { return this.worker.pin.value; }
  get ownerEndReason(): TaskEndReason | null { return this.worker.ownerEndReason; }

  private capture(phase: TaskSample["phase"]): Point {
    const { config, max_proc_bytes, context } = this.input;
    const text = readProcFile("stat", max_proc_bytes, context, this.scratch);
    const cpu = text.reason === null ? parseCpuCounters(text.value) : text;
    const at = performance.now();
    const first = this.history[0];
    const previous = this.history.at(-1);
    if (previous && calculateCpuPercentages(previous.cpu, cpu).reason === "counter_reset") this.resetAt = at;
    const elapsed_ms = first === undefined ? 0 : at - this.opening.at;
    const cutoff = at - config.cpu_window_ms;
    while (this.history.length > 1 && this.history[1]!.at <= cutoff) this.history.shift();
    const start = this.history[0];
    const interval_ms = start === undefined ? 0 : at - start.at;
    const windowCpu = this.resetAt !== null && start !== undefined && start.at < this.resetAt
      ? { value: null, reason: "counter_reset" as const }
      : calculateCpuPercentages(start?.cpu ?? cpu, cpu);
    const unavailable: TaskSample["unavailable"] = {};
    let memory_kb: TaskSample["memory_kb"] = { total: null, free: null, available: null };
    let vmstat_major_faults: number | null = null;
    if (config.memory_enabled) {
      const memoryText = readProcFile("meminfo", max_proc_bytes, context, this.scratch);
      const memory = parseMemoryInfo(memoryText.value ?? "");
      memory_kb = memory.value;
      for (const name of ["total", "free", "available"] as const) {
        const reason = memoryText.reason ?? memory.unavailable[name];
        if (reason) unavailable[`memory_kb.${name}`] = reason;
      }
      const vmstatText = readProcFile("vmstat", max_proc_bytes, context, this.scratch);
      const vmstat = vmstatText.reason === null ? parseVmstat(vmstatText.value) : vmstatText;
      vmstat_major_faults = vmstat.value?.pgmajfault ?? null;
      if (vmstat.reason !== null) unavailable.vmstat_major_faults = vmstat.reason;
    } else {
      for (const name of ["total", "free", "available"]) unavailable[`memory_kb.${name}`] = "configured_off";
      unavailable.vmstat_major_faults = "configured_off";
    }
    const sample: TaskSample = {
      phase, observed_at: new Date().toISOString(), elapsed_ms,
      cpu_window: { interval_ms, full_window: interval_ms >= config.cpu_window_ms, cpu: windowCpu },
      memory_kb, vmstat_major_faults,
      processes: { worker: this.worker.capture(), server: this.server.capture() },
      unavailable,
    };
    const point = { at, cpu, sample };
    this.history.push(point);
    if (this.history.length > config.max_retained_samples) this.history.shift();
    this.samples.push(sample);
    if (this.samples.length > config.max_retained_samples) this.samples.shift();
    this.sampleCount++;
    if (phase === "poll") this.periodicCount++;
    if (phase !== "opening" && windowCpu.reason === null) {
      const busy = Math.min(100, windowCpu.value.user + windowCpu.value.system);
      this.busyMin = this.busyMin === null ? busy : Math.min(this.busyMin, busy);
      this.busyMax = this.busyMax === null ? busy : Math.max(this.busyMax, busy);
      if (sample.cpu_window.full_window) this.fullWindowCount++;
    }
    if (memory_kb.available !== null) {
      this.availableMin = this.availableMin === null ? memory_kb.available : Math.min(this.availableMin, memory_kb.available);
    }
    return point;
  }

  poll(): void {
    if (this.closed === undefined) this.capture("poll");
  }

  close(outcome: TaskOutcome, end_reason: TaskEndReason = "task_settled"): TaskProfile {
    if (this.closed !== undefined) return this.closed;
    const end = this.capture("closing");
    const unavailable: TaskProfile["unavailable"] = {};
    const faults = calculateCounterDifference(this.opening.sample.vmstat_major_faults, end.sample.vmstat_major_faults,
      this.opening.sample.unavailable.vmstat_major_faults ?? end.sample.unavailable.vmstat_major_faults ?? "missing_field");
    if (faults.reason !== null) unavailable.machine_major_faults_delta = faults.reason;
    if (this.availableMin === null) unavailable.machine_available_min_kb = end.sample.unavailable["memory_kb.available"] ?? "missing_field";
    if (this.busyMin === null) {
      unavailable.sampled_busy_min_percent = end.sample.cpu_window.cpu.reason ?? "no_ticks";
      unavailable.sampled_busy_max_percent = unavailable.sampled_busy_min_percent;
    }
    this.closed = TaskProfileSchema.parse({
      identity: this.input.identity, collector: "worker_thread",
      outcome: this.ownerEndReason !== null
        || ["expired", "service_stopped", "start_aborted"].includes(end_reason) ? "cancelled" : outcome,
      end_reason: this.ownerEndReason ?? end_reason,
      started_at: this.opening.sample.observed_at, finished_at: end.sample.observed_at,
      elapsed_ms: end.sample.elapsed_ms, config: this.input.config,
      process_clock_ticks_per_second: this.input.clock_ticks_per_second,
      sample_count: this.sampleCount, periodic_sample_count: this.periodicCount, full_window_count: this.fullWindowCount,
      cpu: this.resetAt !== null ? { value: null, reason: "counter_reset" } : calculateCpuPercentages(this.opening.cpu, end.cpu),
      sampled_busy_min_percent: this.busyMin, sampled_busy_max_percent: this.busyMax,
      machine_available_min_kb: this.availableMin, machine_major_faults_delta: faults.value,
      processes: { worker: this.worker.summarize(), server: this.server.summarize() },
      unavailable, samples: this.samples,
    });
    return this.closed;
  }
}
