/** How does one item keep only the endpoint cells and periodic extrema it needs? */
import { KIB_BYTES, parseItemMemory } from "../probe/memory-probe";
import { readProcFile } from "../probe/proc-reader";
import { calculateCounterDifference } from "./counter-difference";
import { itemCpuShares, parseItemTicks } from "./item-window-cpu";
import { ITEM_WINDOW_VERSION } from "./item-window-schema";
import { readProcessMemory, unavailableProcess } from "./process-memory";
import { ProcessPinError, readPinnedProcess } from "./process-stat";
import { ItemWindowProfileSchema } from "./profile-schema";
import type { CollectorInput, ItemWindowProfile, OwnedProcess, TaskEndReason, TaskOutcome, TaskUnavailableReason } from "./profile-schema";

function bytes(kib: number | null): number | null {
  return kib !== null && Number.isSafeInteger(kib * KIB_BYTES) ? kib * KIB_BYTES : null;
}

function highest(a: number | null, b: number | null): number | null {
  return a === null ? b : b === null ? a : Math.max(a, b);
}

function load1m(text: string | null): number | null {
  const field = text?.trim().split(/\s+/, 1)[0];
  if (field === undefined || !/^\d+(?:\.\d+)?$/.test(field)) return null;
  const load = Number(field);
  return Number.isFinite(load) ? load : null;
}

export class ItemWindowCollector {
  private readonly scratch: Buffer;
  readonly target: OwnedProcess;
  private readonly opening: ReturnType<ItemWindowCollector["endpoint"]>;
  private previous: ReturnType<typeof parseItemTicks>;
  private busyMin: number | null = null;
  private busyMax: number | null = null;
  private availableMin: number | null = null;
  private ownerFailure: TaskEndReason | null = null;
  private closed: ItemWindowProfile | undefined;

  constructor(private readonly input: CollectorInput) {
    if (input.target === null) throw new Error("Item collection requires a pinned worker");
    this.target = input.target;
    this.scratch = Buffer.alloc(input.max_proc_bytes + 1);
    this.opening = this.endpoint();
    if (this.opening.workerReason !== null) throw new ProcessPinError(this.opening.workerReason);
    this.previous = this.opening.cpu;
  }

  get ownerEndReason(): TaskEndReason | null { return this.ownerFailure; }

  private noteOwner(reason: TaskUnavailableReason | null): void {
    if (reason === "pid_reused") this.ownerFailure = "pid_reused";
    if (reason === "process_exited") this.ownerFailure ??= "owner_exited";
  }

  private noteBusy(busy: number | undefined): void {
    if (busy === undefined) return;
    this.busyMin = Math.min(this.busyMin ?? busy, busy);
    this.busyMax = Math.max(this.busyMax ?? busy, busy);
  }

  private machine() {
    const { config, max_proc_bytes, context } = this.input;
    const cpu = parseItemTicks(readProcFile("stat", max_proc_bytes, context, this.scratch).value);
    const memory = parseItemMemory(config.machine_memory_enabled
      ? readProcFile("meminfo", max_proc_bytes, context, this.scratch).value ?? "" : "");
    const available = bytes(memory.available);
    if (available !== null) this.availableMin = Math.min(this.availableMin ?? available, available);
    return { cpu, memory, available };
  }

  private endpoint() {
    const { config, context, max_proc_bytes, server } = this.input;
    const machine = this.machine();
    const load = load1m(readProcFile("loadavg", max_proc_bytes, context, this.scratch).value);
    const workerIdentity = readPinnedProcess(this.target, max_proc_bytes, context, this.scratch);
    const worker = config.memory_enabled && workerIdentity.reason === null && this.ownerFailure === null
      ? readProcessMemory(this.target, max_proc_bytes, context, this.scratch)
      : unavailableProcess(this.target.pid, this.target.start_ticks, workerIdentity.reason ?? "configured_off");
    const workerReason = workerIdentity.reason ?? worker.unavailable.major_faults;
    this.noteOwner(workerReason ?? null);
    const extra = config.memory_enabled && server !== null
      ? readProcessMemory(server, max_proc_bytes, context, this.scratch)
      : unavailableProcess(null, null, config.memory_enabled ? "not_configured" : "configured_off");
    return {
      ...machine, load, worker,
      workerReason: workerIdentity.reason ?? (
        workerReason === "process_exited" || workerReason === "pid_reused" ? workerReason : null
      ),
      server: extra,
    };
  }

  poll(): void {
    if (this.closed !== undefined) return;
    const { context, max_proc_bytes } = this.input;
    const now = this.machine();
    this.noteBusy(itemCpuShares(this.previous, now.cpu)?.busy);
    this.previous = now.cpu;
    this.noteOwner(readPinnedProcess(this.target, max_proc_bytes, context, this.scratch).reason);
  }

  close(outcome: TaskOutcome, reason: TaskEndReason): ItemWindowProfile {
    if (this.closed !== undefined) return this.closed;
    const end = this.endpoint();
    const whole = itemCpuShares(this.opening.cpu, end.cpu);
    // The last poll-to-close segment was never part of the Python extrema.
    this.noteBusy(whole?.busy);
    const faults = calculateCounterDifference(this.opening.server.major_faults, end.server.major_faults, "missing_field");
    const end_reason = this.ownerEndReason ?? reason;
    this.closed = ItemWindowProfileSchema.parse({
      ...this.input.operation, version: ITEM_WINDOW_VERSION, identity: this.input.identity, end_reason,
      outcome: end_reason === "task_settled" || end_reason === "explicit_stop" ? outcome : "cancelled",
      cells: {
        cpu_busy_pct: whole?.busy ?? null, cpu_busy_min: this.busyMin, cpu_busy_max: this.busyMax,
        cpu_steal_pct: whole?.steal ?? null, load_1m: end.load,
        python_rss_bytes: bytes(end.worker.memory_kb.rss), python_rss_anon_bytes: bytes(end.worker.memory_kb.anon),
        llama_rss_bytes: bytes(end.server.memory_kb.rss), llama_rss_anon_bytes: bytes(end.server.memory_kb.anon),
        llama_rss_peak_bytes: bytes(highest(this.opening.server.memory_kb.hwm_lifetime, end.server.memory_kb.hwm_lifetime)),
        llama_major_faults: faults.value,
        os_mem_total_bytes: bytes(end.memory.total), os_mem_available_bytes: end.available,
        os_mem_cached_bytes: bytes(end.memory.cached), os_swap_free_bytes: bytes(end.memory.swap_free),
        os_swap_total_bytes: bytes(end.memory.swap_total), os_mem_available_min_bytes: this.availableMin,
      },
    });
    return this.closed;
  }
}
