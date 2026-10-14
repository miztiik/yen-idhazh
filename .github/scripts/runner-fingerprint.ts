// scripts/runner-fingerprint.ts
import fs from "node:fs";
import os from "node:os";
import { performance } from "node:perf_hooks";

export interface HostFingerprint {
  run_id: string;
  job: string;
  shard: string;
  cpu_model: string;
  cpu_vendor: string;
  cpu_family: string;
  cpu_model_number: string;
  cpu_stepping: string;
  microcode: string;
  cpu_physical_cores: number;
  cpu_logical_processors: number;
  cpu_allowed_processors: number;
  cpu_quota_cores: number | string;
  cpu_quota_state: "unmetered" | "quota_enforced" | "unknown";
  cpu_target_measured_at: string;
  l3_cache_bytes: number;
  cpu_observed_mhz: number;
  cpu_reported_max_mhz: number;
  flags: string[];
  boot_seconds: number;
  memcpy_gib_s: number;
  memcpy_probe_mib: number;
  vm_size: string;
  vm_location: string;
  vm_zone: string;
  vm_fault_domain: string;
  runner_name: string;
  measured_at: string;
}

function parseCpuInfo(): Record<string, string> {
  const result: Record<string, string> = {};
  try {
    const data = fs.readFileSync("/proc/cpuinfo", "utf8");
    for (const line of data.split("\n")) {
      const [key, value] = line.split(":").map((s) => s.trim());
      if (key && value && !result[key]) {
        result[key] = value;
      }
    }
  } catch {
    // Non-Linux or restricted fallback
  }
  return result;
}

function getL3CacheBytes(): number {
  try {
    const cacheDir = "/sys/devices/system/cpu/cpu0/cache";
    if (fs.existsSync(cacheDir)) {
      const indexes = fs.readdirSync(cacheDir);
      for (const idx of indexes) {
        const levelPath = `${cacheDir}/${idx}/level`;
        if (fs.existsSync(levelPath) && fs.readFileSync(levelPath, "utf8").trim() === "3") {
          const rawSize = fs.readFileSync(`${cacheDir}/${idx}/size`, "utf8").trim();
          if (rawSize.endsWith("K")) return parseInt(rawSize) * 1024;
          if (rawSize.endsWith("M")) return parseInt(rawSize) * 1024 * 1024;
          return parseInt(rawSize);
        }
      }
    }
  } catch {}
  return 0;
}

