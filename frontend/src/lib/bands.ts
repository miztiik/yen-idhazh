/** Copy lives here, once. A component never spells a band or a source kind. */

import type { BandReason, ConfidenceBand, SourceKind } from './payload/types';

export interface BandCopy {
	label: string;
	token: string;
	/** `high` shows nothing on an item: ink spent on the absence of a problem. */
	showOnItem: boolean;
}

export const BANDS: Record<ConfidenceBand, BandCopy> = {
	high: { label: 'Matches the source', token: 'var(--band-high)', showOnItem: false },
	medium: { label: 'Mostly matches the source', token: 'var(--band-medium)', showOnItem: true },
	low: { label: 'May not match the source', token: 'var(--band-low)', showOnItem: true }
};

/** What is actually missing, in the voice of the truncation note.
 *
 * A band on its own is a grade. It tells a reader an item is worse without
 * telling them what to look for when they click through, which is the only
 * thing they can do about it. Each sentence names one concrete absence.
 */
export const BAND_REASONS: Record<BandReason, string> = {
	unsupported_number: 'Our summary gives a figure the article does not.',
	not_scored: 'We could not check this summary against the article.',
	lead_missing: 'Our summary leaves out names or figures from the opening.',
	hedge_dropped: 'The article is more careful about this than our summary is.',
	faithfulness: 'Parts of our summary do not line up with the article.'
};

/** The sentence for an item, or the band label when nothing explains it.
 *
 * A day published before the reason existed carries none, and falls back to the
 * label it already showed.
 */
export function bandSentence(band: ConfidenceBand, reason: BandReason | null): string {
	return reason ? BAND_REASONS[reason] : BANDS[band].label;
}

export const BAND_ORDER: ConfidenceBand[] = ['high', 'medium', 'low'];

/** Who is speaking. A vendor's own copy must not read like a reporter's. */
export const SOURCE_KINDS: Record<SourceKind, string> = {
	reporting: 'Reporting',
	announcement: 'Announcement',
	research: 'Research',
	analysis: 'Analysis',
	government: 'Official',
	community: 'Community'
};

/** Only kinds where the speaker has a stake worth naming get a label on the item. */
export const KIND_WORTH_SAYING: SourceKind[] = ['announcement', 'community'];
