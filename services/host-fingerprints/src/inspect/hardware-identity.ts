/** Which named cache entries and uptime reading describe this hardware? */
import type { ServiceConfig } from "../config";
import type { Inspection } from "./bounded-input";
import { readInput, unavailable } from "./bounded-input";

export async function collectHardware(config: ServiceConfig, context: Inspection) {
  let l3: number | null = null;
  for (const index of config.cache_indices) {
    const root = `/sys/devices/system/cpu/cpu0/cache/index${index}`;
    if ((await readInput(`${root}/level`, config, context))?.trim() !== "3") continue;
    const size = (await readInput(`${root}/size`, config, context))?.trim();
    const match = size?.match(/^(\d+)([KM]?)$/);
    if (match) {
      const bytes = Number(match[1]) * (match[2] === "M" ? 1024 ** 2 : match[2] === "K" ? 1024 : 1);
      if (Number.isSafeInteger(bytes)) l3 = bytes;
    }
    break;
  }
  const uptime = (await readInput("/proc/uptime", config, context))?.trim().split(/\s+/)[0];
  const seconds = uptime && /^\d+(?:\.\d+)?$/.test(uptime) ? Number(uptime) : NaN;
  return {
    l3_cache_bytes: l3 ?? unavailable(context, "l3_cache_bytes", "cache_unavailable"),
    boot_seconds: Number.isFinite(seconds) && seconds >= 0 ? seconds : unavailable(context, "boot_seconds", "uptime_unavailable"),
  };
}
