/** Give each judge outcome one label and app color throughout the trial. */
import type { ChartToken } from '$lib/charts/theme';

export const DRAW_PARTS = ['yes', 'no', 'unclear', 'split', 'refused', 'missing'] as const;
export const OUTCOME_STYLE = {
	yes: { label: 'Agreed YES', token: '--chart-2' },
	no: { label: 'Agreed NO', token: '--chart-1' },
	maybe: { label: 'MAYBE', token: '--chart-3' },
	unclear: { label: 'Agreed UNCLEAR', token: '--chart-6' },
	split: { label: 'Split on reversal', token: '--chart-3' },
	refused: { label: 'Refused', token: '--chart-4' },
	missing: { label: 'No return', token: '--chart-8' },
	unclassified: { label: 'Other returns (not classified)', token: '--chart-4' }
} as const satisfies Record<string, { label: string; token: ChartToken }>;
