/** Accepts one validated planner maintenance request from the native scheduler. */
import { maintainPlannerPeriod } from "./planner-maintenance";
import { PlannerMaintenanceFailureError } from "./planner-maintenance-failure";

let decoded = false;
try {
  const request = JSON.parse(await Bun.stdin.text()) as unknown;
  decoded = true;
  const response = await maintainPlannerPeriod(process.cwd(), request);
  process.stdout.write(`${JSON.stringify(response)}\n`);
} catch (error) {
  const failure = error instanceof PlannerMaintenanceFailureError ? error
    : new PlannerMaintenanceFailureError(decoded ? "validate-result" : "decode-request",
      error, !decoded && error instanceof SyntaxError ? "invalid-json" : undefined);
  process.stderr.write(`${JSON.stringify(failure.detail)}\n`);
  process.exitCode = 1;
}
