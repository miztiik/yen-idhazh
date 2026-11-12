/** Which readable console tokens preserve the configured built-in colour family? */
import { rgb } from 'd3-color';
import { interpolateRgb, quantize } from 'd3-interpolate';
import { wcagContrast } from 'culori';
import { colourScheme } from '../src/lib/charts/colour-scheme.ts';
import { RESERVED_GREY } from '../src/lib/charts/d3/ordered-colour.ts';
import type { ChartConfig } from '../src/lib/server/config';
import type { ConsoleColors } from '../src/lib/console/console-style';

/** Six-digit CSS hex roles have eight bits per channel; this is sampling precision, not a style knob. */
const CHANNEL_VALUES = 2 ** 8;
/** These tokens also colour text; the design-system text floor is not palette strength. */
const TEXT_CONTRAST = 4.5;

export function consolePalette(
	colors: ConsoleColors,
	mode: 'light' | 'dark',
	palette: ChartConfig['palette']
): readonly string[] {
	if (palette === 'categorical') return colors.categorical;
	const backgrounds = [colors.canvas, colors.surface, colors.inset];
	const endpoints = mode === 'light' ? ['black', 'white'] : ['white', 'black'];
	const known = colourScheme(palette, colors.categorical.length - 1).map((colour) => {
		const candidates = endpoints.flatMap((end) => quantize(interpolateRgb(colour, end), CHANNEL_VALUES));
		const readable = candidates.find((candidate) =>
			backgrounds.every((background) => wcagContrast(candidate, background) >= TEXT_CONTRAST));
		if (readable === undefined) {
			throw new Error(`The ${mode} console surfaces cannot support readable ${palette} colours.`);
		}
		return rgb(readable).formatHex();
	});
	const result = [...known, colors.categorical[RESERVED_GREY - 1]];
	if (new Set(result).size !== result.length) {
		throw new Error(`The ${mode} console category and absence colours overlap.`);
	}
	return result;
}
