import { expect, test } from '@playwright/test';

import { decodeQuestion, encodeQuestion, explorerAddress, parseExplorerAddress, requestTargetBytes } from '../src/lib/console/explorer/address';
import { LEDGER_NAMES, type LedgerName } from '../src/lib/data/slice-shapes';

const BASE_PATH = '/yen-idhazh/console/data-explorer/';
const REQUEST_TARGET_LIMIT = 8192; // docs/reference/benchmarks/address-length-on-pages.md
const QUERY_MAX_CHARS = 5782;
const FIXED_ADDRESS_BYTES_WITH_RESERVED_END = 476;
const WORST_CASE_Q_CHARS = Math.ceil((4 * (QUERY_MAX_CHARS + 5)) / 3);
const WINDOW_PRESETS = [1, 7, 14, 30, 90] as const;

function printableAscii(seed: number, length: number): string {
	let state = seed >>> 0;
	let out = '';
	for (let index = 0; index < length; index += 1) {
		state = (1664525 * state + 1013904223) >>> 0;
		out += String.fromCharCode(32 + (state % 95));
	}
	return out;
}

test('statements round-trip through deflate-raw and base64url', async () => {
	const statements = [
		'select count(*) from seen',
		"select source, count(*) from item_health where day >= '2026-10-01' group by source",
		printableAscii(0x55aa, QUERY_MAX_CHARS)
	];
	for (const statement of statements) {
		await expect(decodeQuestion(await encodeQuestion(statement))).resolves.toBe(statement);
	}
});

test('the computed ASCII statement length fits the measured GitHub Pages request target', async () => {
	const statement = printableAscii(0x1234abcd, QUERY_MAX_CHARS);
	const encodedQuestion = await encodeQuestion(statement);
	expect(WORST_CASE_Q_CHARS).toBe(7716);
	expect(FIXED_ADDRESS_BYTES_WITH_RESERVED_END + WORST_CASE_Q_CHARS).toBe(REQUEST_TARGET_LIMIT);
	expect(encodedQuestion.length).toBeLessThanOrEqual(WORST_CASE_Q_CHARS);
	const address = await explorerAddress({ basePath: BASE_PATH, ledgers: LEDGER_NAMES, days: 90, statement, maxBytes: REQUEST_TARGET_LIMIT });
	const withReservedEnd = address.href.replace('&q=', '&end=YYYY-MM-DD&q=');
	expect(address.linkedStatement).toBe(true);
	expect(address.query).toContain(`q=${encodedQuestion}`);
	expect(requestTargetBytes(withReservedEnd)).toBeLessThanOrEqual(REQUEST_TARGET_LIMIT);
	const parsed = await parseExplorerAddress(address.query, { ledgerNames: LEDGER_NAMES, windowPresets: WINDOW_PRESETS, defaultDays: 14 });
	expect(parsed.statement).toBe(statement);
	expect(parsed.ledgers).toEqual(LEDGER_NAMES);
	expect(parsed.days).toBe(90);
});

test('a link too long for the byte bound carries ledgers and days only', async () => {
	const address = await explorerAddress({ basePath: BASE_PATH, ledgers: ['seen'], days: 14, statement: printableAscii(1, 200), maxBytes: 80 });
	expect(address.linkedStatement).toBe(false);
	expect(address.query).toBe('ledgers=seen&days=14');
	expect(address.notices).toEqual(['This question is too long for a link, so the link carries the ledgers and the days only.']);
});

test('unknown ledgers, unsupported days and unreadable q return their sentences', async () => {
	const parsed = await parseExplorerAddress('ledgers=seen,unknown-ledger,gardener&days=365&q=not-valid-***', {
		ledgerNames: LEDGER_NAMES,
		windowPresets: WINDOW_PRESETS,
		defaultDays: 14
	});
	expect(parsed.ledgers).toEqual(['seen', 'gardener'] satisfies LedgerName[]);
	expect(parsed.days).toBe(14);
	expect(parsed.statement).toBe('');
	expect(parsed.notices).toEqual([
		'The link named "unknown-ledger", which this site does not have, so it was left out.',
		'The link asked for 365 days, which this page does not offer, so it reads 14 days.',
		'The question in this link could not be read, so the editor is empty.'
	]);
});
