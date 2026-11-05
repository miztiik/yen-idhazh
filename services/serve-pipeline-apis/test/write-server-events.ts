/** Exercise the real event writer in a child so stderr is observed without replacement. */
import { ServerRunSchema } from "../src/server-evidence";
import { createServerEventWriter } from "../src/write-server-event";
import { z } from "zod";

const input = z.strictObject({
  directory: z.string(), source: z.string(), run: ServerRunSchema, module_line: z.string().optional(),
}).parse(await Bun.stdin.json());
const writer = createServerEventWriter({ ...input, group: "machine" });
writer.write({ phase: "starting" });
if (input.module_line !== undefined) writer.acceptModuleLine(input.module_line);
writer.write({ phase: "stopped", exit_code: 0 });
writer.close();
console.log(JSON.stringify({ available: writer.available, filename: writer.filename }));
