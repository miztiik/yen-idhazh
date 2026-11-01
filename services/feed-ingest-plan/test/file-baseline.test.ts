/** Does a Git-free real HTTP execution keep every loaded historical decision fixed? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";

test("recorded HTTP collection reuses immutable raw and compact evidence with Git unavailable", async () => {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./file-baseline-recording.ts", import.meta.url))], {
    cwd: root, env: { ...process.env, PATH: "", Path: "", IDHAZH_ORACLE_SOURCE_ROOT: root },
    stdout: "pipe", stderr: "pipe",
  });
  const [output, error, status] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  expect(status, error).toBe(0);
  expect(JSON.parse(output.trim())).toEqual({
    git_unavailable: true, source_matches_requested: true, loaded_before_fetch: true,
    raw_and_compact: true, baseline_unchanged: true, historical_edits_and_additions: true,
    independent_capture_changed: true, selected_count: 2, native_output_readback: true, selection_retained: true,
    standalone_baseline_unchanged: true,
    utc_boundary_reused: true,
    selected_metadata_readback: true, selected_text_readback: true, health_readback: true,
  });
}, 120_000);
