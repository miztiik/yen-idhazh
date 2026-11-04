/** Preserve real extracted entity evidence and readable reports after later native persistence failure. */
import { expect, test } from "bun:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { parseHTML } from "linkedom";
import { PLANNER_API_PREFIX, readArticleEntities } from "@idhazh/common-contracts";
import { createPlanApp } from "../src/api/server";
import { articleEntitiesFilename, articleEntitiesPath } from "../src/selected-artifact-path";
import { requestPlannerHttp } from "../scripts/feed-ingest-plan-http-client";
import { writeWorkflowReport } from "../scripts/feed-ingest-plan-report";
import { prepareWorkflowArtifacts, ARTICLE_ENTITY_ARTIFACT_DIRECTORY } from "../scripts/feed-ingest-plan-artifacts";
import { publishWorkflowUploadInventories } from "../scripts/feed-ingest-plan-upload-inventory";
import { finishRunOutput } from "../scripts/finish-run-output";
import { recordedPlan } from "./plan-recordings";
import { metadataRegistrations } from "./host-recordings";

test("full sanitized body names survive later failure, artifact preparation and failed upload confirmation", async () => {
  const fixture = await recordedPlan();
  fixture.runtime.attempt = 3;
  fixture.inputs.harvest.config.partition.enabled = false;
  const directory = join(fixture.directory, "feed-ingest-plan");
  fixture.inputs.outputRoot = join(directory, "state");
  const recorded = z.strictObject({
    title: z.string(), article_text: z.string(), article_tail: z.string(), excluded_script: z.string(),
    empty_title: z.string(), empty_body: z.string(),
  }).parse(await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/article-entities.json", import.meta.url)).json());
  const { document } = parseHTML(fixture.transport.recordings.bodies.article);
  const article = document.querySelector("article");
  const heading = document.querySelector("h1");
  if (article === null || heading === null) throw new Error("Expected the recorded article and heading");
  heading.textContent = recorded.title;
  document.title = recorded.title;
  const tail = document.createElement("p");
  tail.textContent = recorded.article_tail;
  article.append(tail);
  const script = document.createElement("script");
  script.textContent = recorded.excluded_script;
  article.append(script);
  fixture.transport.recordings.bodies.article = document.toString();
  fixture.transport.recordings.bodies.rss = `<rss version="2.0"><channel><title>Recorded article names</title>
    <item><title>${recorded.title}</title><link>https://news.example/second</link>
    <pubDate>Wed, 21 Oct 2026 23:00:00 GMT</pubDate></item></channel></rss>`;
  await mkdir(join(fixture.directory, "config"), { recursive: true });
  await writeFile(join(fixture.directory, "config", "feed-ingest-plan-service.json"), JSON.stringify(fixture.inputs.settings));
  await writeFile(join(fixture.directory, "config", "feed-ingest-plan.json"), JSON.stringify(fixture.inputs.harvest.config));
  await mkdir(join(directory, "state", "raw", "feed-ingest-plan"), { recursive: true });
  await writeFile(join(directory, "state", "raw", "feed-ingest-plan", "selected-articles"), "Native write obstruction");
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  const server = Bun.serve({
    hostname: "127.0.0.1", port: 0, idleTimeout: 0,
    fetch(request, listener) {
      return app.fetch(request, { beginPlanning: () => listener.timeout(request, 0),
        stage_origin: `http://127.0.0.1:${listener.port}` });
    },
  });
  try {
    const result = await requestPlannerHttp(`http://127.0.0.1:${server.port}${PLANNER_API_PREFIX}`,
      fixture.inputs, { article_limit: 1 }, directory);
    expect(result.http_status).toBe(500);
    expect(result.summary.planning_complete).toBe(false);
    expect(result.summary.selected_count).toBe(1);
    expect(result.summary.failure).not.toBeNull();
    expect(result.summary.failure?.operation).toBe("persist");
    const context = { run_id: result.summary.run_id, writer: { attempt: result.summary.attempt } };
    const source = join(fixture.directory, articleEntitiesPath(fixture.inputs.settings.inputs.artifact_root, context));
    const original = await readFile(source, "utf8");
    const records = original.trim().split("\n").map(line => readArticleEntities(JSON.parse(line)));
    expect(records).toHaveLength(1);
    const entity = records[0];
    if (entity === undefined) throw new Error("Expected the article's entity record");
    const articleFetch = fixture.events.find(event => event.data.operation === "fetch"
      && event.data.details.document_kind === "article" && event.data.phase === "completed");
    expect(articleFetch).toBeDefined();
    expect(entity).toMatchObject({
      run_id: result.summary.run_id, attempt: 3, status: "complete",
      candidate_id: articleFetch!.data.details.candidate_id,
      title_status: "complete", body_status: "complete",
    });
    for (const name of [
      { kind: "person", scope: "title", text: "Ada Lovelace" },
      { kind: "place", scope: "title", text: "London" },
      { kind: "person", scope: "body", text: "Marie Curie" },
      { kind: "place", scope: "body", text: "Tokyo" },
      { kind: "organization", scope: "body", text: "United Nations" },
    ] as const) expect(entity.entities).toContainEqual(name);
    expect(original).not.toContain("Hidden Person");
    expect(original).not.toContain("Rome");
    expect(original).not.toContain("article_text");
    expect(JSON.stringify(fixture.events)).not.toContain("Marie Curie");
    expect(JSON.stringify(fixture.events)).not.toMatch(/[A-Za-z]:[\\/]/);
    const summaryPath = join(directory, "job-summary.md");
    const report = await writeWorkflowReport({
      root: fixture.directory, directory, summaryPath,
      runNumber: "700", runId: result.summary.run_id,
    });
    expect(report.status).toBe("written");
    const identity = { run_id: result.summary.run_id, attempt: 3, git_sha: fixture.runtime.git_sha };
    const outputs = await prepareWorkflowArtifacts({
      root: fixture.directory, directory, runNumber: "700", attempt: 3,
      identity, registrations: await metadataRegistrations(), runId: result.summary.run_id,
    });
    const filename = articleEntitiesFilename(context);
    expect(outputs.article_entities).toBe(`${ARTICLE_ENTITY_ARTIFACT_DIRECTORY}/${filename}`);
    const entityOutput = outputs.article_entities;
    const reportOutput = outputs.report;
    if (entityOutput === undefined || reportOutput === undefined) throw new Error("Expected the prepared entity file and report");
    expect(await readFile(join(directory, entityOutput), "utf8")).toBe(original);
    const markdown = await readFile(join(directory, reportOutput), "utf8");
    expect(markdown).toContain("Execution failure");
    expect(markdown).toContain("An operating system request failed");
    expect(markdown).toContain(filename);
    expect(markdown).not.toContain("Marie Curie");
    expect(markdown).not.toContain("Hidden Person");
    expect(markdown).not.toMatch(/(?:^|[\s"'(\[{])[A-Za-z]:[\\/]/m);
    const files: string[] = [];
    await publishWorkflowUploadInventories({ directory, runNumber: "700",
      write: event => { if (typeof event.data.details.file === "string") files.push(event.data.details.file); } });
    expect(files).toContain(filename);
    await expect(finishRunOutput({
      root: fixture.directory, temporaryRoot: fixture.directory,
      runNumber: "700", attempt: 3, gitSha: fixture.runtime.git_sha, runId: result.summary.run_id,
      collectionOutcome: "failure", planningComplete: "false", finalizationOutcome: "failure",
      uploadOutcome: "success", artifactId: "123",
      articleEntities: entityOutput, entityUploadOutcome: "failure",
    })).rejects.toThrow("Run output is incomplete");
    expect(await readFile(source, "utf8")).toBe(original);
  } finally {
    await server.stop(true);
    await app.close();
    await fixture.close();
  }
});
