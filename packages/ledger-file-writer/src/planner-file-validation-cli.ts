/** Accept a named-file validation request from the native site check. */
import { validatePlannerFiles } from "./validate-planner-files";

const request = JSON.parse(await Bun.stdin.text()) as unknown;
const response = await validatePlannerFiles(process.cwd(), request);
process.stdout.write(`${JSON.stringify(response)}\n`);
