/** Which bounded numeric facts describe the extracted Markdown without retaining its links or prose? */
import { z } from "zod";
import { CountSchema, reject } from "./primitives";

export const ArticleContentEvidenceSchema = z.strictObject({
  markdown_chars: CountSchema,
  linked_label_chars: CountSchema,
  link_density: z.number().finite().min(0).max(1),
  list_items: CountSchema,
  opening_sample_chars: CountSchema,
  press_release_marker_index: CountSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.linked_label_chars > value.markdown_chars) reject(ctx, "linked labels cannot exceed extracted Markdown");
  if (value.opening_sample_chars > value.markdown_chars) reject(ctx, "opening sample cannot exceed extracted Markdown");
  const density = Number((value.linked_label_chars / Math.max(1, value.markdown_chars)).toFixed(2));
  if (value.link_density !== density) reject(ctx, "link_density must match the rounded character counts", ["link_density"]);
});
export type ArticleContentEvidence = z.infer<typeof ArticleContentEvidenceSchema>;
