import { expect, test } from '@playwright/test';

import { numberFormatter } from '../src/lib/number-format';
import { grouped } from '../src/lib/charts/series';
import { numberFormat } from './support/number-format';

test('the formatter uses its declared locale, not the machine locale', () => {
	const format = numberFormatter({ ...numberFormat, locale: 'de-DE' });

	expect(format(1_234_567)).toBe('1,23M');
});

test('the configured significant digits control rounding across prefixes', () => {
	const format = numberFormatter({ ...numberFormat, significant_digits: 2 });

	expect(format(1_234_567)).toBe('1.2M');
	expect(format(999_500)).toBe('1M');
});

test('the configured threshold decides when a prefix appears', () => {
	const format = numberFormatter({ ...numberFormat, si_prefix_from: 10_000 });

	expect(format(9_990)).toBe('9,990');
	expect(format(9_999)).toBe('10k');
	expect(format(10_000)).toBe('10k');
});

test('exact formatting remains available for a currency amount handled in parts', () => {
	expect(numberFormatter(numberFormat)(1_234_567, { exact: true, si: false })).toBe('1,234,567');
});

test('counts keep every digit while using the declared grouping locale', () => {
	expect(grouped(12_345, numberFormat)).toBe('12,345');
	expect(grouped(1_234_567, { ...numberFormat, locale: 'de-DE' })).toBe('1.234.567');
});

test('non-finite display values fail explicitly', () => {
	const format = numberFormatter(numberFormat);

	expect(() => format(Number.NaN)).toThrow(/finite/);
	expect(() => format(Number.POSITIVE_INFINITY)).toThrow(/finite/);
});
