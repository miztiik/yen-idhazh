/** Run real source downloads against bounded local responses, then parse their actual bytes. */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { parseDocument } from "../src/harvest-feeds/parse-document";
import { inputs } from "./harvest-recordings";

async function runSourceOracle(mode: "transport" | "corrections") {
  const temporary = await mkdtemp(join(import.meta.dir, "../node_modules/.source-browser-"));
  try {
    const built = await Bun.build({
      entrypoints: [join(import.meta.dir, "browser-oracle-entry.ts")],
      outdir: temporary, target: "node", external: ["playwright"],
      plugins: [{
        name: "generated-loopback-admission",
        setup(build) {
          build.onLoad({ filter: /safe-target\.ts$/ }, async args => {
            const original = await Bun.file(args.path).text();
            const signature = "export function validateTargetName(raw: string): URL";
            if (!original.includes(signature)) throw new Error("The named source-admission seam changed");
            return { loader: "ts", contents: original.replace(signature,
              "export function validateProductionTargetName(raw: string): URL") + `
export function validateTargetName(raw: string): URL {
  try { return validateProductionTargetName(raw); }
  catch (error) {
    const url = new URL(raw);
    if (globalThis.__fixtureOrigins.has(url.origin) && !url.username && !url.password) return url;
    throw error;
  }
}` };
          });
        },
      }],
    });
    expect(built.success).toBe(true);
    const child = spawn(process.platform === "win32" ? "node" : process.execPath, [
      join(import.meta.dir, "browser-loopback-source.cjs"), join(temporary, "browser-oracle-entry.js"), mode,
    ], { stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    let errors = "";
    child.stdout.on("data", chunk => { output += chunk.toString(); });
    child.stderr.on("data", chunk => { errors += chunk.toString(); });
    const result = await new Promise<number | null>((resolve, reject) => {
      child.once("error", reject);
      child.once("close", resolve);
    });
    if (result !== 0) console.error(errors);
    expect({ result, errors }).toEqual({ result: 0, errors: "" });
    return output;
  } finally { await rm(temporary, { recursive: true, force: true }); }
}

test("the browser source boundary retains raw feeds, cookies, rendered articles and real failures", async () => {
  const observed = JSON.parse(await runSourceOracle("transport")) as {
    feed: string; article: string; unsupported_article: string;
  };
  const loaded = await inputs();
  const entries = await parseDocument("feed", observed.feed, "https://source.example/feed.xml");
  const article = await parseDocument("article", observed.article, "https://source.example/article", loaded.extraction);
  expect(entries.length).toBeGreaterThan(0);
  expect(article.article_text.length).toBeGreaterThan(0);
  expect(article.article_text).not.toContain("<script");
  const unsupported = await parseDocument("article", observed.unsupported_article,
    "https://source.example/shared-worker", loaded.extraction);
  expect(unsupported.article_text).toBe("");
}, 180000);

test("browser icons and background redirects cannot corrupt document outcomes", async () => {
  expect(JSON.parse(await runSourceOracle("corrections")).passed).toBe(true);
}, 180000);
