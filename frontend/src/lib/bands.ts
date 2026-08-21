/** Copy lives here, once. A component never spells a band or a source kind. */

import type { ConfidenceBand, SourceKind } from './payload/types';

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
