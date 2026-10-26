/** Which completed files remain recoverable even when another producer fails? */
import { join } from "node:path";
import { z } from "zod";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { WorkflowResourcesSchema } from "./feed-ingest-plan-workflow-resources";
import { ExecutionIdentitySchema, hostWriter, readMetadataRegistrations, verifyMetadataFile } from "./feed-ingest-plan-metadata";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";
import { verifyHostFingerprint } from "./feed-ingest-plan-host-verification";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";

export async function readWorkflowPublicationContext(input: {
  root: string; directory: string; runNumber: string; attempt: number;
}) {
  const resources = z.object({ host_request: WorkflowResourcesSchema.shape.host_request })
    .parse(await Bun.file(join(input.directory, "resources.json")).json());
  const { run_id, attempt, git_sha } = resources.host_request.writer;
  const identity = ExecutionIdentitySchema.parse({ run_id, attempt, git_sha });
  z.string().regex(/^\d+$/).parse(input.runNumber);
  const child = Bun.spawn(["git", "rev-parse", "HEAD"], { cwd: input.root, stdout: "pipe", stderr: "pipe" });
  const [sha] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
  if (await child.exited !== 0 || sha.trim() !== identity.git_sha || input.attempt !== identity.attempt
    || identity.run_id !== `${resources.host_request.date}-${input.runNumber}`
    || JSON.stringify(resources.host_request.writer) !== JSON.stringify(hostWriter(identity))) {
    throw new Error("Workflow metadata differs from the executed revision, run or attempt");
  }
  const settings = ServiceSettingsSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan-service.json")).json());
  return { identity, registrations: await readMetadataRegistrations(join(input.root, settings.inputs.registrations)) };
}

export async function collectWorkflowFiles(input: {
  root: string; directory: string; identity: ExecutionIdentity; registrations: MetadataRegistrations;
}) {
  const stateRoot = join(input.directory, "state");
  const paths: string[] = [];
  const failures: unknown[] = [];
  let response: ReturnType<typeof PlanResponseSchema.parse> | undefined;
  const resources = Bun.file(join(input.directory, "resources.json"));
  if (await resources.exists()) {
    try {
      const evidence = WorkflowResourcesSchema.parse(await resources.json());
      if (evidence.host.status === "recorded") paths.push(...await verifyHostFingerprint(stateRoot,
        { ...evidence.host, status: "written" }, input.registrations, input.identity));
      else if (evidence.host.status === "failed") throw new Error(evidence.host.reason);
    } catch (error) { failures.push(error); }
  }
  const result = Bun.file(join(input.directory, "response.json"));
  if (await result.exists()) {
    try {
      const parsed = PlanResponseSchema.parse(await result.json());
      if (parsed.run_id !== input.identity.run_id || parsed.attempt !== input.identity.attempt) {
        throw new Error("Planner result belongs to another execution");
      }
      const registrations = input.registrations;
      const verified = await verifyPlanningCompletion(stateRoot, parsed, {
        discovered_articles: registrations["discovered-articles"], selected_articles: registrations["selected-articles"],
        feed_health_state: registrations["feed-health-state"], plan_runs: registrations["plan-runs"],
      }, input.root);
      for (const path of Object.values(verified).flatMap(result => result?.files ?? [])) {
        await verifyMetadataFile(stateRoot, path, registrations, input.identity);
        paths.push(path);
      }
      response = parsed;
    } catch (error) { failures.push(error); }
  }
  if (new Set(paths).size !== paths.length) throw new Error("Workflow metadata repeats a completed file");
  return { paths, response, failures };
}
