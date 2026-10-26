/** Measure only the chosen article Markdown before final URL scrubbing destroys its links. */
import { ArticleContentEvidenceSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";

export function measureArticleContent(
  markdown: string, pressRelease: FeedIngestConfig["content_filters"]["press_release"],
) {
  let linkedLabelChars = 0;
  let listItems = 0;
  const countLabel = (label: string) => { linkedLabelChars += label.length; return ""; };
  Bun.markdown.render(markdown, {
    link: countLabel, image: countLabel,
    listItem: () => { listItems++; return ""; },
  }, { autolinks: false });
  const sample = markdown.slice(0, pressRelease.sample_chars);
  const markerIndex = pressRelease.markers.findIndex(marker => new RegExp(
    `\\b${marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i",
  ).test(sample));
  return ArticleContentEvidenceSchema.parse({
    markdown_chars: markdown.length, linked_label_chars: linkedLabelChars,
    // Two decimal places are the prototype metric's precision, not an admission threshold.
    link_density: Number((linkedLabelChars / Math.max(1, markdown.length)).toFixed(2)),
    list_items: listItems, opening_sample_chars: sample.length,
    press_release_marker_index: markerIndex < 0 ? null : markerIndex,
  });
}
