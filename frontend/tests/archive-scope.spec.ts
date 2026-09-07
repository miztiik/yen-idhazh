import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ENCODER_DIMENSIONS } from '../src/lib/assist/encoder';
import { indexOf, monthsInWindow, type MonthIndex, windowStart } from '../src/lib/assist/month';
import { decodeVectorAt, rank, readScope, searchedDays } from '../src/lib/assist/search';
import { plural } from '../src/lib/format';

/**
 * How far back does a search actually reach?
 *
 * The scope used to be "the newest month shard", which is a calendar boundary
 * rather than a window. On the last day of a month that reads 31 days; on the
 * first day of the next one it reads a single day, and the reader who gets
 * nothing back cannot tell that from "we never published it". This file holds
 * the rule that ends the collapse.
 *
 * Pure, and driven in Node rather than in a page, because the canary build
 * publishes one month and a rule about two months cannot show up in it -
 * the same reason `frontend/src/lib/day-shape.ts` is unit-tested here
 * (`docs/how-to/run-the-gates.md`).
 *
 * The corpus is the committed `2026-08` shard, re-dated rather than invented:
 * its newest day becomes a one-day September shard and everything before it
 * stays as August. Real entries, real vectors, real byte offsets - and the
 * query is one item's own vector, so retrieval is checked without an encoder.
 */

const INDEX = resolve(process.cwd(), 'public', 'assist', 'index');

/** The committed month, header and entries, exactly as a browser would read it. */
function committed(): { index: MonthIndex; vectors: Int8Array } {
	const payload = JSON.parse(readFileSync(resolve(INDEX, '2026-08.json'), 'utf8'));
	const index = indexOf(payload);
	if (index === null) throw new Error('the committed 2026-08 shard did not parse');
	const bytes = readFileSync(resolve(INDEX, '2026-08.bin'));
	return { index, vectors: new Int8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength) };
}

/** Two shards whose newest holds exactly one day. The shape 1 September has. */
function twoMonths(): { newest: MonthIndex; previous: MonthIndex; vectors: Int8Array } {
	const { index, vectors } = committed();
	const dates = [...new Set(index.entries.map((entry) => entry.date))].sort().reverse();
	expect(dates.length, 'the committed shard holds one day, so it cannot be split').toBeGreaterThan(
		1
	);

	const last = dates[0]!;
	const newest: MonthIndex = {
		...index,
		month: '2026-09',
		entries: index.entries
			.filter((entry) => entry.date === last)
			.map((entry) => ({ ...entry, date: '2026-09-01' }))
	};
	const previous: MonthIndex = {
		...index,
		month: '2026-08',
		entries: index.entries.filter((entry) => entry.date !== last)
	};
	return { newest, previous, vectors };
}

test('a search reaches past the newest month when that month holds one day', async () => {
	const { newest, previous, vectors } = twoMonths();
	const shards = new Map([
		['2026-09', newest],
		['2026-08', previous]
	]);
	const load = async (month: string): Promise<MonthIndex | null> => shards.get(month) ?? null;

	// One story from the previous month, and its own vector as the question. It
	// scores 1.0 against itself, so a miss can only be a scope that never read it.
	const target = previous.entries.find((entry) => entry.vector !== null && entry.vector !== undefined);
	expect(target, 'no entry in the previous month carries a vector').toBeDefined();
	const query = decodeVectorAt(vectors, target!.vector!, ENCODER_DIMENSIONS, previous.scale);
	expect(query, 'the target vector did not decode').not.toBeNull();

	const read = await readScope(['2026-09', '2026-08'], { months: 1, minDays: 7 }, load);
	const days = searchedDays(read);

	const hits = rank(
		read.map((index) => ({ index, vectors })),
		query!,
		{ limit: 10, minScore: 0.35 }
	);
	const found = hits.map((hit) => hit.entry.item_id);

	expect(
		found,
		`the search read ${read.map((index) => index.month).join(', ')} covering ` +
			`${plural(days.length, 'day', 'days')}, so ${target!.item_id} from 2026-08 was out of reach`
	).toContain(target!.item_id);
});

