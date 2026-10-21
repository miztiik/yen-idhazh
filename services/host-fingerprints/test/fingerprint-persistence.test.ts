/** Do API and CLI captures persist real compatible Parquet or fail explicitly? */
import { expect, test } from "bun:test";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tableFromIPC } from "apache-arrow";
import initializeWasm, { readParquet, readMetadata } from "parquet-wasm/esm";
import type { Table } from "apache-arrow";
import { HostFingerprintRowSchema } from "@idhazh/common-contracts";
import { createFingerprintHandler, FINGERPRINT_PATH, HEALTH_PATH } from "../src/api/server";
import { persistFingerprint } from "../src/persist-fingerprint";
import { writeAtomically } from "../../../packages/ledger-file-writer/src/atomic-file";
import { fixture } from "./fixture";

async function readTable(root: string, path: string) {
  await initializeWasm();
  const bytes = new Uint8Array(await readFile(join(root, ...path.split("/"))));
  const table = tableFromIPC(readParquet(bytes).intoIPCStream());
  return { table, bytes };
}
function storedRow(table: Table): Record<string, unknown> {
  const row = table.get(0);
  if (!row) throw new Error("expected one persisted host row");
  return Object.fromEntries(Object.entries(row.toJSON()).map(([name, value]) =>
    [name, typeof value === "bigint" ? Number(value) : value]));
}
function request(input: unknown) {
  return new Request(`http://localhost${FINGERPRINT_PATH}`, { method: "POST", body: JSON.stringify(input) });
}
test("POST persists the entire hardware row and independent Arrow column transcript", async () => {
  const f = await fixture();
  try {
    const outputRoot = join(f.directory, "state");
    const handler = createFingerprintHandler(f.config, f.settings, { outputRoot, inspection: f.inspection });
    const response = await handler(request(f.capture));
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("written");
    expect(body.row).toMatchObject(f.input.expected);
    expect(body.files).toHaveLength(1);
    expect(body.files[0].path).toMatch(/^raw\/host-fingerprint\/2026\/10\/21\/[0-9a-f-]+\.parquet$/);
    const { table, bytes } = await readTable(outputRoot, body.files[0].path);
    const recorded = await Bun.file(new URL("../../../tests/fixtures/host-fingerprints/host-schema.json", import.meta.url)).json();
    const columns = new Map(table.schema.fields.map((field) => [field.name, field.type.toString()]));
    for (const [name, kind] of Object.entries(recorded.columns)) {
      expect(columns.get(name)).toBe(kind === "int64" ? "Int64" : kind === "float64" ? "Float64" : "Utf8");
      expect(table.schema.fields.find((field) => field.name === name)?.nullable).toBe(!recorded.required.includes(name));
    }
    const actual = storedRow(table);
    for (const [name, value] of Object.entries(body.row)) expect(actual[name]).toEqual(value);
    expect(actual.pipeline_name).toBe("fixture-pipeline");
    expect(actual.task_name).toBe("inspect-host");
    expect(actual.attempt).toBe(1);
    const parquetMetadata = readMetadata(bytes);
    const metadata = Object.fromEntries(parquetMetadata.fileMetadata().keyValueMetadata());
    parquetMetadata.free();
    expect(metadata.schema_version).toBe("2026-10-14");
    expect(metadata.writer).toBe("idhazh_typescript.ledger.parquet");
    expect(metadata.content_sha256).toBe(body.files[0].content_sha256);
  } finally { await f.cleanup(); }
});
test("full independently recorded row retains every non-null hardware and clock cell through the shared writer", async () => {
  const f = await fixture();
  try {
    const { persistLedger } = await import("@idhazh/ledger-file-writer");
    const recorded = await Bun.file(new URL("../../../tests/fixtures/host-fingerprints/host-schema.json", import.meta.url)).json();
    const row = HostFingerprintRowSchema.parse(recorded.row);
    const outputRoot = join(f.directory, "full-row");
    const result = await persistLedger({
      ledger: "host-fingerprint", rowContract: { schema: HostFingerprintRowSchema, schemaVersion: row.version },
      rows: [row], writerContext: f.capture.writer, outputRoot,
      registryEntry: { name: "host-fingerprint", family: "host-fingerprint", grain: "raw-and-compact", lifecycle_status: "active", prefix: ["host-fingerprint"] },
      ledgerSettings: f.settings.ledger, period: { tier: "raw", covers: row.date },
    });
    if (result.status !== "written" || !result.files[0]) throw new Error("full host row did not persist");
    const { table } = await readTable(outputRoot, result.files[0].path);
    const actual = storedRow(table);
    for (const [name, value] of Object.entries(recorded.row)) expect(actual[name]).toEqual(value);
  } finally { await f.cleanup(); }
});
test("health and inspection GET have no side effects; malformed caller input never writes", async () => {
  const f = await fixture();
  try {
    const outputRoot = join(f.directory, "never-created");
    const handler = createFingerprintHandler(f.config, f.settings, { outputRoot, inspection: f.inspection });
    expect((await handler(new Request(`http://localhost${HEALTH_PATH}`))).status).toBe(200);
    expect((await handler(new Request(`http://localhost${FINGERPRINT_PATH}`))).status).toBe(405);
    expect((await handler(request({ ...f.capture, writer: { ...f.capture.writer, pipeline_name: "../unsafe" } }))).status).toBe(400);
    expect((await handler(request({ ...f.capture, writer: { ...f.capture.writer, task_name: null } }))).status).toBe(400);
    expect((await handler(request({ ...f.capture, writer: { ...f.capture.writer, shard: -1 } }))).status).toBe(400);
    expect((await handler(new Request(`http://localhost${FINGERPRINT_PATH}`, { method: "POST", body: "bad JSON" }))).status).toBe(400);
    expect(await Bun.file(outputRoot).exists()).toBe(false);
    f.config.max_input_bytes = 1;
    expect((await handler(request(f.capture))).status).toBe(413);
  } finally { await f.cleanup(); }
});
test.each(["host_telemetry_enabled", "host_fingerprint"] as const)("%s off skips reads and all writes but still validates caller identity", async (key) => {
  const f = await fixture();
  try {
    f.settings.observability[key] = false;
    const outputRoot = join(f.directory, "disabled");
    const result = await persistFingerprint(f.capture, f.config, f.settings, { outputRoot, registryPath: join(f.directory, "missing-registry") });
    expect(result).toEqual({ status: "disabled", row: null, files: [], unavailable: {} });
    expect(await Bun.file(outputRoot).exists()).toBe(false);
    await expect(persistFingerprint({ ...f.capture, writer: {} }, f.config, f.settings, { outputRoot })).rejects.toThrow();
  } finally { await f.cleanup(); }
});
test("failed persistence rejects the API request rather than returning row or paths", async () => {
  const f = await fixture();
  try {
    const outputRoot = join(f.directory, "blocked");
    await writeFile(outputRoot, "existing file");
    const handler = createFingerprintHandler(f.config, f.settings, { outputRoot, inspection: f.inspection });
    await expect(handler(request(f.capture))).rejects.toThrow();
    expect(await readFile(outputRoot, "utf8")).toBe("existing file");
    const target = join(f.directory, "rename-blocked.parquet");
    await mkdir(target);
    await writeFile(join(target, "keep"), "original");
    await expect(writeAtomically(target, new Uint8Array([1, 2, 3]))).rejects.toThrow();
    expect(await readFile(join(target, "keep"), "utf8")).toBe("original");
    expect((await readdir(f.directory)).filter((name) => name.endsWith(".tmp"))).toEqual([]);
  } finally { await f.cleanup(); }
});
test("retry keeps one work-unit identity and later whole-row settlement without editing prior files", async () => {
  const f = await fixture();
  try {
    const outputRoot = join(f.directory, "retry");
    const options = { outputRoot, inspection: f.inspection };
    const first = await persistFingerprint(f.capture, f.config, f.settings, options);
    if (first.status !== "written" || !first.files[0]) throw new Error("first capture missing");
    const original = await readFile(join(outputRoot, first.files[0].path));
    const retry = await persistFingerprint({ ...f.capture, job_seconds: 99, writer: { ...f.capture.writer, attempt: 2 } }, f.config, f.settings, options);
    if (retry.status !== "written" || !retry.files[0]) throw new Error("retry capture missing");
    expect(first.files[0].unit_id).toBe(retry.files[0].unit_id);
    expect(first.files[0].path).not.toBe(retry.files[0].path);
    expect(await readFile(join(outputRoot, first.files[0].path))).toEqual(original);
    const rows = await Promise.all([first.files[0], retry.files[0]].map(async (file) => storedRow((await readTable(outputRoot, file.path)).table)));
    // Existing settlement chooses the later whole row, not a merge of cells.
    const settled = rows.sort((a, b) => Number(a.attempt) - Number(b.attempt)).at(-1);
    expect(settled?.job_seconds).toBe(99);
    expect(settled?.cpu_vendor).toBe("GenuineIntel");
  } finally { await f.cleanup(); }
});
test("paused registration fails explicitly and leaves no files", async () => {
  const f = await fixture();
  try {
    const registryPath = join(f.directory, "registry.json");
    await writeFile(registryPath, JSON.stringify({ families: [{ name: "host-fingerprint", lifecycle_status: "paused", ledgers: [{ name: "host-fingerprint", grain: "raw-and-compact", prefix: ["host-fingerprint"] }] }] }));
    const outputRoot = join(f.directory, "paused");
    await expect(persistFingerprint(f.capture, f.config, f.settings, { outputRoot, registryPath, inspection: f.inspection })).rejects.toThrow("not persisted");
    expect(await Bun.file(outputRoot).exists()).toBe(false);
  } finally { await f.cleanup(); }
});
test("actual CLI writes readable Parquet, honors selected settings, and exits nonzero on write failure", async () => {
  const f = await fixture();
  try {
    const contextPath = join(f.directory, "context.json");
    const configPath = join(f.directory, "service.json");
    const settingsPath = join(f.directory, "selected.json");
    await writeFile(contextPath, JSON.stringify(f.capture));
    await writeFile(configPath, JSON.stringify({ ...f.config, metadata_url: null }));
    await writeFile(settingsPath, JSON.stringify(f.settings));
    const outputRoot = join(f.directory, "cli");
    const { fileURLToPath } = await import("node:url");
    const cli = fileURLToPath(new URL("../src/index.ts", import.meta.url));
    const args = [process.execPath, "run", cli, "--fingerprint", "--context", contextPath, "--state-root", outputRoot, "--config", configPath, "--settings", settingsPath];
    const child = Bun.spawn(args, { stdout: "pipe", stderr: "pipe" });
    const body = await new Response(child.stdout).text();
    expect(await child.exited).toBe(0);
    const response = JSON.parse(body);
    const actual = storedRow((await readTable(outputRoot, response.files[0].path)).table);
    expect(actual.run_id).toBe(f.capture.writer.run_id);
    expect(actual.pipeline_name).toBe(f.capture.writer.pipeline_name);
    expect(actual.job_seconds).toBe(42);
    if (process.platform !== "linux") expect(actual.cpu_vendor).toBeNull();
    const failRoot = join(f.directory, "file-not-directory");
    await writeFile(failRoot, "unchanged");
    const failed = Bun.spawn(args.map((arg) => arg === outputRoot ? failRoot : arg), { stdout: "pipe", stderr: "pipe" });
    expect(await failed.exited).not.toBe(0);
    expect(await new Response(failed.stdout).text()).toBe("");
    expect(await new Response(failed.stderr).text()).toContain("host_fingerprint_failed");
    f.settings.observability.host_telemetry_enabled = false;
    await writeFile(settingsPath, JSON.stringify(f.settings));
    const disabled = Bun.spawn(args, { stdout: "pipe", stderr: "pipe" });
    expect(await disabled.exited).toBe(0);
    expect(JSON.parse(await new Response(disabled.stdout).text()).status).toBe("disabled");
  } finally { await f.cleanup(); }
});
