/** Accepts one validated planner maintenance request from the native scheduler. */
import { maintainPlannerPeriod } from "./planner-maintenance";

const request = JSON.parse(await Bun.stdin.text()) as unknown;
const response = await maintainPlannerPeriod(process.cwd(), request);
process.stdout.write(`${JSON.stringify(response)}\n`);