test('the scope stops at one extra shard, so a search costs at most one more fetch', async () => {
	const { newest, previous } = twoMonths();
	const asked: string[] = [];
	const shards = new Map([
		['2026-09', newest],
		['2026-08', previous],
		['2026-07', previous],
		['2026-06', previous]
	]);
	const load = async (month: string): Promise<MonthIndex | null> => {
		asked.push(month);
		return shards.get(month) ?? null;
	};

	const read = await readScope(
		['2026-09', '2026-08', '2026-07', '2026-06'],
		{ months: 1, minDays: 7 },
		load
	);

	expect(asked, 'a thin newest month may cost one extra fetch and no more').toEqual([
		'2026-09',
		'2026-08'
	]);
	expect(read.map((index) => index.month)).toEqual(['2026-09', '2026-08']);
});

test('a month that already covers the floor is read on its own', async () => {
	const { index, vectors } = committed();
	const asked: string[] = [];
	const load = async (month: string): Promise<MonthIndex | null> => {
		asked.push(month);
		return month === '2026-08' ? index : null;
	};

	// The committed shard's own day count is the floor this has to clear.
	const days = searchedDays([index]).length;
	const read = await readScope(['2026-08', '2026-07'], { months: 1, minDays: days }, load);

	expect(asked, 'a month that covers the floor must not fetch a second one').toEqual(['2026-08']);
	expect(read.map((shard) => shard.month)).toEqual(['2026-08']);
	expect(vectors.length).toBeGreaterThan(0);
});

/**
 * How far back does the browse LIST reach - a separate question from the search
 * above, and the one Finding 89 is about.
 *
 * The list opens on a window of days, not on the whole archive, and fetches
 * only the month files that window can hold a story from. `monthsInWindow` is
 * that rule, and it is pure for the same reason `readScope` is: the canary
 * publishes one index month, so a rule about several months cannot show up in a
 * page built on it. Here the months are given directly - the shape
 * `indexMonths()` returns, newest first - because the rule is date arithmetic
 * on month strings and needs no shard to exercise.
 */

test('the browse window fetches only the months it can hold a story from, newest first', () => {
	// Four months on disk, newest first, the way `indexMonths()` hands them over.
	const months = ['2026-09', '2026-08', '2026-07', '2026-06'];

	// A seven-day window on the third of a month reaches back over the boundary
	// into the previous month, and no further - two files fetched, not four. This
	// is the bound: yesterday's loop walked to '2026-06' to fill a page.
	expect(monthsInWindow(months, '2026-09-03', 7)).toEqual(['2026-09', '2026-08']);

	// A one-day window is the anchor day alone, so it is the anchor's month alone.
	expect(monthsInWindow(months, '2026-09-03', 1)).toEqual(['2026-09']);

	// A ninety-day window from early September reaches back into June, so all four.
	expect(monthsInWindow(months, '2026-09-03', 90)).toEqual([
		'2026-09',
		'2026-08',
		'2026-07',
		'2026-06'
	]);
});

test('the browse window never returns a month the archive does not hold', () => {
	// The window reaches back to April, but only these three months were published.
	// A month absent from disk costs no request, because it is never in the result.
	expect(monthsInWindow(['2026-08', '2026-07', '2026-06'], '2026-08-20', 120)).toEqual([
		'2026-08',
		'2026-07',
		'2026-06'
	]);

	// And a month newer than the anchor is never in reach - the anchor is the
	// newest published day, so nothing after it can hold a story yet.
	expect(monthsInWindow(['2026-09', '2026-08'], '2026-08-20', 30)).toEqual(['2026-08']);
});

test('the browse window counts back inclusive of the anchor day', () => {
	// A thirty-day window ending 2026-08-20 opens on 2026-07-22: thirty days
	// counting the anchor itself, not thirty before it.
	expect(windowStart('2026-08-20', 30)).toBe('2026-07-22');
	expect(windowStart('2026-08-20', 1)).toBe('2026-08-20');

	// The arithmetic is real dates across a year boundary, not string subtraction.
	expect(windowStart('2026-01-05', 10)).toBe('2025-12-27');
});
