/** Which already-supported host observations do local benchmark tools read? */
import { z } from "zod";
import { loadConfig } from "../config";
import { readLinuxFile } from "../probe/proc-reader";
import { OwnedProcessSchema } from "../task-profile/profile-schema";
import { readProcessMemory } from "../task-profile/process-memory";
import { loadConfig as loadFingerprintConfig } from "@idhazh/host-fingerprints/config";
import { readInput } from "../../../host-fingerprints/src/inspect/bounded-input";
import { parseCpuModel } from "../../../host-fingerprints/src/inspect/cpu-model";

function keyValues(text: string | null) {
  return Object.fromEntries((text ?? "").trim().split("\n").flatMap(line => {
    const space = line.indexOf(" ");
    if (space <= 0) return [];
    const value = line.slice(space + 1);
    const integer = /^\d+$/.test(value) ? Number(value) : null;
    return [[line.slice(0, space), integer !== null && Number.isSafeInteger(integer) ? integer : value]];
  }));
}

const operation = z.enum(["cpu-model", "rss-peak", "cgroup"]).parse(Bun.argv[2]);
if (operation === "cpu-model") {
  const config = await loadFingerprintConfig();
  const cpu = process.platform === "linux" ? await readInput("/proc/cpuinfo", config, {}) : null;
  console.log(JSON.stringify(parseCpuModel(cpu, false).cpu_model));
} else {
  const config = await loadConfig();
  if (operation === "rss-peak") {
    const pin = OwnedProcessSchema.parse({ pid: Number(Bun.argv[3]), start_ticks: Bun.argv[4] });
    const memory = readProcessMemory(pin, config.max_proc_bytes, {});
    console.log(JSON.stringify(memory.memory_kb.hwm_lifetime));
  } else {
    const memory = z.enum(["on", "off"]).parse(Bun.argv[3]);
    const read = (name: "cpu.stat" | "cpu.pressure" | "memory.events" | "memory.peak") =>
      process.platform === "linux" ? readLinuxFile(`/sys/fs/cgroup/${name}`, config.max_proc_bytes).value : null;
    console.log(JSON.stringify({
      cpu_stat: keyValues(read("cpu.stat")), cpu_pressure: keyValues(read("cpu.pressure")),
      ...(memory === "off" ? {} : {
        memory_events: keyValues(read("memory.events")), memory_peak: read("memory.peak")?.trim() ?? null,
      }),
    }));
  }
}
