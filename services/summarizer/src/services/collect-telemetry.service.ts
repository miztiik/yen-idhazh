import fs from "node:fs";
import { execSync } from "node:child_process";
import type { SwapActivityMetrics } from "../schemas/export-all-schemas.js";

export function readServerPid(): number | null {
  try {
    const candidatePaths = [
      process.env.LLAMA_PID_FILE,
      ".llama_server.pid",
      "../../.llama_server.pid",
      "../.llama_server.pid",
      "/tmp/.llama_server.pid",
    ].filter(Boolean) as string[];

    for (const filePath of candidatePaths) {
      if (fs.existsSync(filePath)) {
        const pidStr = fs.readFileSync(filePath, "utf8").trim();
        if (pidStr) {
          const parsed = parseInt(pidStr, 10);
          if (!isNaN(parsed)) return parsed;
        }
      }
    }
  } catch {}
  return null;
}

export function getVmstatSwap(): { pswpin: number; pswpout: number } {
  try {
    const vmstat = fs.readFileSync("/proc/vmstat", "utf8");
    let pswpin = 0;
    let pswpout = 0;
    for (const line of vmstat.split("\n")) {
      if (line.startsWith("pswpin ")) pswpin = parseInt(line.split(/\s+/)[1], 10);
      if (line.startsWith("pswpout ")) pswpout = parseInt(line.split(/\s+/)[1], 10);
    }
    return { pswpin, pswpout };
  } catch {
    return { pswpin: 0, pswpout: 0 };
  }
}

export function getMemorySnapshot() {
  let swappiness = -1;
  try {
    swappiness = parseInt(fs.readFileSync("/proc/sys/vm/swappiness", "utf8").trim(), 10);
  } catch {}

  let swapTotal = 0;
  let swapFree = 0;
  try {
    const meminfo = fs.readFileSync("/proc/meminfo", "utf8");
    for (const line of meminfo.split("\n")) {
      if (line.startsWith("SwapTotal:")) swapTotal = parseInt(line.split(/\s+/)[1], 10) / 1024;
      if (line.startsWith("SwapFree:")) swapFree = parseInt(line.split(/\s+/)[1], 10) / 1024;
    }
  } catch {}

  const pid = readServerPid();
  let vmRss = 0;
  let vmSwap = 0;
  if (pid) {
    try {
      const status = fs.readFileSync(`/proc/${pid}/status`, "utf8");
      for (const line of status.split("\n")) {
        if (line.startsWith("VmRSS:")) vmRss = parseInt(line.split(/\s+/)[1], 10) / 1024;
        if (line.startsWith("VmSwap:")) vmSwap = parseInt(line.split(/\s+/)[1], 10) / 1024;
      }
    } catch {}
  }

  return {
    swappiness,
    pid,
    vmRssMb: Math.round(vmRss),
    vmSwapMb: Math.round(vmSwap),
    systemSwapUsedMb: Math.round(swapTotal - swapFree),
    systemSwapTotalMb: Math.round(swapTotal),
  };
}

export function detectL3Cache(): string {
  try {
    const cacheDir = "/sys/devices/system/cpu/cpu0/cache";
    if (fs.existsSync(cacheDir)) {
      for (const idx of fs.readdirSync(cacheDir)) {
        const levelPath = `${cacheDir}/${idx}/level`;
        if (fs.existsSync(levelPath) && fs.readFileSync(levelPath, "utf8").trim() === "3") {
          const raw = fs.readFileSync(`${cacheDir}/${idx}/size`, "utf8").trim();
          let bytes = 0;
          if (raw.endsWith("K")) bytes = parseInt(raw, 10) * 1024;
          else if (raw.endsWith("M")) bytes = parseInt(raw, 10) * 1024 * 1024;
          else bytes = parseInt(raw, 10);
          return `${(bytes / (1024 * 1024)).toFixed(2)} MB (${bytes} bytes)`;
        }
      }
    }
  } catch {}

  try {
    const out = execSync("lscpu", { encoding: "utf8" });
    const match = out.match(/L3 cache:\s*(.+)$/m);
    if (match) return match[1].trim();
  } catch {}

  return "Unknown";
}

export function finalizeSwapMetrics(
  initialPeakSwap: number,
  vmstatStart: { pswpin: number; pswpout: number }
): SwapActivityMetrics {
  const finalSnap = getMemorySnapshot();
  const peakServerSwap = Math.max(initialPeakSwap, finalSnap.vmSwapMb);
  const vmstatEnd = getVmstatSwap();

  const swapOutPages = Math.max(0, vmstatEnd.pswpout - vmstatStart.pswpout);
  const swapInPages = Math.max(0, vmstatEnd.pswpin - vmstatStart.pswpin);

  return {
    swappiness: finalSnap.swappiness,
    server_pid: finalSnap.pid,
    server_vm_rss_mb: finalSnap.vmRssMb,
    peak_server_swap_mb: peakServerSwap,
    final_server_swap_mb: finalSnap.vmSwapMb,
    system_swap_used_mb: finalSnap.systemSwapUsedMb,
    system_swap_total_mb: finalSnap.systemSwapTotalMb,
    swap_bytes_written_mb: Number(((swapOutPages * 4) / 1024).toFixed(2)),
    swap_bytes_read_mb: Number(((swapInPages * 4) / 1024).toFixed(2)),
  };
}