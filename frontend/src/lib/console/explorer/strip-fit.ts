/** How many question chips fit on one line, beside their run labels and the fold that holds the rest. */

/** Measured widths, in CSS px, of everything the question strip can draw on its line.
 * `chips` lists the saved chips first, then the examples, in the order the strip draws them. */
export interface StripWidths {
	savedLabel: number;
	examplesLabel: number;
	more: number;
	gap: number;
	chips: readonly number[];
}

/** The most chips, at most `limit`, that fit in `available` px together with the label of
 * each run they belong to and, when any chip is left over, the `{n} more` fold. Saved chips
 * come first, so an example folds before a saved question does. */
export function chipsThatFit(widths: StripWidths, available: number, savedCount: number, limit: number): number {
	for (let count = Math.min(widths.chips.length, limit); count > 0; count -= 1) {
		const savedShown = Math.min(count, savedCount);
		const parts = [
			...(savedShown > 0 ? [widths.savedLabel, ...widths.chips.slice(0, savedShown)] : []),
			...(count > savedShown ? [widths.examplesLabel, ...widths.chips.slice(savedCount, savedCount + count - savedShown)] : []),
			...(count < widths.chips.length ? [widths.more] : [])
		];
		const needed = parts.reduce((sum, part) => sum + part, 0) + widths.gap * (parts.length - 1);
		if (needed <= available) return count;
	}
	return 0;
}
