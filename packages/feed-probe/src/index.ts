/** Export the standalone feed probe operation and its native contracts. */
export { feedProbe, probeFeed } from "./feed-probe";
export type { FeedProbeOptions } from "./feed-probe";
export {
  FEED_PROBE_SAMPLE_DEFAULT,
  FEED_PROBE_SAMPLE_MAX,
  FEED_PROBE_VERSION,
  FeedProbeArticleSampleSchema,
  FeedProbePaywallEvidenceSchema,
  FeedProbeRequestSchema,
  FeedProbeResultSchema,
  FeedProbeSampleCountSchema,
  FeedProbeVerdictSchema,
  FeedProbeWarningSchema,
} from "@idhazh/common-contracts";
export type {
  FeedProbeArticleSample,
  FeedProbeRequest,
  FeedProbeResult,
  FeedProbeVerdict,
  FeedProbeWarning,
} from "@idhazh/common-contracts";
export {
  feedProbeCliUsage,
  parseFeedProbeCliArguments,
  parseCliArguments,
} from "./cli-options";
export type {
  FeedProbeCliOptions,
  FeedProbeCliParseResult,
  FeedProbeLogLevel,
  SourceSelectionMode,
} from "./cli-options";
export {
  deriveAdHocSourceId,
  deriveSourceId,
  deriveSourceIdCandidates,
  loadSourceCatalog,
  normalizeFeedAddress,
  normalizeFeedUrl,
  parseSourceCatalog,
  resolveFeedProbeTargets,
} from "./source-selection";
export type {
  CatalogSource,
  FeedProbeTarget,
} from "./source-selection";
export {
  FeedProbeReportSchema,
  FeedProbeReportSummarySchema,
  buildFeedProbeReport,
  buildFeedProbeReportSummary,
} from "./feed-probe-report";
export type {
  FeedProbeReport,
  FeedProbeReportSummary,
} from "./feed-probe-report";
export {
  defaultTraceRelativePath,
  getRepositoryRoot,
  resolveSafeArtifactPath,
  writeJsonLines,
} from "./cli-artifacts";
export {
  writeHumanFeedTable,
  writeJsonSummary,
} from "./cli-output";
export {
  parseCli,
  runFeedProbeCli,
} from "./cli";
export type {
  FeedProbeCliDependencies,
} from "./cli";
