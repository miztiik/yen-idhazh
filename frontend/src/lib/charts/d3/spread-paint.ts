/** What paint a spread band is drawn in, and the readout swatch that keys it.
 *
 * One function, so the band behind a line and the swatch that names its edges in
 * the strip and the tooltip are one colour and cannot drift apart: the series'
 * token, mixed toward the page surface at `--chart-spread-mix`. It leaves as a
 * custom-property reference, so both themes resolve it and `tokens.css` stays
 * the one place a colour is decided.
 */
import type { ChartToken } from '../theme';

export function spreadPaint(token: ChartToken): string {
	return `color-mix(in srgb, var(${token}) calc(var(--chart-spread-mix) * 100%), var(--color-surface))`;
}
