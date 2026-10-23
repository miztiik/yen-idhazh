/** Which headline matches and optional feed votes were actually observed? */
import { z } from "zod";
import { NonEmptySchema, PositiveSchema, SlugSchema, reject } from "./primitives";

export const WeightedLensObservationSchema = z.strictObject({
  id: SlugSchema, weight: PositiveSchema,
});
export const SalienceFeedObservationSchema = z.strictObject({
  feed_id: SlugSchema, available: z.boolean(), voted: z.boolean().nullable(),
  unavailable_reason: NonEmptySchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.available !== (value.voted !== null)) reject(ctx, "available salience requires a measured vote");
  if (value.available !== (value.unavailable_reason === null)) reject(ctx, "unavailable salience requires a reason");
});
export const PlanningObservationsSchema = z.strictObject({
  feed_headline: NonEmptySchema.nullable(),
  best_weighted_lens: WeightedLensObservationSchema.nullable(),
  watchlist_match: z.boolean().nullable(),
  salience: z.array(SalienceFeedObservationSchema),
  salience_available: z.boolean(), on_front_page: z.boolean().nullable(),
  salience_unavailable_reason: NonEmptySchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.salience_available !== (value.on_front_page !== null)) reject(ctx, "available salience requires a measured front-page observation");
  if (value.salience_available !== (value.salience_unavailable_reason === null)) reject(ctx, "unavailable salience requires a reason");
  if (value.salience_available) {
    if (!value.salience.length || value.salience.some(feed => !feed.available)) reject(ctx, "salience requires every configured feed to be available");
    if (value.on_front_page !== value.salience.some(feed => feed.voted)) reject(ctx, "front-page observation must match measured votes");
  }
  if (new Set(value.salience.map(feed => feed.feed_id)).size !== value.salience.length) reject(ctx, "salience feed ids must be distinct");
  if (value.feed_headline === null && (value.best_weighted_lens !== null || value.watchlist_match !== null)) reject(ctx, "headline matches require the original feed headline");
});
export type PlanningObservations = z.infer<typeof PlanningObservationsSchema>;
