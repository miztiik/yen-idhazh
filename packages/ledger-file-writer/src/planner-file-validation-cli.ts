/** Accept a named-file validation request from the native site check. */
import { validatePlannerFiles } from "./validate-planner-files";
import { PLANNER_FILE_VALIDATION_VERSION } from "@idhazh/common-contracts";

const args = process.argv.slice(2);
if (args.length && (args.length !== 1 || args[0] !== "--check-runtime")) {
  throw new Error("Expected no arguments or --check-runtime");
}
const request: unknown = args.length
  ? { version: PLANNER_FILE_VALIDATION_VERSION, files: [] }
  : JSON.parse(await Bun.stdin.text());
const response = await validatePlannerFiles(process.cwd(), request);
process.stdout.write(`${JSON.stringify(response)}\n`);
