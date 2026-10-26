/** How are bounded host inputs materialized as real temporary files? */
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { z } from "zod";
import { CaptureContextSchema, loadConfig, loadSettings } from "../src/config";

const InputFixtureSchema = z.object({
  files: z.record(z.string(), z.string()),
  metadata: z.unknown(), environment: z.record(z.string(), z.string()),
  expected: z.record(z.string(), z.union([z.string(), z.number()])),
});
export async function fixture() {
  const input = InputFixtureSchema.parse(await Bun.file(new URL("../../../tests/fixtures/host-fingerprints/linux-inputs.json", import.meta.url)).json());
  const directory = await mkdtemp(join(tmpdir(), "host-fingerprint-"));
  const root = join(directory, "inputs");
  for (const [path, text] of Object.entries(input.files)) {
    const target = join(root, ...path.split("/"));
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, text);
  }
  const config = await loadConfig();
  const settings = await loadSettings();
  settings.observability.host_fingerprint_frequency_enabled = true;
  const capture = CaptureContextSchema.parse({
    date: "2026-10-21", writer: {
      run_id: "2026-10-21-123", attempt: 1, job: null,
      pipeline_name: "fixture-pipeline", task_name: "inspect-host", shard: 2,
      producer: "telemetry.silicon", git_sha: "a".repeat(40),
    },
    model_load_ms: 123.5, job_seconds: 42, server_prompt_tokens: 320, server_prompt_seconds: 1.25,
  });
  return {
    input, directory, root, config, settings, capture,
    apiInput: { date: capture.date, writer: capture.writer },
    inspection: {
      root, platform: "linux" as const, environment: input.environment,
      get metadata() { return Response.json(input.metadata); },
    },
    cleanup: () => rm(directory, { recursive: true, force: true }),
  };
}
