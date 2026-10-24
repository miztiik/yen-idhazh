/** Which reviewed publisher identities are defined and referenced by the source catalog? */
import { z } from "zod";
import {
  NonEmptySchema, SlugSchema,
} from "@idhazh/common-contracts";

export const PublisherIdSchema = SlugSchema;

export const PublisherDefinitionSchema = z.strictObject({
  id: PublisherIdSchema,
  display_name: NonEmptySchema,
});

export type PublisherDefinition = z.infer<typeof PublisherDefinitionSchema>;

export function validatePublisherReferences(
  publishers: readonly PublisherDefinition[],
  feeds: readonly { id: string; publisher_id: string | null }[],
) {
  const ids = publishers.map(publisher => publisher.id);
  if (new Set(ids).size !== ids.length) throw new Error("publisher ids must be distinct");
  const known = new Set(ids);
  for (const feed of feeds) {
    if (feed.publisher_id !== null && !known.has(feed.publisher_id)) {
      throw new Error(`source.${feed.id}.publisher_id: unknown publisher`);
    }
  }
}
