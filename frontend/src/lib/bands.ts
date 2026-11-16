/** Shared labels for operator confidence and publisher provenance. */

import type { ConfidenceBand, SourceKind } from './payload/types';
import taxonomy from '../../../config/taxonomy.json' with { type: 'json' };

export interface BandCopy {
	label: string;
}

export const BANDS: Record<ConfidenceBand, BandCopy> = {
	high: { label: 'Matches the source' },
	medium: { label: 'Mostly matches the source' },
	low: { label: 'May not match the source' }
};

/** Who is speaking. A vendor's own copy must not read like a reporter's. */
export interface SourceKindDefinition {
	id: string;
	display_name: string;
	status: string;
	retired_on: string | null;
	show_on_item: boolean;
	counts_as_reporting: boolean;
	requires_reporting_for_lead: boolean;
}

export function sourceKindLabels(definitions: readonly SourceKindDefinition[]) {
	return Object.fromEntries(definitions.map((entry) => [entry.id, entry.display_name]));
}

export function visibleSourceKinds(definitions: readonly SourceKindDefinition[]): SourceKind[] {
	return definitions.filter((entry) => entry.show_on_item).map((entry) => entry.id);
}

export const SOURCE_KINDS = sourceKindLabels(taxonomy.source_kinds);

/** Only kinds where the speaker has a stake worth naming get a label on the item.
 *
 * Four, since 2026-09-01. `government` and `research` joined the first two
 * because a ministry's press release and a paper nobody has reviewed are both
 * a speaker with something to gain, and both were arriving in the same typeface
 * as a reporter who checked.
 *
 * What it costs the page, over the 12 committed days and 4,598 items on
 * 2026-09-01: 340 more items carry a label - 241 `research` and 99 `government` -
 * so 696 in all, 15.1 percent of them, up from 356 and 7.7 percent. The 340 is
 * the part that holds still; the shares move with every publish.
 *
 * `reporting` and `analysis` stay out, and the share above is why. The label is
 * a warning, so it only works while most items do not carry one - `reporting`
 * alone is 79.2 percent of the tree, and labelling it would turn the mark into
 * wallpaper. `analysis` is a publication's own reading of a story it does not
 * stand to gain from, which is the line the other four are on the wrong side of.
 */
export const KIND_WORTH_SAYING = visibleSourceKinds(taxonomy.source_kinds);

export function sourceKindCopy(
	kind: SourceKind,
	definitions: readonly SourceKindDefinition[] = taxonomy.source_kinds
): { label: string; showOnItem: boolean; registered: boolean } {
	const entry = definitions.find((definition) => definition.id === kind);
	return entry
		? { label: entry.display_name, showOnItem: entry.show_on_item, registered: true }
		: { label: `${kind} (unregistered source kind)`, showOnItem: true, registered: false };
}
