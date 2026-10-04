import { expect, test } from '@playwright/test';

import { decodeQuestion, encodeQuestion, explorerAddress, parseExplorerAddress, requestTargetBytes } from '../src/lib/console/explorer/address';
import { LEDGER_NAMES, type LedgerName } from '../src/lib/data/slice-shapes';
import { explorerConfig } from '../src/lib/server/config';

const BASE_PATH = '/yen-idhazh/console/data-explorer/';
const REQUEST_TARGET_LIMIT = 8192; // docs/reference/benchmarks/address-length-on-pages.md
const QUERY_MAX_CHARS = explorerConfig().query_max_chars;
/** The most base64url characters `q` takes for an `n`-character statement that does not
 *  compress: deflate-raw stores it in one block with a 5-byte header. */
const worstCaseQuestionChars = (chars: number): number => Math.ceil((4 * (chars + 5)) / 3);
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

test('the computed ASCII statement length fits the measured GitHub Pages request target', async () => {
	// The worst case is measured, not assumed: the link's fixed part comes from the real encoder
	// with every ledger name and a custom span carrying `from` and `end`, so a ledger added to the
	// registry grows it and turns this red until the length comes down.
	const fixedPart = await explorerAddress({
		basePath: BASE_PATH,
		ledgers: LEDGER_NAMES,
		days: Math.max(...WINDOW_PRESETS),
		from: CUSTOM_FROM,
		end: CUSTOM_END,
		statement: 'x',
		maxBytes: 1
	});
	expect(fixedPart.linkedStatement).toBe(false);
	const fixedBytes = requestTargetBytes(`${fixedPart.href}&q=`);
	expect(fixedBytes + worstCaseQuestionChars(QUERY_MAX_CHARS)).toBeLessThanOrEqual(REQUEST_TARGET_LIMIT);
	expect(fixedBytes + worstCaseQuestionChars(QUERY_MAX_CHARS + 1), 'a longer statement would also fit').toBeGreaterThan(REQUEST_TARGET_LIMIT);

	const statement = printableAscii(0x1234abcd, QUERY_MAX_CHARS);
	const encodedQuestion = await encodeQuestion(statement);
	expect(encodedQuestion.length).toBeLessThanOrEqual(worstCaseQuestionChars(QUERY_MAX_CHARS));
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
