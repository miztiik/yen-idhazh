/** What affinity and visible cgroup quota apply to the intended process? */
import { readlink } from "node:fs/promises";
import { posix } from "node:path";
import type { FingerprintTarget, ServiceConfig } from "../config";
import type { Inspection } from "./bounded-input";
import { hostPath, parseInteger, readInput, unavailable } from "./bounded-input";
import { parseCpuIds } from "./cpu-topology";

export async function pinFingerprintTarget(pid: number, config: ServiceConfig, context: Inspection = {}): Promise<FingerprintTarget | null> {
  if ((context.platform ?? process.platform) !== "linux") return null;
  const stat = await readInput(`/proc/${pid}/stat`, config, context);
  // Linux puts an unescaped process name in parentheses before field three.
  const end = stat?.lastIndexOf(") ") ?? -1;
  if (stat == null || end < 0 || !stat.startsWith(`${pid} (`)) return null;
  const fields = stat.slice(end + 2).trim().split(/\s+/);
  const start_ticks = fields[19];
  return start_ticks !== undefined && /^\d{1,20}$/.test(start_ticks)
    && /^[A-Za-z]$/.test(fields[0] ?? "") && !["Z", "X", "x"].includes(fields[0] ?? "")
    ? { pid, start_ticks } : null;
}

async function pinned(target: FingerprintTarget, config: ServiceConfig, context: Inspection) {
  return (await pinFingerprintTarget(target.pid, config, context))?.start_ticks === target.start_ticks;
}

async function sharesQuotaView(processRoot: string, context: Inspection) {
  if (processRoot === "/proc/self") return true;
  try {
    for (const namespace of ["cgroup", "mnt"]) {
      const self = await readlink(hostPath(context, `/proc/self/ns/${namespace}`));
      const target = await readlink(hostPath(context, `${processRoot}/ns/${namespace}`));
      if (target !== self) return false;
    }
    return true;
  } catch (error) {
    if (error instanceof Error && "code" in error
      && ["ENOENT", "EACCES", "EPERM", "EINVAL", "ENOTDIR"].includes(String(error.code))) return false;
    throw error;
  }
}

function unknownTarget(context: Inspection, reason: string) {
  return {
    cpu_allowed_processors: unavailable(context, "cpu_allowed_processors", reason),
    cpu_quota_cores: unavailable(context, "cpu_quota_cores", reason),
    cpu_quota_state: null,
    cpu_target_measured_at: null,
  };
}

export async function collectCapacity(
  ids: number[] | null, config: ServiceConfig, context: Inspection, target: FingerprintTarget | "self" | null,
) {
  if (target === null) return unknownTarget(context, "target_not_supplied");
  if (target !== "self" && !await pinned(target, config, context)) return unknownTarget(context, "target_pin_unavailable");
  const processRoot = target === "self" ? "/proc/self" : `/proc/${target.pid}`;
  const status = await readInput(`${processRoot}/status`, config, context);
  const affinity = parseCpuIds(status?.match(/^Cpus_allowed_list:\s*(.+)$/m)?.[1] ?? null, config.max_online_processors);
  const count = ids && affinity ? ids.filter((id) => affinity.includes(id)).length : 0;
  const sharedView = await sharesQuotaView(processRoot, context);
  const groups = sharedView ? await readInput(`${processRoot}/cgroup`, config, context) : null;
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
    unavailable(context, "cpu_quota_cores", sharedView ? "ancestor_quota_unavailable" : "target_quota_view_unavailable");
  }
  if (target !== "self") {
    if (!await pinned(target, config, context)) return unknownTarget(context, "target_pin_unavailable");
    if (groups !== null && (await readInput(`${processRoot}/cgroup`, config, context) !== groups
      || !await sharesQuotaView(processRoot, context))) {
      state = "unavailable";
      quota = unavailable(context, "cpu_quota_cores", "target_quota_view_changed");
    }
  }
  return {
    cpu_allowed_processors: count || unavailable(context, "cpu_allowed_processors", "affinity_unavailable"),
    cpu_quota_cores: quota, cpu_quota_state: state,
    cpu_target_measured_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  };
}
