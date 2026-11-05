/** Observe the real feed diagnostic adapter and shared mirror through a child process. */
import { z } from "zod";
import { ApiGroupSchema, ServerRunSchema } from "@idhazh/serve-pipeline-apis/evidence";
import { createServerEventWriter } from "@idhazh/serve-pipeline-apis/events";
import { readFeedApiDiagnostic } from "../scripts/read-feed-api-diagnostic";

const input = z.strictObject({
  directory: z.string(), source: z.string(), run: ServerRunSchema,
  module_line: z.string().optional(), module_lines: z.array(z.string()).optional(),
  group: ApiGroupSchema,
}).parse(await Bun.stdin.json());
const writer = createServerEventWriter({ ...input, decode: readFeedApiDiagnostic });
writer.write({ phase: "starting" });
if (input.group === "delivery") writer.write({ phase: "ready" });
if (input.module_line !== undefined) writer.acceptModuleLine(input.module_line);
for (const line of input.module_lines ?? []) writer.acceptModuleLine(line);
writer.write({ phase: "stopped", exit_code: 0 });
writer.close();
console.log(JSON.stringify({ available: writer.available, filename: writer.filename }));
