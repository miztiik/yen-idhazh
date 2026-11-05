/** Observe native diagnostic projection through the actual shared stderr mirror. */
import { z } from "zod";
import { ServerRunSchema } from "@idhazh/serve-pipeline-apis/evidence";
import { createServerEventWriter } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "../src/api/read-machine-api-diagnostic";

const input = z.strictObject({
  directory: z.string(), source: z.string(), run: ServerRunSchema,
  module_line: z.string().optional(), module_lines: z.array(z.string()).optional(),
}).parse(await Bun.stdin.json());
const writer = createServerEventWriter({ ...input, group: "machine", decode: readMachineApiDiagnostic });
writer.write({ phase: "starting" });
if (input.module_line !== undefined) {
  writer.acceptModuleLine(input.module_line);
  writer.acceptModuleLine(input.module_line);
}
for (const line of input.module_lines ?? []) writer.acceptModuleLine(line);
writer.write({ phase: "stopped", exit_code: 0 });
writer.close();
console.log(JSON.stringify({ available: writer.available, profile_count: writer.reportedProfiles.length }));
