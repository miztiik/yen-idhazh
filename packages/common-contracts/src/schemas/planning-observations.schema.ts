/** Which headline matches and optional feed votes were actually observed? */
import { z } from "zod";
import { NonEmptySchema, PositiveSchema, SlugSchema, reject } from "./primitives";

export const WeightedLensObservationSchema = z.strictObject({
  id: SlugSchema, weight: PositiveSchema,
});
export const SalienceFeedObservationSchema = z.strictObject({
  feed_id: SlugSchema, available: z.boolean().describe("Complete voting input, independent of a known positive vote."), voted: z.boolean().nullable(),
  unavailable_reason: NonEmptySchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.available && value.voted === null) reject(ctx, "available salience requires a measured vote");
  if (!value.available && value.voted === false) reject(ctx, "incomplete salience cannot prove an absent vote");
  if (value.available !== (value.unavailable_reason === null)) reject(ctx, "unavailable salience requires a reason");
});
export const PlanningObservationsSchema = z.strictObject({
  feed_headline: NonEmptySchema.nullable(),
  best_weighted_lens: WeightedLensObservationSchema.nullable(),
  watchlist_match: z.boolean().nullable(),
  salience: z.array(SalienceFeedObservationSchema),
  salience_available: z.boolean().describe("All configured voting inputs are complete."), on_front_page: z.boolean().nullable(),
  salience_unavailable_reason: NonEmptySchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.salience_available !== (value.salience_unavailable_reason === null)) reject(ctx, "unavailable salience requires a reason");
  if (value.salience_available) {
    if (!value.salience.length || value.salience.some(feed => !feed.available)) reject(ctx, "salience requires every configured feed to be available");
  }
  const expected = value.salience.some(feed => feed.voted === true) ? true : value.salience_available ? false : null;
  if (value.on_front_page !== expected) reject(ctx, "front-page observation must preserve positive votes and unknown absence");
  if (new Set(value.salience.map(feed => feed.feed_id)).size !== value.salience.length) reject(ctx, "salience feed ids must be distinct");
  if (value.feed_headline === null && (value.best_weighted_lens !== null || value.watchlist_match !== null)) reject(ctx, "headline matches require the original feed headline");
});
export type PlanningObservations = z.infer<typeof PlanningObservationsSchema>;
