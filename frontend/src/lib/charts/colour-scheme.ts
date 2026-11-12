/** Which built-in D3 colours belong to a configured palette choice? */
import { schemeBlues, schemePiYG, schemeSpectral } from 'd3-scale-chromatic';
import type { ChartConfig } from '../server/config';

type BuiltinPalette = Exclude<ChartConfig['palette'], 'categorical'>;
const SCHEMES = {
	sequential: schemeBlues,
	spectral: schemeSpectral,
	piyg: schemePiYG
} satisfies Record<BuiltinPalette, readonly (readonly string[])[]>;

export function colourScheme(palette: BuiltinPalette, count?: number): readonly string[] {
	const scheme = SCHEMES[palette];
	if (scheme === undefined) throw new RangeError(`Unknown D3 palette ${palette}.`);
	const colours = scheme[count ?? scheme.length - 1];
	if (colours === undefined) throw new RangeError(`D3 ${palette} has no built-in scheme of size ${count}.`);
	return colours;
}
