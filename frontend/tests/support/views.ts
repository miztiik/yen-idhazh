/** Which width and theme pairs a layout check opens a page at.
 *
 * Width moves layout and theme moves colour, and neither decides what the other
 * does. So a check opens every width in the first theme, and each other theme
 * once, at the narrowest width - where a page has the least room and is judged
 * most strictly. Every width and every theme is still seen; only the pairs that
 * repeat a finding are dropped. Three widths in two themes is four page loads
 * rather than six.
 */
export interface View<W extends number, T extends string> {
	width: W;
	theme: T;
}

export function viewsOf<W extends number, T extends string>(
	widths: readonly W[],
	themes: readonly T[]
): View<W, T>[] {
	if (widths.length === 0 || themes.length === 0) {
		throw new Error('a view needs at least one width and one theme');
	}
	const narrowest = widths.reduce((least, width) => (width < least ? width : least));
	return [
		...widths.map((width) => ({ width, theme: themes[0]! })),
		...themes.slice(1).map((theme) => ({ width: narrowest, theme }))
	];
}
