/** How a console chart moves, and the one switch that stops it moving.
 *
 * One duration and one easing, both read from the tokens `build-frame-css.mjs`
 * writes out of `config/appearance.json`, so a number here could only ever
 * disagree with them. A chart animates what the compositor or the painter can
 * change without moving anything else - opacity, transform, colour - and never
 * a width or a position, because a transition on layout slides the page under
 * the reader's cursor.
 *
 * **Reduced motion is a hard stop, written once.** Where the reader asked for
 * it, there is no transition at all rather than a shorter one: a shorter
 * animation is still an animation.
 */

/** The media query a reader's system sets when they asked for less motion. */
export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/** What a chart may animate. Layout properties are absent on purpose. */
const MAY_ANIMATE: ReadonlySet<string> = new Set([
	'opacity',
	'transform',
	'color',
	'background-color',
	'fill',
	'fill-opacity',
	'stroke',
	'stroke-opacity'
]);

/** A CSS `transition` value for these properties, or `none`.
 *
 * Refuses a property that moves layout by name, so the mistake is found where
 * it is written rather than on a page that jumps.
 */
export function transition(properties: readonly string[], reduced: boolean): string {
	for (const property of properties) {
		if (!MAY_ANIMATE.has(property)) {
			throw new Error(
				`A console chart does not animate "${property}": only ${[...MAY_ANIMATE].join(', ')} may move.`
			);
		}
	}
	if (reduced || properties.length === 0) return 'none';
	return properties
		.map((property) => `${property} var(--dur-base) var(--ease-standard)`)
		.join(', ');
}

/** Something that answers a media query, the way `window.matchMedia` does. */
export type MediaMatcher = (query: string) => { matches: boolean };

function browserMatcher(): MediaMatcher | undefined {
	return typeof globalThis.matchMedia === 'function'
		? (query: string) => globalThis.matchMedia(query)
		: undefined;
}

/** Whether to draw without motion.
 *
 * True where there is no window to ask. A page drawn on the server never
 * animates, so drawing it still is drawing it as it is.
 */
export function prefersReducedMotion(match: MediaMatcher | undefined = browserMatcher()): boolean {
	return match === undefined ? true : match(REDUCED_MOTION_QUERY).matches;
}
