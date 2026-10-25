import { expect, test } from '@playwright/test';
import { elapsed, size, statusSentence } from '../src/lib/console/explorer/status';
import { refusedSentence } from '../src/lib/console/waiting';
import { numberFormat } from './support/number-format';

test('explorer status numbers use the shared declared format', () => {
	expect(size(1_234_567, numberFormat)).toBe('1.18 MB');
	expect(elapsed(1_234, numberFormat)).toBe('1.23 s');
	expect(statusSentence({ state: 'running-fetch', files: 1_234, bytes: 1_234_567 }, numberFormat))
		.toBe('Fetching 1,234 files, 1.18 MB.');
	expect(refusedSentence({ kind: 'over-ceiling', bytes: 1_234_567, files: 1_234, max: 2_345_678 }, numberFormat))
		.toBe('These days would fetch 1.18 MB from 1,234 files, and one question may fetch 2.24 MB. Pick fewer days or fewer ledgers.');
});
