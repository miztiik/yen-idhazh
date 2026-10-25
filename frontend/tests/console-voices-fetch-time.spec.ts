import { expect, test } from '@playwright/test';
import { fetchTime } from '../src/lib/console/voices/fetch-time';
import { numberFormat } from './support/number-format';

test('fetch-time labels and accessible readings share the declared precision', () => {
	const reading = fetchTime([{
		source_id: 'alpha',
		fetch_ms: 10_500,
		robots_ms: 1_000,
		retry_total_ms: 500,
		fetch_connect_ms: 1_000,
		fetch_ttfb_ms: 2_000,
		retry_count: 2
	}], 3, numberFormat);

	expect(reading.geometry?.rows[0].row.value).toBe('10.5 s');
	expect(reading.lede).toBe('alpha is slowest, averaging 10.5 seconds a fetch.');
	expect(reading.records[0].facts[0].value).toBe('10,500 ms over 1 fetches');
	expect(reading.records[0].facts[1].value).toBe('1,000 ms');
});
