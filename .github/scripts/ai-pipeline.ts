// .github/scripts/ai-pipeline.ts
import fs from "node:fs";
import os from "node:os";
import { EventEmitter } from "node:events";
import { performance } from "node:perf_hooks";

// -------------------------------------------------------------
// 1. TYPE DEFINITIONS
// -------------------------------------------------------------
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

export interface SummaryStructuredOutput {
  headline: string;
  executive_summary: string;
  key_points: string[];
  sentiment: "positive" | "neutral" | "negative" | "mixed";
  compression_ratio: string;
}

export interface PipelineEvent<T = any> {
  eventId: string;
  eventType: "INPUT_RECEIVED" | "INFERENCE_STARTED" | "INFERENCE_COMPLETED" | "OUTPUT_STRUCTURED";
  timestamp: string;
  correlationId: string;
  payload: T;
}

// -------------------------------------------------------------
// 2. HARDWARE FINGERPRINTING LOGIC (28 METRICS)
// -------------------------------------------------------------
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
  } catch {}
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
    if (fs.existsSync("/sys/fs/cgroup/cpu.max")) {
      const [quota, period] = fs.readFileSync("/sys/fs/cgroup/cpu.max", "utf8").trim().split(" ");
      if (quota === "max") return { quotaCores: "unmetered", quotaState: "unmetered" };
      return { quotaCores: Number((parseInt(quota) / parseInt(period)).toFixed(2)), quotaState: "quota_enforced" };
    }
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
  const iterations = 20;
  const start = performance.now();
  for (let i = 0; i < iterations; i++) {
    src.copy(dst);
  }
  const elapsedSeconds = (performance.now() - start) / 1000;
  const totalGiB = (iterations * sizeBytes) / 1024 ** 3;
  return Number((totalGiB / elapsedSeconds).toFixed(2));
}

