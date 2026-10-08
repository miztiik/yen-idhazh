import { expect, test } from '@playwright/test';

import { decodeQuestion, encodeQuestion, explorerAddress, parseExplorerAddress, requestTargetBytes } from '../src/lib/console/explorer/address';
import { LEDGER_NAMES, type LedgerName } from '../src/lib/data/slice-shapes';
import { explorerConfig } from '../src/lib/server/config';

const BASE_PATH = '/yen-idhazh/console/data-explorer/';
const REQUEST_TARGET_LIMIT = 8192; // docs/reference/benchmarks/address-length-on-pages.md
const QUERY_MAX_CHARS = explorerConfig().query_max_chars;
const WINDOW_PRESETS = [1, 7, 14, 30, 90] as const;
const TODAY = '2026-10-04';
const CUSTOM_FROM = '2026-04-05';
const CUSTOM_END = '2026-04-12';
const PARSE_OPTIONS = { ledgerNames: LEDGER_NAMES, windowPresets: WINDOW_PRESETS, defaultDays: 14, today: TODAY, reachDays: 365 };

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

test('a statement at the configured maximum fits a shared link with every ledger', async () => {
	const statement = printableAscii(0x1234abcd, QUERY_MAX_CHARS);
	const encodedQuestion = await encodeQuestion(statement);
	const address = await explorerAddress({ basePath: BASE_PATH, ledgers: LEDGER_NAMES, days: 90, from: CUSTOM_FROM, end: CUSTOM_END, statement, maxBytes: REQUEST_TARGET_LIMIT });
	expect(address.linkedStatement).toBe(true);
	expect(address.query).toContain(`q=${encodedQuestion}`);
	expect(requestTargetBytes(address.href)).toBeLessThanOrEqual(REQUEST_TARGET_LIMIT);
	const parsed = await parseExplorerAddress(address.query, PARSE_OPTIONS);
	expect(parsed.statement).toBe(statement);
	expect(parsed.ledgers).toEqual(LEDGER_NAMES);
	expect(parsed.from).toBe(CUSTOM_FROM);
	expect(parsed.end).toBe(CUSTOM_END);
	expect(parsed.days).toBe(8);

	const oneMoreCharacter = printableAscii(0x1234abcd, QUERY_MAX_CHARS + 1);
	const tooLong = await explorerAddress({
		basePath: BASE_PATH,
		ledgers: LEDGER_NAMES,
		days: 90,
		from: CUSTOM_FROM,
		end: CUSTOM_END,
		statement: oneMoreCharacter,
		maxBytes: REQUEST_TARGET_LIMIT
	});
	expect(tooLong.linkedStatement).toBe(false);
	expect(tooLong.query).not.toContain('q=');
});

test('a link too long for the byte bound carries ledgers and days only', async () => {
	const address = await explorerAddress({ basePath: BASE_PATH, ledgers: ['seen'], days: 14, statement: printableAscii(1, 200), maxBytes: 80 });
	expect(address.linkedStatement).toBe(false);
	expect(address.query).toBe('ledgers=seen&days=14');
	expect(address.notices).toEqual(['This question is too long for a link, so the link carries the ledgers and the days only.']);
});

test('unknown ledgers, unsupported days and unreadable q return their sentences', async () => {
	const parsed = await parseExplorerAddress('ledgers=seen,unknown-ledger,gardener&days=365&q=not-valid-***', PARSE_OPTIONS);
	expect(parsed.ledgers).toEqual(['seen', 'gardener'] satisfies LedgerName[]);
	expect(parsed.days).toBe(14);
	expect(parsed.statement).toBe('');
	expect(parsed.notices).toEqual([
		'The link named "unknown-ledger", which this site does not have, so it was left out.',
		'The link asked for 365 days, which this page does not offer, so it reads 14 days.',
		'The question in this link could not be read, so the editor is empty.'
	]);
});

test('a span of one day is one day in the notice, never 1 days', async () => {
	const oneDay = await parseExplorerAddress('days=365', { ...PARSE_OPTIONS, defaultDays: 1 });
	expect(oneDay.notices).toEqual(['The link asked for 365 days, which this page does not offer, so it reads 1 day.']);
	const askedForOne = await parseExplorerAddress('days=1', { ...PARSE_OPTIONS, windowPresets: [7, 14] });
	expect(askedForOne.notices).toEqual(['The link asked for 1 day, which this page does not offer, so it reads 14 days.']);
	const notADay = await parseExplorerAddress('days=soon', PARSE_OPTIONS);
	expect(notADay.notices).toEqual(['The link asked for soon days, which this page does not offer, so it reads 14 days.']);
});

test('custom dates replace days, and invalid custom dates are dropped with a sentence', async () => {
	const address = await explorerAddress({ basePath: BASE_PATH, ledgers: ['seen'], days: 14, from: CUSTOM_FROM, end: CUSTOM_END, statement: 'select 1' });
	expect(address.query).toContain(`from=${CUSTOM_FROM}`);
	expect(address.query).toContain(`end=${CUSTOM_END}`);
	expect(address.query).not.toContain('days=');
	const parsed = await parseExplorerAddress(address.query, PARSE_OPTIONS);
	expect(parsed).toMatchObject({ ledgers: ['seen'], days: 8, from: CUSTOM_FROM, end: CUSTOM_END, statement: 'select 1', notices: [] });

	const invalid = await parseExplorerAddress('from=2025-01-01&end=2026-10-05', PARSE_OPTIONS);
	expect(invalid.from).toBeNull();
	expect(invalid.end).toBeNull();
	expect(invalid.days).toBe(14);
	expect(invalid.notices).toEqual(['The link asked for 2025-01-01 to 2026-10-05, which is not a span this page can read, so it ends today.']);
});

test('a date shaped like a day that is not one is dropped with the same sentence, never thrown', async () => {
	// 2026-08-32 has the shape of a day and no time at all, so a check that prints it
	// before it asks whether it is a day throws instead of answering.
	const parsed = await parseExplorerAddress('ledgers=seen&from=2026-08-32&end=2026-09-02', PARSE_OPTIONS);
	expect(parsed).toMatchObject({ ledgers: ['seen'], days: 14, from: null, end: null });
	expect(parsed.notices).toEqual(['The link asked for 2026-08-32 to 2026-09-02, which is not a span this page can read, so it ends today.']);
});
