/** What words must a windowed surface say about its own span at a preset?
 *
 * Reader's words, written out here rather than read from `span-words.ts`, so a
 * page check cannot agree with the helper by construction. At one day a surface
 * says "this one day" for the days on screen or "1 day" for a bare count, and at
 * one day a few sentences say it in a sentence of their own, such as "One day is
 * too short for a line". At more it says "7 days". No surface ever says "1 days".
 */

/** The span words a surface owes at `preset`. */
export function spanSaid(preset: number): RegExp {
	return preset === 1 ? /\b(?:one day|1 day)\b/i : new RegExp(`\\b${preset} days\\b`);
}

/** The words no surface may print at any preset. */
export const ONE_DAYS = /\b1 days\b/;
