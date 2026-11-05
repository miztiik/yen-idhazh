/** Can every named shared export and test execute without importing a native service? */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

const root = fileURLToPath(new URL("../", import.meta.url));
const sharedExports = {
  "./app": "./src/create-api-app.ts",
  "./settings": "./src/load-settings.ts",
  "./startup": "./src/api-startup.ts",
  "./supervisor": "./src/supervise-api-task.ts",
  "./evidence": "./src/server-evidence.ts",
  "./read-evidence": "./src/read-server-evidence.ts",
  "./readiness": "./src/read-api-readiness.ts",
  "./events": "./src/write-server-event.ts",
  "./child": "./src/run-http-child.ts",
  "./supervise-child": "./src/supervise-http-child.ts",
  "./child-failure": "./src/http-child-failure.ts",
};
const sharedTests = [
  "test/server-events.test.ts", "test/write-server-events.ts", "test/run-host-lifetime.ts",
  "test/supervise-http-child.test.ts", "test/check-api-dependencies.test.ts",
];
const nativeServices = ["feed-ingest-plan", "host-fingerprints", "host-probes"];
const ManifestSchema = z.object({
  exports: z.record(z.string(), z.string()),
  dependencies: z.record(z.string(), z.string()),
  devDependencies: z.record(z.string(), z.string()),
});

function nativeReferences(value: string) {
  const parts = value.replaceAll("\\", "/").split(/[/@:]/);
  return nativeServices.filter(name => parts.includes(name));
}

test("the named export inventory and all declared dependencies exclude native services", async () => {
  const manifest = ManifestSchema.parse(await Bun.file(join(root, "package.json")).json());
  expect(manifest.exports).toEqual(sharedExports);
  expect(Object.keys(manifest.dependencies).sort()).toEqual(["@idhazh/common-contracts", "hono", "zod"]);
  for (const dependencies of [manifest.dependencies, manifest.devDependencies]) {
    for (const [name, specifier] of Object.entries(dependencies)) {
      expect(nativeReferences(name), name).toEqual([]);
      expect(nativeReferences(specifier), specifier).toEqual([]);
    }
  }
});

test("real Bun dependency graphs for fixed shared entries contain no native implementation", async () => {
  const entries = [...Object.values(sharedExports), ...sharedTests];
  const options = {
    entrypoints: entries.map(entry => join(root, entry)), target: "bun" as const, write: false, metafile: true,
  };
  const result = await Bun.build(options);
  expect(result.success, result.logs.map(log => log.message).join("\n")).toBe(true);
  const metafile = result.metafile;
  expect(metafile).toBeDefined();
  if (metafile === undefined) throw new Error("Bun did not generate dependency metadata");
  const inputs = Object.keys(metafile.inputs);
  expect(inputs.length).toBeGreaterThan(0);
  for (const entry of entries) {
    const suffix = entry.replace(/^\.\//, "");
    expect(inputs.some(input => {
      const path = input.replaceAll("\\", "/").replace(/^\.\//, "");
      return path === suffix || path.endsWith(`/${suffix}`);
    }), entry).toBe(true);
  }
  for (const input of inputs) expect(nativeReferences(input), input).toEqual([]);
}, 25_000);
