/** Verify the real request gate with Chromium, not a recorded browser or external website. */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { spawn } from "node:child_process";

test("Chromium admits redirects and child requests before dispatch", async () => {
  const temporary = await mkdtemp(join(import.meta.dir, "../node_modules/.source-browser-"));
  try {
    const built = await Bun.build({
      entrypoints: [join(import.meta.dir, "browser-oracle-entry.ts")],
      outdir: temporary, target: "node", external: ["playwright"],
    });
    expect(built.success).toBe(true);
    const child = spawn(process.platform === "win32" ? "node" : process.execPath, [
      join(import.meta.dir, "browser-loopback-source.cjs"), join(temporary, "browser-oracle-entry.js"),
    ], { env: { ...process.env, NODE_PATH: join(import.meta.dir, "../node_modules") },
      stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    let errors = "";
    child.stdout.on("data", chunk => { output += chunk.toString(); });
    child.stderr.on("data", chunk => { errors += chunk.toString(); });
    const result = await new Promise<number | null>((resolve, reject) => {
      child.once("error", reject);
      child.once("exit", resolve);
    });
    expect({ result, errors }).toEqual({ result: 0, errors: "" });
    expect(JSON.parse(output).passed).toBe(true);
    if (process.platform === "linux") console.log(JSON.stringify({ renderer_sandbox: JSON.parse(output).sandbox }));
  } finally { await rm(temporary, { recursive: true, force: true }); }
}, 40000);
