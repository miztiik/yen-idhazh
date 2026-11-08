/** Can the real machine entry and summary caller resolve without any feed implementation? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";

test("native machine entries and the summary helper have no feed dependency", async () => {
  const result = await Bun.build({
    entrypoints: [
      new URL("../src/api/serve-machine-apis.ts", import.meta.url),
      new URL("../src/api/supervise-machine-api-task.ts", import.meta.url),
      new URL("../../../tools/summary-eval/machine-task.ts", import.meta.url),
    ].map(url => fileURLToPath(url)),
    target: "bun", metafile: true,
  });
  expect(result.success, result.logs.map(log => log.message).join("\n")).toBe(true);
  if (result.metafile === undefined) throw new Error("Machine dependency inspection requires build metadata");
  const inputs = Object.keys(result.metafile.inputs).map(path => path.replaceAll("\\", "/"));
  expect(inputs.some(path => /(?:^|\/)feed-ingest-plan\//.test(path))).toBe(false);
  expect(inputs.some(path => path.endsWith("/serve-machine-apis.ts"))).toBe(true);
  expect(inputs.some(path => path.endsWith("/machine-task.ts"))).toBe(true);
});
