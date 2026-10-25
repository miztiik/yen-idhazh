/** Number formatting shared by the digest drawing and the console. */

export interface NumberFormatConfig {
	locale: string;
	si_prefix_from: number;
	significant_digits: number;
}

export interface NumberFormatOptions {
	/** Use an SI prefix where the configured threshold is reached. */
	si?: boolean;
	/** Keep every integer digit for exact counts or currency integer parts. */
	exact?: boolean;
}

export type NumberFormatter = (value: number, options?: NumberFormatOptions) => string;

const SI_PREFIXES: Readonly<Record<number, string>> = {
	[-30]: 'q',
	[-27]: 'r',
	[-24]: 'y',
	[-21]: 'z',
	[-18]: 'a',
	[-15]: 'f',
	[-12]: 'p',
	[-9]: 'n',
	[-6]: 'u',
	[-3]: 'm',
	0: '',
	3: 'k',
	6: 'M',
	9: 'G',
	12: 'T',
	15: 'P',
	18: 'E',
	21: 'Z',
	24: 'Y',
	27: 'R',
	30: 'Q'
};

const FORMATTERS = new Map<string, NumberFormatter>();

/** Create one formatter for a page using the single declared number style. */
export function numberFormatter(config: NumberFormatConfig): NumberFormatter {
	const key = `${config.locale}\0${config.si_prefix_from}\0${config.significant_digits}`;
	const cached = FORMATTERS.get(key);
	if (cached !== undefined) return cached;

	const measured = new Intl.NumberFormat(config.locale, {
		maximumSignificantDigits: config.significant_digits
	});
	const exact = new Intl.NumberFormat(config.locale, { maximumFractionDigits: 0 });

	const format: NumberFormatter = (value, options = {}) => {
		if (!Number.isFinite(value)) throw new RangeError('A displayed number must be finite.');
		if (options.exact) return exact.format(value);

		const usePrefix = options.si !== false;
		const rounded = Number(value.toPrecision(config.significant_digits));
		let exponent =
			usePrefix && Math.abs(rounded) >= config.si_prefix_from
				? Math.min(30, Math.floor(Math.log10(Math.abs(rounded)) / 3) * 3)
				: 0;
		let scaled = value / 10 ** exponent;
		while (
			usePrefix &&
			exponent > 0 &&
			exponent < 30 &&
			Math.abs(Number(scaled.toPrecision(config.significant_digits))) >= 1000
		) {
			exponent += 3;
			scaled = value / 10 ** exponent;
		}
		return `${measured.format(scaled)}${SI_PREFIXES[exponent] ?? ''}`;
	};
	FORMATTERS.set(key, format);
	return format;
}

export function formatNumber(
	value: number,
	config: NumberFormatConfig,
	options?: NumberFormatOptions
): string {
	return numberFormatter(config)(value, options);
}
