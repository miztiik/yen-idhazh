/** Observe native diagnostic projection through the actual shared stderr mirror. */
import { z } from "zod";
import { ServerRunSchema } from "@idhazh/serve-pipeline-apis/evidence";
import { createServerEventWriter } from "@idhazh/serve-pipeline-apis/events";
import { readMachineApiDiagnostic } from "../src/api/read-machine-api-diagnostic";

const input = z.strictObject({
  directory: z.string(), source: z.string(), run: ServerRunSchema, module_line: z.string(),
}).parse(await Bun.stdin.json());
const writer = createServerEventWriter({ ...input, group: "machine", decode: readMachineApiDiagnostic });
writer.write({ phase: "starting" });
writer.acceptModuleLine(input.module_line);
writer.acceptModuleLine(input.module_line);
writer.write({ phase: "stopped", exit_code: 0 });
writer.close();
console.log(JSON.stringify({ available: writer.available, profile_count: writer.reportedProfiles.length }));
