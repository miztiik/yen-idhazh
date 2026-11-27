/** Name the reader comparison fills shared by the CSS build and the drawing. */
export const COMPARISON_COLORS = {
	measure: '--story-chart-measure',
	above_zero: '--story-chart-above-zero',
	below_zero: '--story-chart-below-zero'
} as const;

type FillRole = keyof typeof COMPARISON_COLORS;
export type ComparisonColorToken = (typeof COMPARISON_COLORS)[FillRole];
export type StoryComparisonColors = Record<'light' | 'dark', Record<FillRole, string>>;