function getCpuQuota(): { quotaCores: number | string; quotaState: "unmetered" | "quota_enforced" | "unknown" } {
  try {
    // cgroup v2
    if (fs.existsSync("/sys/fs/cgroup/cpu.max")) {
      const [quota, period] = fs.readFileSync("/sys/fs/cgroup/cpu.max", "utf8").trim().split(" ");
      if (quota === "max") return { quotaCores: "unmetered", quotaState: "unmetered" };
      return { quotaCores: Number((parseInt(quota) / parseInt(period)).toFixed(2)), quotaState: "quota_enforced" };
    }
    // cgroup v1
    if (fs.existsSync("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")) {
      const quota = parseInt(fs.readFileSync("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "utf8").trim());
      const period = parseInt(fs.readFileSync("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "utf8").trim());
      if (quota < 0) return { quotaCores: "unmetered", quotaState: "unmetered" };
      return { quotaCores: Number((quota / period).toFixed(2)), quotaState: "quota_enforced" };
    }
  } catch {}
  return { quotaCores: "unknown", quotaState: "unknown" };
}

function getAllowedProcessors(): number {
  try {
    const status = fs.readFileSync("/proc/self/status", "utf8");
    const match = status.match(/^Cpus_allowed_list:\s*(.+)$/m);
    if (match?.[1]) {
      const ranges = match[1].split(",");
      let count = 0;
      for (const r of ranges) {
        const [start, end] = r.split("-").map(Number);
        count += end !== undefined ? end - start + 1 : 1;
      }
      return count;
    }
  } catch {}
  return os.cpus().length;
}

function benchmarkMemcpy(probeMib = 64): number {
  const sizeBytes = probeMib * 1024 * 1024;
  const src = Buffer.alloc(sizeBytes, 0x5a);
  const dst = Buffer.alloc(sizeBytes);
  const iterations = 25;
  const start = performance.now();
  for (let i = 0; i < iterations; i++) {
    src.copy(dst);
  }
  const elapsedSeconds = (performance.now() - start) / 1000;
  const totalGiB = (iterations * sizeBytes) / (1024 ** 3);
  return Number((totalGiB / elapsedSeconds).toFixed(2));
}

async function getVmMetadata() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 600); // Fail fast if IMDS blocked
  try {
    const res = await fetch("http://169.254.169.254/metadata/instance?api-version=2021-02-01", {
      headers: { Metadata: "true" },
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (res.ok) {
      const data: any = await res.json();
      return {
        vm_size: data.compute?.vmSize || "Azure_VM",
        vm_location: data.compute?.location || "unknown",
        vm_zone: data.compute?.zone || "unknown",
        vm_fault_domain: data.compute?.platformFaultDomain || "unknown",
      };
    }
  } catch {}

  let dmiProduct = "unknown";
  try {
    dmiProduct = fs.readFileSync("/sys/class/dmi/id/product_name", "utf8").trim();
  } catch {}

  return {
    vm_size: dmiProduct !== "unknown" ? dmiProduct : "GitHub-Standard-Runner",
    vm_location: process.env.RUNNER_ENVIRONMENT || "github-hosted",
    vm_zone: "n/a",
    vm_fault_domain: "n/a",
  };
}

async function collectRunnerData(): Promise<HostFingerprint> {
  const cpuInfo = parseCpuInfo();
  const cpus = os.cpus();
  const quota = getCpuQuota();
  const vm = await getVmMetadata();
  const probeMib = 64;

  let maxMhz = 0;
  try {
    maxMhz = Number((parseInt(fs.readFileSync("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "utf8").trim()) / 1000).toFixed(2));
  } catch {
    maxMhz = cpus[0]?.speed || 0;
  }

  const flags = cpuInfo["flags"] ? cpuInfo["flags"].split(" ") : [];

  return {
    run_id: process.env.GITHUB_RUN_ID || "local-run",
    job: process.env.GITHUB_JOB || "manual-job",
    shard: process.env.SHARD_ID || "1/1",
    cpu_model: cpuInfo["model name"] || cpus[0]?.model || "unknown",
    cpu_vendor: cpuInfo["vendor_id"] || "unknown",
    cpu_family: cpuInfo["cpu family"] || "unknown",
    cpu_model_number: cpuInfo["model"] || "unknown",
    cpu_stepping: cpuInfo["stepping"] || "unknown",
    microcode: cpuInfo["microcode"] || "unknown",
    cpu_physical_cores: parseInt(cpuInfo["cpu cores"] || "1", 10),
    cpu_logical_processors: cpus.length,
    cpu_allowed_processors: getAllowedProcessors(),
    cpu_quota_cores: quota.quotaCores,
    cpu_quota_state: quota.quotaState,
    cpu_target_measured_at: new Date().toISOString(),
    l3_cache_bytes: getL3CacheBytes(),
    cpu_observed_mhz: parseFloat(cpuInfo["cpu MHz"] || `${cpus[0]?.speed || 0}`),
    cpu_reported_max_mhz: maxMhz,
    flags: flags.filter((f) => ["avx", "avx2", "avx512f", "fma", "sse4_2"].includes(f)),
    boot_seconds: Math.floor(os.uptime()),
    memcpy_gib_s: benchmarkMemcpy(probeMib),
    memcpy_probe_mib: probeMib,
    vm_size: vm.vm_size,
    vm_location: vm.vm_location,
    vm_zone: vm.vm_zone,
    vm_fault_domain: vm.vm_fault_domain,
    runner_name: process.env.RUNNER_NAME || "local-runner",
    measured_at: new Date().toISOString(),
  };
}

function writeMarkdownSummary(data: HostFingerprint) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const markdown = `
### 🖥️ GitHub Runner Host Fingerprint

| Metric | Measured Value |
| :--- | :--- |
| **Runner Name** | \`${data.runner_name}\` |
| **Run ID / Job** | \`${data.run_id}\` / \`${data.job}\` (Shard: \`${data.shard}\`) |
| **VM Profile** | \`${data.vm_size}\` (Loc: \`${data.vm_location}\`, Zone: \`${data.vm_zone}\`) |
| **CPU Model** | **${data.cpu_model}** |
| **Vendor / Family / Stepping** | \`${data.cpu_vendor}\` / \`${data.cpu_family}\` (Model: \`${data.cpu_model_number}\`, Stepping: \`${data.cpu_stepping}\`) |
| **Microcode** | \`${data.microcode}\` |
| **Cores (Physical / Logical)** | **${data.cpu_physical_cores}** physical / **${data.cpu_logical_processors}** logical |
| **Allowed / Quota Cores** | Allowed: **${data.cpu_allowed_processors}** \| Quota: **${data.cpu_quota_cores}** (\`${data.cpu_quota_state}\`) |
| **Clock (Observed / Max)** | \`${data.cpu_observed_mhz} MHz\` / \`${data.cpu_reported_max_mhz} MHz\` |
| **L3 Cache Size** | **${(data.l3_cache_bytes / (1024 * 1024)).toFixed(2)} MB** (\`${data.l3_cache_bytes} bytes\`) |
| **Memory Bandwidth (\`memcpy\`)** | **${data.memcpy_gib_s} GiB/s** (Probe size: \`${data.memcpy_probe_mib} MiB\`) |
| **Key SIMD / Vector Flags** | \`${data.flags.join(", ") || "none detected"}\` |
| **Boot Uptime** | \`${data.boot_seconds}s\` |
| **Measured At** | \`${data.measured_at}\` |

<details>
<summary><b>View Raw JSON Fingerprint</b></summary>

\`\`\`json
${JSON.stringify(data, null, 2)}
\`\`\`

</details>
`;

  fs.appendFileSync(summaryPath, markdown, "utf8");
}

async function run() {
  const data = await collectRunnerData();
  
  // 1. Output to stdout
  console.log(JSON.stringify(data, null, 2));

  // 2. Save JSON file artifact
  fs.writeFileSync("host-fingerprint.json", JSON.stringify(data, null, 2), "utf8");

  // 3. Write Markdown to GitHub Actions Summary
  writeMarkdownSummary(data);
}

run();
