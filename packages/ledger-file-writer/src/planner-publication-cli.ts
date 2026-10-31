/** Project only current planner files from one build's named publication copy. */
import { selectPlannerPublication } from "./planner-publication";

process.stdout.write(`${JSON.stringify(await selectPlannerPublication(process.cwd(), JSON.parse(await Bun.stdin.text())))}\n`);