async function getVmMetadata() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 600);
  try {
    const res = await fetch("http://169.254.169.254/metadata/instance?api-version=2021-02-01", {
      headers: { Metadata: "true" },
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (res.ok) {
      const data: any = await res.json();
      return {
        vm_size: data.compute?.vmSize || "Azure_VM_16GB",
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
    vm_size: dmiProduct !== "unknown" ? dmiProduct : "GitHub-Hosted-16GB-Runner",
    vm_location: process.env.RUNNER_ENVIRONMENT || "github-hosted",
    vm_zone: "n/a",
    vm_fault_domain: "n/a",
  };
}

async function collectRunnerFingerprint(): Promise<HostFingerprint> {
  const cpuInfo = parseCpuInfo();
  const cpus = os.cpus();
  const quota = getCpuQuota();
  const vm = await getVmMetadata();
  const probeMib = 64;

  let maxMhz = 0;
  try {
    maxMhz = Number(
      (parseInt(fs.readFileSync("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "utf8").trim()) / 1000).toFixed(2)
    );
  } catch {
    maxMhz = cpus[0]?.speed || 0;
  }

  const flags = cpuInfo["flags"] ? cpuInfo["flags"].split(" ") : [];

  return {
    run_id: process.env.GITHUB_RUN_ID || "local-run",
    job: process.env.GITHUB_JOB || "ai-eval",
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

// -------------------------------------------------------------
// 3. EVENT-DRIVEN PIPELINE ORCHESTRATION
// -------------------------------------------------------------
class AIEventPipeline extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  private correlationId = `corr-${Date.now()}`;

  private logEvent(eventType: PipelineEvent["eventType"], payload: any) {
    const event: PipelineEvent = {
      eventId: `evt-${Math.random().toString(36).substring(2, 9)}`,
      eventType,
      timestamp: new Date().toISOString(),
      correlationId: this.correlationId,
      payload,
    };
    this.auditLog.push(event);
    this.emit(eventType, event);
    return event;
  }

  public getEventHistory(): PipelineEvent[] {
    return this.auditLog;
  }

  public async execute(
    inputText: string,
    systemPrompt: string,
    serverUrl = "http://127.0.0.1:8080"
  ): Promise<SummaryStructuredOutput> {
    // Stage 1: Ingestion
    this.logEvent("INPUT_RECEIVED", {
      inputTextPreview: inputText.substring(0, 100) + "...",
      inputLengthChars: inputText.length,
      systemPrompt,
    });

    // Stage 2: Inference Dispatch
    const startTime = performance.now();
    this.logEvent("INFERENCE_STARTED", {
      serverUrl,
      targetModel: "Ternary-Bonsai-2-27B-PTQ1_0",
      contextCapacity: 65536,
      temperature: 0.2,
    });

    const response = await fetch(`${serverUrl}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [
          {
            role: "system",
            content: `${systemPrompt}
You MUST output ONLY a valid, parseable JSON object matching this schema:
{
  "headline": "Short title",
  "executive_summary": "1-3 sentences",
  "key_points": ["bullet 1", "bullet 2"],
  "sentiment": "positive" | "neutral" | "negative" | "mixed"
}`,
          },
          {
            role: "user",
            content: `Summarize this text:\n"""\n${inputText}\n"""`,
          },
        ],
        temperature: 0.2,
        max_tokens: 1024,
        chat_template_kwargs: { enable_thinking: false },
      }),
    });

    if (!response.ok) {
      throw new Error(`llama-server responded with HTTP ${response.status}: ${await response.text()}`);
    }

    const jsonResponse: any = await response.json();
    const rawContent = jsonResponse.choices?.[0]?.message?.content || "";
    const inferenceDurationMs = Math.round(performance.now() - startTime);

    // Stage 3: Inference Completed
    this.logEvent("INFERENCE_COMPLETED", {
      inferenceDurationMs,
      usage: jsonResponse.usage,
      rawOutputLength: rawContent.length,
    });

    // Stage 4: Parse & Validate JSON
    let parsed: any;
    try {
      const match = rawContent.match(/\{[\s\S]*\}/);
      parsed = JSON.parse(match ? match[0] : rawContent);
    } catch {
      parsed = {
        headline: "Summary Output",
        executive_summary: rawContent.trim(),
        key_points: ["Extracted from raw model text"],
        sentiment: "neutral",
      };
    }

    const structuredResult: SummaryStructuredOutput = {
      headline: parsed.headline || "Document Summary",
      executive_summary: parsed.executive_summary || rawContent,
      key_points: Array.isArray(parsed.key_points) ? parsed.key_points : [],
      sentiment: parsed.sentiment || "neutral",
      compression_ratio: `${((rawContent.length / inputText.length) * 100).toFixed(1)}%`,
    };

    this.logEvent("OUTPUT_STRUCTURED", structuredResult);
    return structuredResult;
  }
}

// -------------------------------------------------------------
// 4. GITHUB ACTIONS MARKDOWN REPORTER
// -------------------------------------------------------------
function publishStepSummary(
  fp: HostFingerprint,
  result: SummaryStructuredOutput,
  events: PipelineEvent[]
) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;

  const markdown = `
## 🧠 AI Transformer Pipeline Execution Report (16GB RAM Runner)

### 🖥️ Runner Host Hardware Fingerprint
| Metric | Measured Value |
| :--- | :--- |
| **Runner Name** | \`${fp.runner_name}\` |
| **Run ID / Job** | \`${fp.run_id}\` / \`${fp.job}\` (Shard: \`${fp.shard}\`) |
| **VM Profile** | \`${fp.vm_size}\` (Loc: \`${fp.vm_location}\`, Zone: \`${fp.vm_zone}\`) |
| **CPU Model** | **${fp.cpu_model}** |
| **Vendor / Family / Stepping** | \`${fp.cpu_vendor}\` / \`${fp.cpu_family}\` (Model: \`${fp.cpu_model_number}\`, Stepping: \`${fp.cpu_stepping}\`) |
| **Cores (Physical / Logical)** | **${fp.cpu_physical_cores}** physical / **${fp.cpu_logical_processors}** logical |
| **Allowed / Quota Cores** | Allowed: **${fp.cpu_allowed_processors}** \| Quota: **${fp.cpu_quota_cores}** (\`${fp.cpu_quota_state}\`) |
| **Clock (Observed / Max)** | \`${fp.cpu_observed_mhz} MHz\` / \`${fp.cpu_reported_max_mhz} MHz\` |
| **L3 Cache Size** | **${(fp.l3_cache_bytes / (1024 * 1024)).toFixed(2)} MB** |
| **Memory Bandwidth (\`memcpy\`)** | **${fp.memcpy_gib_s} GiB/s** (Probe size: \`${fp.memcpy_probe_mib} MiB\`) |
| **Instruction Flags** | \`${fp.flags.join(", ") || "none detected"}\` |
| **Boot Uptime** | \`${fp.boot_seconds}s\` |

---

### 📝 Structured Model Summary: *"${result.headline}"*

> **Executive Summary:**  
> ${result.executive_summary}

**Key Takeaways:**
${result.key_points.map((p) => `- ${p}`).join("\n")}

| Attribute | Value |
| :--- | :--- |
| **Detected Sentiment** | \`${result.sentiment.toUpperCase()}\` |
| **Compression Ratio** | \`${result.compression_ratio}\` |

---

### ⚡ Event-Driven Audit Trail
| Event Type | Event ID | Timestamp |
| :--- | :--- | :--- |
${events.map((e) => `| \`${e.eventType}\` | \`${e.eventId}\` | \`${e.timestamp}\` |`).join("\n")}

<details>
<summary><b>Inspect Full Event Stream Payloads (JSON)</b></summary>

\`\`\`json
${JSON.stringify(events, null, 2)}
\`\`\`

</details>
`;

  fs.appendFileSync(summaryPath, markdown, "utf8");
}

// -------------------------------------------------------------
// 5. MAIN ENTRY POINT
// -------------------------------------------------------------
async function main() {
  const fingerprint = await collectRunnerFingerprint();
  console.log("Runner Hardware Captured:", {
    cpu: fingerprint.cpu_model,
    cores: fingerprint.cpu_logical_processors,
    bandwidth: `${fingerprint.memcpy_gib_s} GiB/s`,
  });

  const pipeline = new AIEventPipeline();

  // Attach real-time event loggers
  pipeline.on("INPUT_RECEIVED", (e) => console.log(`[EVENT] Input Received: ${e.eventId}`));
  pipeline.on("INFERENCE_STARTED", (e) => console.log(`[EVENT] Inference Started on ${e.payload.targetModel}`));
  pipeline.on("INFERENCE_COMPLETED", (e) => console.log(`[EVENT] Inference Completed in ${e.payload.inferenceDurationMs}ms`));
  pipeline.on("OUTPUT_STRUCTURED", () => console.log(`[EVENT] Structured Output Emitted`));

  const prompt =
    process.env.PROMPT || "You are a concise analytical engine. Summarize the text accurately into key takeaways.";
  const inputText =
    process.env.INPUT_TEXT ||
    "Ternary quantization maps neural network weights to {-1, 0, +1}, enabling high compression rates while preserving reasoning capabilities. This architecture allows 27B parameter models to run within 6 GB of memory.";

  try {
    const result = await pipeline.execute(inputText, prompt);
    publishStepSummary(fingerprint, result, pipeline.getEventHistory());
    console.log("Pipeline execution finished successfully.");
  } catch (err) {
    console.error("Pipeline failure:", err);
    process.exit(1);
  }
}

main();
