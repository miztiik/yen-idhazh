/** Which bounded feed and article sample observations the read-only probe can return? */
import { z } from "zod";
import { FEED_PROBE_VERSION } from "../version";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ItemHealthFailureCodeSchema } from "./item-health-failure.schema";
import { PlannerHarvestObservationSchema } from "./planner-stage.schema";
import { CountSchema, UrlSchema } from "./primitives";

export const FEED_PROBE_SAMPLE_DEFAULT = 3 as const;
export const FEED_PROBE_SAMPLE_MAX = 10 as const;

export const FeedProbePaywallEvidenceSchema = PlannerHarvestObservationSchema.shape.paywall_evidence;
export const FeedProbeSampleCountSchema = z.int().min(1).max(FEED_PROBE_SAMPLE_MAX).default(FEED_PROBE_SAMPLE_DEFAULT);
export const FeedProbeRequestSchema = z.strictObject({
  version: z.literal(FEED_PROBE_VERSION).default(FEED_PROBE_VERSION),
  feed_url: UrlSchema,
  sample_count: FeedProbeSampleCountSchema,
}).meta({
  version: FEED_PROBE_VERSION,
  changelog: [
    { version: FEED_PROBE_VERSION, change: "Declare strict feed probe request and result contracts." },
  ],
});
export type FeedProbeRequest = z.infer<typeof FeedProbeRequestSchema>;

export const FeedProbeArticleSampleSchema = z.strictObject({
  readable: z.boolean(),
  dated: z.boolean().nullable(),
  paywall: z.boolean().nullable(),
  paywall_evidence: FeedProbePaywallEvidenceSchema,
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
}).meta({
  version: FEED_PROBE_VERSION,
  changelog: [
    { version: FEED_PROBE_VERSION, change: "Keep article sample evidence body-free and bounded." },
  ],
});
export type FeedProbeArticleSample = z.infer<typeof FeedProbeArticleSampleSchema>;

export const FeedProbeVerdictSchema = z.enum([
  "pass",
  "paywall_confirmed",
  "paywall_not_confirmed",
  "article_fetch_failure",
  "feed_failure",
]);
export const FeedProbeWarningSchema = z.enum([
  "malformed-json-ld",
  "semantic-dom-fallback",
  "no_dated_entries",
]);
export type FeedProbeVerdict = z.infer<typeof FeedProbeVerdictSchema>;
export type FeedProbeWarning = z.infer<typeof FeedProbeWarningSchema>;

export const FeedProbeResultSchema = z.strictObject({
  version: z.literal(FEED_PROBE_VERSION).default(FEED_PROBE_VERSION),
  verdict: FeedProbeVerdictSchema,
  passed: z.boolean(),
  paywall_confirmed: z.boolean(),
  sample_count: CountSchema,
  readable_count: CountSchema,
  paywall_sample_count: CountSchema,
  paywall_evidence: FeedProbePaywallEvidenceSchema,
  failure_code: ItemHealthFailureCodeSchema.nullable(),
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  warnings: z.array(FeedProbeWarningSchema).max(5).default([]),
  samples: z.array(FeedProbeArticleSampleSchema).max(FEED_PROBE_SAMPLE_MAX).default([]),
}).superRefine((value, ctx) => {
  if (value.sample_count !== value.samples.length) {
    ctx.addIssue({ code: "custom", message: "sample_count must equal the bounded article sample list length" });
  }
  const readableCount = value.samples.filter(sample => sample.readable).length;
  const paywallSampleCount = value.samples.filter(sample => sample.paywall === true).length;
  if (value.readable_count !== readableCount) {
    ctx.addIssue({ code: "custom", message: "readable_count must count readable article samples" });
  }
  if (value.paywall_sample_count !== paywallSampleCount) {
    ctx.addIssue({ code: "custom", message: "paywall_sample_count must count paywall article samples" });
  }
  if (value.passed !== (readableCount > 0)) {
    ctx.addIssue({ code: "custom", message: "passed must follow the readable article count" });
  }
  if (value.verdict === "pass" && !value.passed) {
    ctx.addIssue({ code: "custom", message: "a pass verdict requires one readable article" });
  }
  const evidenceCounts = new Map<string, number>();
  for (const sample of value.samples) {
    if (sample.paywall !== true || !["json-ld", "configured-marker"].includes(sample.paywall_evidence)) continue;
    evidenceCounts.set(sample.paywall_evidence, (evidenceCounts.get(sample.paywall_evidence) ?? 0) + 1);
  }
  const matchingPaywallEvidence = [...evidenceCounts.values()].some(count => count >= 2);
  if (value.paywall_confirmed !== matchingPaywallEvidence) {
    ctx.addIssue({ code: "custom", message: "paywall_confirmed requires two matching paywall evidence samples" });
  }
  if (value.verdict === "paywall_confirmed" && !matchingPaywallEvidence) {
    ctx.addIssue({ code: "custom", message: "a paywall_confirmed verdict requires matching evidence" });
  }
  if (value.verdict === "paywall_not_confirmed" && matchingPaywallEvidence) {
    ctx.addIssue({ code: "custom", message: "a paywall_not_confirmed verdict cannot have matching evidence" });
  }
}).meta({
  version: FEED_PROBE_VERSION,
  changelog: [
    { version: FEED_PROBE_VERSION, change: "Declare strict feed probe request and result contracts." },
  ],
});
export type FeedProbeResult = z.infer<typeof FeedProbeResultSchema>;
