/** Run the standalone feed probe CLI using the PR 1 core and no service registration. */
import { resolve, join } from "node:path";
import {
  FeedProbeResultSchema,
  type FeedProbeResult,
} from "@idhazh/common-contracts";
import { probeFeed } from "./feed-probe";
import type { FeedProbeOptions } from "./feed-probe";
import {
  feedProbeCliUsage,
  parseFeedProbeCliArguments,
} from "./cli-options";
import {
  resolveFeedProbeTargets,
  type FeedProbeTarget,
} from "./source-selection";
import {
  buildFeedProbeReport,
  type FeedProbeReport,
} from "./feed-probe-report";
import {
  defaultTraceRelativePath,
  getRepositoryRoot,
  resolveSafeArtifactPath,
  writeJsonLines,
} from "./cli-artifacts";
import {
  writeHumanFeedTable,
  writeJsonSummary,
} from "./cli-output";

export type FeedProbeCliDependencies = {
  repoRoot?: string;
  now?: () => Date;
  probe?: (
    request: unknown,
    signalOrOptions?: AbortSignal | FeedProbeOptions,
  ) => Promise<FeedProbeResult>;
  loadSourceCatalog?: () => Promise<unknown>;
  stdout?: (line: string) => void;
  stderr?: (line: string) => void;
};

function defaultStdout(line: string): void {
  process.stdout.write(line.endsWith("\n") ? line : `${line}\n`);
}

function defaultStderr(line: string): void {
  console.error(line);
}

export async function runFeedProbeCli(
  argv: readonly string[],
  dependencies: FeedProbeCliDependencies = {},
): Promise<number> {
  const parsed = parseFeedProbeCliArguments(argv);
  if (parsed.kind === "help") {
    (dependencies.stdout ?? defaultStdout)(feedProbeCliUsage());
    return 0;
  }
  if (parsed.kind === "error") {
    (dependencies.stderr ?? defaultStderr)(`error: ${parsed.message}`);
    return 2;
  }

  const options = parsed.options;
  const stdout = dependencies.stdout ?? defaultStdout;
  const stderr = dependencies.stderr ?? defaultStderr;
  const repoRoot = resolve(dependencies.repoRoot ?? getRepositoryRoot());
  const now = dependencies.now?.() ?? new Date();

  let targets: FeedProbeTarget[];
  try {
    const catalogLoader = dependencies.loadSourceCatalog
      ?? (() => Bun.file(join(repoRoot, "config", "sources.json")).json());
    targets = await resolveFeedProbeTargets(options, catalogLoader);
  } catch (error) {
    stderr(`error: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }

  let tracePath;
  let reportPath = null;
  try {
    tracePath = resolveSafeArtifactPath(
      repoRoot,
      options.trace ?? defaultTraceRelativePath(now),
      now,
    );
    if (options.report !== null) {
      reportPath = resolveSafeArtifactPath(repoRoot, options.report, now);
      if (reportPath.relative === tracePath.relative) {
        throw new Error("Report and trace paths must be different");
      }
    }
  } catch (error) {
    stderr(`error: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }

  if (options.logLevel === "DEBUG") {
    stderr(`debug: ${targets.length} target(s) selected`);
    for (const target of targets) {
      stderr(`debug: target ${target.feed_id} ${target.url}`);
    }
  }

  const reports: FeedProbeReport[] = [];
  let exceptionFailures = 0;
  const probe = dependencies.probe ?? probeFeed;

  for (const target of targets) {
    const started = performance.now();
    try {
      const result = await probe({
        feed_url: target.url,
        sample_count: options.articles,
      });
      FeedProbeResultSchema.parse(result);
      const totalMs = Math.max(0, Math.round(performance.now() - started));
      const report = buildFeedProbeReport(target.feed_id, target.url, result, totalMs);
      reports.push(report);
      if (options.logLevel === "DEBUG") {
        stderr(`debug: ${target.feed_id} verdict=${report.verdict}`);
      }
    } catch (error) {
      exceptionFailures += 1;
      stderr(`error: ${target.feed_id} ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  try {
    await writeJsonLines(
      tracePath.absolute,
      reports.map(report => JSON.stringify(report)),
    );
    if (reportPath !== null) {
      await writeJsonLines(
        reportPath.absolute,
        reports.map(report => JSON.stringify(report)),
      );
    }
  } catch (error) {
    stderr(`error: ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }

  if (options.logLevel !== "ERROR") {
    if (options.logLevel !== "WARN") stderr(`trace: ${tracePath.relative}`);
    if (reportPath !== null && options.logLevel !== "WARN") stderr(`report: ${reportPath.relative}`);
  }

  writeHumanFeedTable(
    stderr,
    reports,
    options.logLevel,
    reports.filter(report => !report.passed).length + exceptionFailures,
    targets.length,
  );

  if (options.jsonLines) {
    for (const report of reports) stdout(JSON.stringify(report));
  } else if (options.json) {
    writeJsonSummary(stdout, reports);
  }

  return reports.some(report => !report.passed) || exceptionFailures > 0 ? 1 : 0;
}

export function parseCli(options: string[]): Promise<number> {
  return runFeedProbeCli(options);
}
