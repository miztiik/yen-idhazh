/** Which reviewed publisher identities are defined and referenced by the source catalog? */
import { z } from "zod";
import {
  DateStampSchema, LifecycleStatusSchema, NonEmptySchema, SlugSchema,
} from "@idhazh/common-contracts";

export const PublisherIdSchema = SlugSchema;

export const PublisherDefinitionSchema = z.strictObject({
  id: PublisherIdSchema,
  display_name: NonEmptySchema,
  added_on: DateStampSchema.nullable().default(null),
  status: LifecycleStatusSchema.nullable().default(null),
  retired_on: DateStampSchema.nullable().default(null),
  retirement_reason: z.string().min(1).nullable().default(null).refine(
    value => value === null || (value.trim().length > 0 && value === value.toLowerCase()),
    "publisher retirement_reason must be nonempty lowercase text",
  ),
}).superRefine((publisher, ctx) => {
  const retired = publisher.status === "retired";
  const hasRetirementFields = publisher.retired_on !== null || publisher.retirement_reason !== null;
  if (hasRetirementFields && (publisher.retired_on === null || publisher.retirement_reason === null)) {
    ctx.addIssue({ code: "custom", message: "publisher retirement needs both retired_on and retirement_reason" });
  }
  if (retired && publisher.added_on !== null && !hasRetirementFields) {
    ctx.addIssue({ code: "custom", message: "a newly retired publisher needs retired_on and retirement_reason" });
  }
  if (publisher.status !== "retired" && (publisher.retired_on !== null || publisher.retirement_reason !== null)) {
    ctx.addIssue({ code: "custom", message: "retirement fields are only meaningful on a retired publisher" });
  }
  if (publisher.retired_on !== null && publisher.added_on !== null && publisher.retired_on < publisher.added_on) {
    ctx.addIssue({ code: "custom", message: "retired_on cannot precede added_on" });
  }
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
