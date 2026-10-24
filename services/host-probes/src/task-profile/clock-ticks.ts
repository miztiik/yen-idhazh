/** What Linux clock-tick rate converts process counters to CPU milliseconds? */
import { execFile } from "node:child_process";
import type { ProbeConfig } from "../config";
import type { ClockTicks } from "./profile-schema";

// POSIX getconf's fixed executable and variable identify the operating-system protocol.
const GETCONF_PATH = "/usr/bin/getconf";
const CLOCK_TICK_VARIABLE = "CLK_TCK";
let clockTicks: Promise<ClockTicks> | undefined;

export function parseClockTicks(text: string): ClockTicks {
  const value = Number(text.trim());
  return /^\d+$/.test(text.trim()) && Number.isSafeInteger(value) && value > 0
    ? { value, reason: null } : { value: null, reason: "invalid_data" };
}

export function resolveClockTicks(config: ProbeConfig): Promise<ClockTicks> {
  if (!config.task_profile.enabled) return Promise.resolve({ value: null, reason: "configured_off" });
  clockTicks ??= process.platform !== "linux"
    ? Promise.resolve({ value: null, reason: "unsupported_platform" })
    : new Promise<ClockTicks>((resolve, reject) => {
      execFile(GETCONF_PATH, [CLOCK_TICK_VARIABLE], {
        encoding: "utf8", timeout: config.task_profile.lifecycle_timeout_ms, maxBuffer: config.max_proc_bytes,
      }, (error, stdout) => {
        if (error === null) { resolve(parseClockTicks(stdout)); return; }
        if (error.code === "ERR_CHILD_PROCESS_STDIO_MAXBUFFER") {
          resolve({ value: null, reason: "too_large" });
        } else if (error.killed || typeof error.code === "number"
          || ["ENOENT", "EACCES", "EPERM"].includes(String(error.code))) {
          resolve({ value: null, reason: "clock_ticks_unavailable" });
        } else reject(new Error("Cannot resolve Linux process clock ticks", { cause: error }));
      });
    });
  return clockTicks;
}
