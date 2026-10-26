/** Route an awaited one-shot CLI or the operator HTTP listener. */
import { fileURLToPath } from "node:url";
import { loadPlanInputs } from "./load-plan-inputs";
import type { PlanInputs } from "./load-plan-inputs";
import { parseCliRequest, describePlanError } from "./api/plan-request";
import { servePlan } from "./api/server";
import { runFeedPlan, summarizePlan } from "./run-feed-plan";
import type { PlanRuntime } from "./run-feed-plan";
import { writeJsonLine } from "./logging/structured-logger";
import { loadConfig as loadProbeConfig } from "../../host-probes/src/config";

export async function main(args: readonly string[], options: {
  inputs?: PlanInputs; runtime?: PlanRuntime; output?: (result: ReturnType<typeof summarizePlan>) => void;
} = {}) {
  const { mode, request } = parseCliRequest(args);
  const inputs = options.inputs ?? await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
  let runtime = options.runtime;
  if (runtime === undefined) {
    const git = Bun.spawn(["git", "--no-pager", "rev-parse", "HEAD"], {
      cwd: inputs.root, stdout: "pipe", stderr: "pipe",
    });
    const git_sha = (await new Response(git.stdout).text()).trim();
    if (await git.exited !== 0) throw new Error("git_sha: git could not resolve the checkout commit");
    runtime = {
      git_sha,
      task_profiling: {
        config: await loadProbeConfig(),
        report: profile => writeJsonLine({ event: "task_profile", profile }),
      },
    };
  }
  if (mode === "serve") return servePlan(inputs, runtime);
  const plan = await runFeedPlan(request, inputs, runtime);
  const result = summarizePlan(plan);
  (options.output ?? (value => console.log(JSON.stringify(value))))(result);
  return result;
}

if (import.meta.main) {
  try {
    const result = await main(Bun.argv.slice(2));
    if ("planning_complete" in result && !result.planning_complete) process.exitCode = 2;
  } catch (error) {
    writeJsonLine({ event: "planner_error", ...describePlanError(error, fileURLToPath(new URL("../../../", import.meta.url))) });
    process.exitCode = 1;
  }
}
