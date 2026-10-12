/** Independent reader-word oracles, not the formatter under test. */
export function spanSaid(preset: number): RegExp {
	return preset === 1 ? /\b(?:one day|1 day)\b/i : new RegExp(`\\b${preset} days\\b`);
}
export const ONE_DAYS = /\b1 days\b/;
