/** What affinity and tightest visible cgroup quota apply to this process? */
import { posix } from "node:path";
import type { ServiceConfig } from "../config";
import type { Inspection } from "./bounded-input";
import { parseInteger, readInput, unavailable } from "./bounded-input";
import { parseCpuIds } from "./cpu-topology";

export async function collectCapacity(ids: number[] | null, config: ServiceConfig, context: Inspection) {
  const status = await readInput("/proc/self/status", config, context);
  const affinity = parseCpuIds(status?.match(/^Cpus_allowed_list:\s*(.+)$/m)?.[1] ?? null, config.max_online_processors);
  const count = ids && affinity ? ids.filter((id) => affinity.includes(id)).length : 0;
  const groups = await readInput("/proc/self/cgroup", config, context);
  const lines = (groups ?? "").split("\n").map((line) => line.match(/^(\d+):([^:]*):(\/.*)$/));
  const v2 = lines.find((line) => line?.[1] === "0" && line[2] === "");
  const chosen = v2 ?? lines.find((line) => line?.[2]?.split(",").includes("cpu"));
  const path = chosen?.[3];
  let quota: number | null = null;
  let state: "finite" | "unlimited" | "unavailable" = "unavailable";
  if (path && !path.split("/").includes("..") && !path.includes("\0") && !path.includes("\\")) {
    const parts = path.split("/").filter(Boolean);
    if (parts.length <= config.max_cgroup_depth) {
      let valid = true;
      const base = v2 ? "/sys/fs/cgroup" : "/sys/fs/cgroup/cpu";
      for (let depth = parts.length; depth >= 0; depth--) {
        const node = posix.join(base, ...parts.slice(0, depth));
        let amount: number | null, period: number | null;
        if (v2) {
          const cells = (await readInput(`${node}/cpu.max`, config, context))?.trim().split(/\s+/);
          amount = cells?.[0] === "max" ? -1 :
            cells?.[0] && /^\d+$/.test(cells[0]) ? parseInteger(cells[0]) : null;
          period = cells?.length === 2 ? parseInteger(cells[1]) : null;
        } else {
          amount = parseInteger(await readInput(`${node}/cpu.cfs_quota_us`, config, context));
          period = parseInteger(await readInput(`${node}/cpu.cfs_period_us`, config, context));
        }
        if (amount === null || period === null || period <= 0 || (amount !== -1 && amount <= 0)) valid = false;
        else if (amount !== -1) quota = quota === null ? amount / period : Math.min(quota, amount / period);
      }
      if (valid) state = quota === null ? "unlimited" : "finite";
    }
  }
  if (state === "unavailable") {
    quota = null;
    unavailable(context, "cpu_quota_cores", "ancestor_quota_unavailable");
  }
  return {
    cpu_allowed_processors: count || unavailable(context, "cpu_allowed_processors", "affinity_unavailable"),
    cpu_quota_cores: quota, cpu_quota_state: state,
  };
}
