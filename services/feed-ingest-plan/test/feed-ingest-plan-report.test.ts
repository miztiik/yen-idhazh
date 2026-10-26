/** Does optional reporting preserve body-free observations without inventing saved output? */
import { test, expect } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFeedIngestEvent } from "../../../packages/common-contracts/src/index";
import { formatPlannerReport, writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { formatRam, formatResourceSummary } from "../scripts/feed-ingest-plan-resource-summary";
import { formatWorkflowPolicy } from "../scripts/feed-ingest-plan-policy-report";
import { configureWorkflowProfiling, observeWorkflowResources, WorkflowResourcesSchema } from "../scripts/feed-ingest-plan-workflow-resources";
import { loadConfig as loadProbeConfig } from "../../host-probes/src/config";
import { ResourceProofSchema } from "../../host-probes/scripts/feed-ingest-plan-profile-schema";
import { fixture as hostFixture } from "../../host-fingerprints/test/fixture";
import { captureLocalFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";

async function fixture() {
  const rows: unknown[] = await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/report-events.json", import.meta.url),
  ).json();
  return rows.map(readFeedIngestEvent);
}

test("reads current sparse progress and refuses hidden article or audit payloads", async () => {
  const events = await fixture();
  const before = structuredClone(events);
  expect(formatPlannerReport(events)).toEqual(formatPlannerReport(before));
  expect(events.every(event => event.version === "2026-10-26")).toBe(true);
  for (const changed of [
    { ...events[0], headers: { authorization: "private" } },
    { ...events[0], article_text: "Private article body" },
    { ...events[0], payload: { kind: "candidate_decision" } },
    { ...events[0], event_id: "a".repeat(64) },
    { ...events[0], correlation_id: "old-run-label" },
    { ...events[0], version: "2026-10-20" },
  ]) expect(() => formatPlannerReport([changed])).toThrow();
  expect(events).toEqual(before);
});

test("absent progress stays unavailable and zero counts do not certify publication", async () => {
  const events = await fixture();
  const before = JSON.stringify(events);
  const report = formatPlannerReport(events);
  expect(report.summary).toContain("Progress does not prove saved output or publication.");
  expect(report.annotations).toEqual([]);
  expect(JSON.stringify(events)).toBe(before);
  const empty = formatPlannerReport([]);
  expect(empty.summary).toContain("No progress was supplied. The result is unavailable.");
  expect(empty.annotations).toEqual([]);
  const zero = formatPlannerReport([{ ...events[0], phase: "completed", output_count: 0, duration_ms: 0 }]);
  expect(zero.summary).toContain("0 milliseconds");
  expect(zero.summary).not.toContain("publication completed");
  expect(formatRam(1_000_000, 2_000_000, "free")).toBe("1.02 GB / 2.05 GB total (50.00% free)");
  expect(formatRam(0, 2_000_000)).toBe("0.00 GB / 2.05 GB total (0.00% available)");
  expect(formatRam(null, 2_000_000, "free", "configured_off")).toBe("Unavailable (configured off)");
  expect(formatRam(1, null)).toContain("percentage unavailable");
  expect(formatRam(1, 0)).toContain("percentage unavailable");
  const proof = ResourceProofSchema.parse(await Bun.file(
    new URL("../../../tests/fixtures/host-probes/cache-resource-proof.json", import.meta.url)).json());
  const f = await hostFixture();
  try {
    const host = await captureLocalFingerprint(f.apiInput, { ...f.config, listen_port: 0 }, f.settings, {
      outputRoot: join(f.directory, "state"), inspection: f.inspection,
    });
    if (host.status !== "written") throw new Error("A report fixture requires completed host Parquet");
    const resources = { host_request: f.apiInput, profile_requested: true, host: { ...host, status: "recorded" },
      profile: { status: "recorded", value: proof.task_profile!.profile } };
    const resource = formatResourceSummary(resources, proof, true);
    expect(resource.notice).toContain("Actual host:");
    expect(resource.notice).toMatch(/\d+\.\d{2}% free/);
    expect(resource.notice).toMatch(/\d+\.\d{2}% available/);
    expect(resource.notice).toContain("Planner and HTTP listener share one PID");
    const rendered = Bun.markdown.html(resource.summary);
    expect((rendered.match(/<table>/g) ?? [])).toHaveLength(1);
    expect(rendered).toContain("Lowest observed available RAM");
    expect(rendered).toContain("not an assured whole-run minimum");
    expect(rendered).toContain("Independent controlled process");
    expect(rendered).not.toContain("kB</td>");
    expect(rendered).not.toContain("GiB");
    expect(rendered).not.toContain("Server not configured");
    for (const reason of ["profile_machine_memory=false", "observability.host_telemetry_enabled=false"]) {
      const off = formatResourceSummary({ ...resources, profile_requested: false,
        host: { status: "disabled", reason }, profile: { status: "disabled", reason } }, undefined, false);
      expect(off.notice).toContain(reason);
      expect(off.notice).toContain("not requested");
      expect(off.notice).not.toContain("0.00 GB");
    }
    const unavailable = formatResourceSummary(undefined, undefined, true);
    expect(unavailable.notice).toContain("unavailable");
    expect(unavailable.notice).not.toContain("0.00 GB");
    const partial = formatResourceSummary(resources, { ...proof, status: "failed", stage: "cache",
      error: "Independent cache proof failed" }, true);
    expect(partial.notice).toContain("failed at cache");
    expect(partial.summary).toContain("Independent cache proof failed");
  } finally { await f.cleanup(); }
});

test("escapes command data and refuses URLs or arbitrary progress fields", async () => {
  const events = await fixture();
  const report = formatPlannerReport([{ ...events[0], phase: "failed",
    failure_code: "NETWORK\r\n::error title=pwn::run | <script>` %" }]);
  expect(report.annotations).toHaveLength(1);
  expect(report.annotations[0]).not.toContain("\n");
  expect(report.annotations[0]).not.toContain("\r");
  expect(report.annotations[0]).toContain("%0A");
  expect(report.annotations[0]).toContain("%25");
  expect(() => formatPlannerReport([{ ...events[0], feed_id: "https://news.example/feed?token=private" }])).toThrow();
  expect(() => formatPlannerReport([{ ...events[0], url: "https://news.example/private" }])).toThrow();
});

test("refuses mixed executions but permits concurrent stage ordering without fabricated sequence fields", async () => {
  const events = await fixture();
  expect(() => formatPlannerReport([events[0], { ...events[1], run_id: "2026-10-21-999" }])).toThrow("more than one run");
  expect(() => formatPlannerReport([events[0], { ...events[1], correlation_id: "040345df-230e-4bf9-8efc-d0d823fcde3b" }])).toThrow("more than one run");
  expect(() => formatPlannerReport([{ ...events[0], sequence: 1 }])).toThrow();
  expect(() => formatPlannerReport([events[1], events[0]])).not.toThrow();
});

test("disabled reporting reads no evidence and enabled reporting requires an explicit output path", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-report-"));
  try {
    const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
    const summary = join(root, "summary.md");
    const lines: string[] = [];
    await writePlannerReport({
      config: { ...config, workflow_reporting: { ...config.workflow_reporting, enabled: false } },
      summary_path: summary, annotate: line => lines.push(line),
      get events(): never { throw new Error("Disabled reporting must not inspect progress"); },
      get evidence(): never { throw new Error("Disabled reporting must not inspect execution evidence"); },
    });
    expect(lines).toEqual([]);
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    const events = await fixture();
    const enabled = { ...config, workflow_reporting: { ...config.workflow_reporting, enabled: true } };
    await writePlannerReport({ config: enabled, events, summary_path: summary, annotate: line => lines.push(line) });
    expect(await readFile(summary, "utf8")).toBe(formatPlannerReport(events).summary);
    expect(lines).toEqual([...formatPlannerReport(events).annotations]);
    await expect(writePlannerReport({ config: enabled, events, annotate: () => {} })).rejects.toThrow("summary output path");
    const probe = await loadProbeConfig();
    for (const requested of [false, true]) for (const host_telemetry_enabled of [false, true]) {
      for (const memory_profiling_enabled of [false, true]) {
        const configured = configureWorkflowProfiling(probe, requested, { host_telemetry_enabled, memory_profiling_enabled });
        expect(configured.task_profile.enabled).toBe(requested && host_telemetry_enabled);
        expect(configured.task_profile.memory_enabled).toBe(requested && host_telemetry_enabled && memory_profiling_enabled);
        expect(configured.task_profile.machine_memory_enabled).toBe(configured.task_profile.memory_enabled);
      }
    }
    const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
    const policy = formatWorkflowPolicy({ config,
      request: { freshness_hours: 2, article_limit: 10, shards: 4, partition_strategy: "bin-pack" },
      history: settings.collect, parser_concurrency: 4 }, true);
    expect(policy.notice).toContain("maximum age 2 hours; 10 articles; 4 workers; bin-pack");
    expect(policy.rows.find(([name]) => name === "Maximum article age")?.[1]).toBe("2 hours (workflow override)");
    expect(policy.rows.find(([name]) => name === "Article limit")?.[1]).toBe("10 articles (workflow override)");
    expect(policy.notice).not.toContain("24 hours");
    expect(formatWorkflowPolicy(undefined, false).notice).toContain("defaults do not prove");
    await mkdir(join(root, "config"));
    const input = { root, directory: root, stateRoot: join(root, "state"), profileRequested: false, gitSha: "a".repeat(40), attempt: 1,
      identity: { pipeline_name: "feed-ingest-plan", task_name: "planner-http-request",
        run_id: events[0]!.run_id, correlation_id: events[0]!.correlation_id, request_id: crypto.randomUUID() } };
    await writeFile(join(root, "config", "idhazh.json"), JSON.stringify({ ...settings,
      observability: { ...settings.observability, host_telemetry_enabled: true, host_fingerprint: true } }));
    await (await observeWorkflowResources(input)).close("success");
    const failed = WorkflowResourcesSchema.parse(await Bun.file(join(root, "resources.json")).json());
    expect(failed.host.status).toBe("failed");
    if (failed.host.status !== "failed") throw new Error("Missing collector configuration must remain a failed observation");
    expect(failed.host.reason).toContain("config/host-fingerprints.json");
    expect(failed.host.reason).not.toContain(root);
    await writeFile(join(root, "config", "idhazh.json"), JSON.stringify({ ...settings,
      observability: { ...settings.observability, host_telemetry_enabled: false } }));
    await (await observeWorkflowResources({ ...input, profileRequested: true })).close("success");
    const off = WorkflowResourcesSchema.parse(await Bun.file(join(root, "resources.json")).json());
    expect(off.host).toEqual({ status: "disabled", reason: "observability.host_telemetry_enabled=false" });
    expect(off.profile).toEqual({ status: "disabled", reason: "observability.host_telemetry_enabled=false" });
  } finally { await rm(root, { recursive: true, force: true }); }
});
