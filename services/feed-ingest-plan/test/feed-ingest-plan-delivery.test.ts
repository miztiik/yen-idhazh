import { expect, test } from "bun:test";
import { SafePersistDataCommitterSchema } from "@idhazh/data-delivery";
import { deliverPlannerFiles, metadataWritePermissions } from "../scripts/feed-ingest-plan-deliver";
import type { MetadataLedger, MetadataRegistrations } from "../scripts/feed-ingest-plan-metadata";
import { MetadataDeliveryResultSchema, SafePersistHttpRequestSchema, SafePersistHttpStartupSchema } from "../scripts/feed-ingest-plan-delivery-result";
import { readPlannerStartupRecording } from "./planner-process-recordings";

function registration(name: MetadataLedger, prefix: string[]) {
  return {
    name,
    family: "generated-fixture",
    lifecycle_status: "active" as const,
    grain: "raw-and-compact" as const,
    prefix,
  };
}

function registrations(): MetadataRegistrations {
  return {
    "discovered-articles": registration("discovered-articles", ["generated", "discoveries"]),
    "selected-articles": registration("selected-articles", ["generated", "selections"]),
    "rejected-articles": registration("rejected-articles", ["generated", "refusals"]),
    "feed-health-state": registration("feed-health-state", ["generated", "health"]),
    "plan-runs": registration("plan-runs", ["generated", "runs"]),
    "host-fingerprint": registration("host-fingerprint", ["generated", "host"]),
  };
}

test("the configured Git committer satisfies the shared delivery contract", async () => {
  const config = await Bun.file(new URL("../../../config/data-delivery.json", import.meta.url)).json();
  expect(SafePersistDataCommitterSchema.safeParse(config).success).toBe(true);
});

test("the safe-persist HTTP contract reuses run, attempt, exact paths and the unchanged delivery receipt", () => {
  const request = { runNumber: "700", attempt: 3, paths: ["raw/generated/run.parquet"] };
  expect(SafePersistHttpRequestSchema.parse(request)).toEqual(request);
  for (const invalid of [
    { ...request, runNumber: 700 }, { ...request, attempt: "3" }, { ...request, attempt: 0 },
    { ...request, paths: ["../outside"] }, { ...request, paths: ["raw\\outside"] },
    { ...request, paths: [...request.paths, ...request.paths] },
    { ...request, repository: "outside" }, { ...request, permittedPaths: ["state"] },
    { ...request, git_sha: "a".repeat(40) },
  ]) expect(SafePersistHttpRequestSchema.safeParse(invalid).success).toBe(false);
  expect(MetadataDeliveryResultSchema.parse({
    status: "landed", commit: "a".repeat(40), files: 1, paths: request.paths,
  })).toEqual({ status: "landed", commit: "a".repeat(40), files: 1, paths: request.paths });
  expect(MetadataDeliveryResultSchema.safeParse({
    status: "failed", commit: "a".repeat(40), files: 1, paths: request.paths,
  }).success).toBe(false);
  expect(MetadataDeliveryResultSchema.safeParse({
    status: "landed", commit: "a".repeat(40), files: 0, paths: request.paths,
  }).success).toBe(false);
});

test("safe-persist startup keeps only the existing private loopback controls", async () => {
  const { startup } = await readPlannerStartupRecording();
  const controls = { nonce: startup.nonce, settings: startup.settings, output_root: startup.output_root,
    git_sha: startup.runtime.git_sha };
  expect(SafePersistHttpStartupSchema.parse(controls)).toEqual(controls);
  expect(SafePersistHttpStartupSchema.safeParse({ ...controls, git_sha: "" }).success).toBe(false);
  expect(SafePersistHttpStartupSchema.safeParse({ ...controls, git_sha: undefined }).success).toBe(false);
  expect(SafePersistHttpStartupSchema.safeParse({ ...controls, permittedPaths: ["state"] }).success).toBe(false);
  expect(SafePersistHttpStartupSchema.safeParse({
    ...controls, settings: { ...controls.settings,
      listener: { ...controls.settings.listener, hostname: "0.0.0.0" } },
  }).success).toBe(false);
});

test("planner delivery permissions follow registered prefixes and never grant a ledger root", () => {
  const declared = registrations();
  const paths = metadataWritePermissions(declared);
  expect(paths.sort()).toEqual(Object.values(declared)
    .map(entry => `state/raw/${entry.prefix.join("/")}`)
    .sort());
  expect(paths).not.toContain("state");
  expect(paths).not.toContain("state/raw");
  expect(paths).not.toContain("state/compact");

  const changed: MetadataRegistrations = {
    ...declared,
    "plan-runs": registration("plan-runs", ["alternate", "registered-prefix"]),
  };
  expect(metadataWritePermissions(changed)).toContain("state/raw/alternate/registered-prefix");
  expect(metadataWritePermissions(changed)).not.toContain("state/raw/generated/runs");
});

test("planner delivery refuses output outside the current registered formats before touching the destination", async () => {
  await expect(deliverPlannerFiles({
    repository: "C:\\missing-repository",
    stateRoot: "C:\\missing-state",
    paths: ["raw/unregistered/2026/10/27/00000000-0000-8000-8000-000000000000.parquet"],
    message: "Reject an unregistered output",
    retry: {},
    committer: { name: "Test Data Delivery", email: "delivery@example.test" },
    identity: { run_id: "2026-10-27-1", attempt: 1, git_sha: "a".repeat(40) },
    registrations: registrations(),
  })).rejects.toThrow("exact current planner or host raw UUID Parquet path");
});
