/** Which completed files remain recoverable even when another producer fails? */
import { join } from "node:path";
import { z } from "zod";
import { PlannerSavedResponseSchema } from "@idhazh/common-contracts";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { verifyWorkflowHostRequest, WorkflowHostFingerprintSchema } from "./feed-ingest-plan-host-fingerprint";
import { ExecutionIdentitySchema, readMetadataRegistrations, verifyMetadataFile } from "./feed-ingest-plan-metadata";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";
import { verifyHostFingerprint } from "./feed-ingest-plan-host-verification";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";

export async function readWorkflowDeliveryContext(input: {
  root: string; directory: string; runNumber: string; attempt: number; gitSha: string; job: string;
}) {
  const runNumber = z.string().regex(/^\d+$/).parse(input.runNumber);
  const host = z.object({ host_request: WorkflowHostFingerprintSchema.shape.host_request })
    .parse(await Bun.file(join(input.directory, "host-fingerprint.json")).json());
  const identity = ExecutionIdentitySchema.parse({
    run_id: `${host.host_request.date}-${runNumber}`, attempt: input.attempt, git_sha: input.gitSha, job: input.job,
  });
  verifyWorkflowHostRequest(host.host_request, identity);
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
  const hostFile = Bun.file(join(input.directory, "host-fingerprint.json"));
  if (await hostFile.exists()) {
    try {
      const evidence = WorkflowHostFingerprintSchema.parse(await hostFile.json());
      verifyWorkflowHostRequest(evidence.host_request, input.identity);
      if (evidence.host.status === "recorded") paths.push(...await verifyHostFingerprint(stateRoot,
        { ...evidence.host, status: "written" }, input.registrations, input.identity));
      else if (evidence.host.status === "failed") throw new Error(evidence.host.reason);
    } catch (error) { failures.push(error); }
  }
  const result = Bun.file(join(input.directory, "response.json"));
  if (await result.exists()) {
    try {
      const saved = PlannerSavedResponseSchema.parse(await result.json());
      if (!("planning_complete" in saved)) {
        const execution = saved.failure?.execution;
        if (execution?.run_id != null && execution.run_id !== input.identity.run_id
          || execution?.attempt != null && execution.attempt !== input.identity.attempt
          || execution?.git_sha != null && execution.git_sha !== input.identity.git_sha) {
          throw new Error("Planner failure belongs to another execution");
        }
        return { paths, response, failures };
      }
      const parsed = saved;
      if (parsed.run_id !== input.identity.run_id || parsed.attempt !== input.identity.attempt) {
        throw new Error("Planner result belongs to another execution");
      }
      const registrations = input.registrations;
      const verified = await verifyPlanningCompletion(stateRoot, parsed, {
        discovered_articles: registrations["discovered-articles"], selected_articles: registrations["selected-articles"],
        rejected_articles: registrations["rejected-articles"],
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
