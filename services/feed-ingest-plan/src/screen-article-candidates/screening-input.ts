/** Which bounded candidate, harvest, discovery and run inputs can screening trust? */
import { z } from "zod";
import {
  FeedIngestCandidateSchema, NonEmptySchema,
  NonNegativeSchema, RunIdSchema, Sha256Schema,
  DateStampSchema, ItemHealthFailureCodeSchema, CountSchema,
} from "@idhazh/common-contracts";
import { HarvestObservationSchema } from "@idhazh/feed-ingest-plan/harvest-feeds";
import type { HarvestObservation } from "@idhazh/feed-ingest-plan/harvest-feeds";
import { loadPlanningConfig } from "../config/resolve-policy";
import type { PlanningConfig } from "../config/resolve-policy";
import { DiscoveredEvidenceSchema } from "./discovered-evidence";
import type { DiscoveredEvidence } from "./discovered-evidence";
import { UtcInstantSchema } from "../utc-instant";
import type { FeedIngestCandidate } from "@idhazh/common-contracts";

export type { HarvestObservation } from "@idhazh/feed-ingest-plan/harvest-feeds";

const ScreeningRunSchema = z.strictObject({
  now: UtcInstantSchema,
  run_id: RunIdSchema,
  correlation_id: NonEmptySchema,
});
// Only the existing authored setting used by this reader is declared.
const ClockConfigSchema = z.object({ collect: z.object({ max_future_hours: NonNegativeSchema }) });
const ExclusionsSchema = z.strictObject({
  published_window_days: CountSchema, published_on: z.record(Sha256Schema, DateStampSchema),
  settled_failure_codes: z.record(Sha256Schema, ItemHealthFailureCodeSchema),
  matched_published_keys: z.record(Sha256Schema, Sha256Schema).optional(),
  matched_failure_keys: z.record(Sha256Schema, Sha256Schema).optional(),
});

export type ScreeningInput = {
  candidates: readonly FeedIngestCandidate[];
  observations: Readonly<Record<string, HarvestObservation>>;
  discovered: DiscoveredEvidence;
  planning: PlanningConfig;
  clock_config: { collect: { max_future_hours: number } };
  run: { now: string; run_id: string; correlation_id: string };
  exclusions?: z.infer<typeof ExclusionsSchema>;
};

export function validateScreeningInput(input: ScreeningInput) {
  const candidates = z.array(FeedIngestCandidateSchema).parse(input.candidates);
  const observations = z.record(Sha256Schema, HarvestObservationSchema).parse(input.observations);
  const discovered = DiscoveredEvidenceSchema.parse(input.discovered);
  const run = ScreeningRunSchema.parse(input.run);
  const planning = loadPlanningConfig(input.planning.config);
  const clockConfig = ClockConfigSchema.parse(input.clock_config);
  const exclusions = input.exclusions === undefined ? undefined : ExclusionsSchema.parse(input.exclusions);
  const ids = new Set<string>();
  for (const candidate of candidates) {
    UtcInstantSchema.parse(candidate.fetched_at);
    if (candidate.published_at !== null) UtcInstantSchema.parse(candidate.published_at);
    if (candidate.run_id !== run.run_id || candidate.correlation_id !== run.correlation_id) {
      throw new Error(`candidates.${candidate.candidate_id}: run_id/correlation_id must match run`);
    }
    if (ids.has(candidate.candidate_id)) throw new Error(`candidates.${candidate.candidate_id}: duplicate candidate_id`);
    ids.add(candidate.candidate_id);
  }
  for (const id of Object.keys(observations)) {
    if (!ids.has(id)) throw new Error(`observations.${id}: no candidate in this screening batch`);
    const observation = observations[id];
    if (!observation || observation.candidate_id !== id) {
      throw new Error(`observations.${id}.candidate_id: must match its key`);
    }
    UtcInstantSchema.parse(observation.observed_at);
  }
  return { candidates, observations, discovered, planning, run, exclusions, maxFutureHours: clockConfig.collect.max_future_hours };
}
