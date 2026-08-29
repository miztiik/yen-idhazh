/** The bridge between `tokens.css` and a chart engine that only speaks hex.
 *
 * The engine renders SVG on the server at build time, which is what keeps the
 * console complete before any script runs. But a hex baked into that SVG cannot
 * follow a theme change, and reading the real token values on the server is not
 * possible - there is no document to compute styles against.
 *
 * So the server draws with SENTINEL colours and the sentinels are swapped for
 * custom-property references in the emitted SVG. The result is a prerendered
 * chart whose geometry came from the server and whose colour comes from CSS:
 * both themes work, the theme toggle is instant, and `tokens.css` stays the
 * only place a colour is decided. No JavaScript is involved in any of it.
 *
 * A sentinel is never seen by anybody. If one reaches a browser it is a bug,
 * and `charts.spec.ts` asserts none does.
 */

/** Every token a chart may draw with, in the order a categorical series takes
 * them. A token that is not here cannot be used by a chart, which is the point:
 * it makes the palette a closed set rather than whatever someone typed. */
const PALETTE = [
	'--chart-1',
	'--chart-2',
	'--chart-3',
	'--chart-4',
	'--chart-5',
	'--chart-6',
	'--chart-7',
	'--chart-8'
] as const;

const STRUCTURE = [
	'--chart-grid',
	'--chart-axis',
	'--chart-marker',
	'--color-text',
	'--color-text-secondary',
	'--color-text-tertiary',
	'--color-surface',
	'--color-accent',
	'--band-high',
	'--band-medium',
	'--band-low'
] as const;

export type ChartToken = (typeof PALETTE)[number] | (typeof STRUCTURE)[number];

const TOKENS: readonly ChartToken[] = [...PALETTE, ...STRUCTURE];

/** `#ff00NN`. A reserved-looking magenta ramp no palette would choose, so a
 * sentinel that escapes the swap is loud rather than plausible. */
function sentinelFor(index: number): string {
	return `#ff00${index.toString(16).padStart(2, '0')}`;
}

const SENTINEL_OF = new Map<ChartToken, string>(
	TOKENS.map((token, i) => [token, sentinelFor(i)])
);

/** The colour to put in a chart option. Never a real hex - always a sentinel
 * that `toCssVariables` will turn back into the token. */
export function paint(token: ChartToken): string {
	const sentinel = SENTINEL_OF.get(token);
	if (!sentinel) throw new Error(`${token} is not a chart token`);
	return sentinel;
}

/** The categorical ramp, in order, for a series that needs N distinct colours. */
export function series(count: number): string[] {
	return Array.from({ length: count }, (_, i) => paint(PALETTE[i % PALETTE.length]));
}

/** Swap every sentinel in a rendered SVG for the custom property it stands for.
 *
 * Case-insensitive because the engine does not promise the case it writes a hex
 * in, and a swap that missed on case would ship a magenta chart.
 */
export function toCssVariables(svg: string): string {
	let out = svg;
	for (const [token, sentinel] of SENTINEL_OF) {
		out = out.replace(new RegExp(sentinel, 'gi'), `var(${token})`);
	}
	return out;
}

/** Read the real values out of the document. Only the client can do this, and
 * it only needs to for the parts of a live chart that are not SVG attributes -
 * a tooltip's own background, for instance. */
export function readTokens(root: Element = document.documentElement): Record<ChartToken, string> {
	const style = getComputedStyle(root);
	const out = {} as Record<ChartToken, string>;
	for (const token of TOKENS) out[token] = style.getPropertyValue(token).trim();
	return out;
}

/** Turn every sentinel in a chart option into the colour the document computes
 * for its token.
 *
 * The server does not need this - it swaps sentinels for custom-property
 * references in the finished SVG, and CSS resolves them. A live chart does: it
 * paints into a canvas-shaped API that never sees a stylesheet, so a sentinel
 * handed straight to the engine is drawn as the magenta it literally is.
 * Measured 2026-08-29 in the browser, that is exactly what happened before this
 * existed.
 *
 * Functions are passed through untouched, so a label or tooltip formatter
 * survives the walk.
 */
export function resolveSentinels<T>(option: T, root?: Element): T {
	const values = readTokens(root);
	const bySentinel = new Map(
		TOKENS.map((token) => [SENTINEL_OF.get(token) as string, values[token]])
	);
	const walk = (node: unknown): unknown => {
		if (typeof node === 'string') return bySentinel.get(node.toLowerCase()) ?? node;
		if (Array.isArray(node)) return node.map(walk);
		if (node !== null && typeof node === 'object') {
			return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, walk(value)]));
		}
		return node;
	};
	return walk(option) as T;
}

/** Exported for the test that proves no sentinel survives into a built page. */
export const SENTINEL_PATTERN = /#ff00[0-9a-f]{2}/i;
