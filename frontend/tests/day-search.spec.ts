import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ENCODER_DIMENSIONS } from '../src/lib/assist/encoder';
import { indexOf, monthsBackFrom, type MonthIndex } from '../src/lib/assist/month';
import { decodeVectorAt } from '../src/lib/assist/search';
import {
	costNote,
	newSearch,
	NO_SCOPE,
	scopeSentence,
	stateSentence,
	type SearchPhase,
	type SearchScope
} from '../src/lib/assist/session';
import { markParts } from '../src/lib/day-shape';

/**
 * Row #5's oracle: one field, two tiers, and the second one never gates the first.
 *
 * The instant tier already had an oracle - `filter-bar.spec.ts` proves a needle
 * keeps exactly the stories whose title, summary or key points hold it, and
 * that typing asks for nothing. This file holds the half that is new: the
 * ranked ids a question comes back with, every way a question can refuse, the
 * sentence each refusal prints, and the rule that turns a matched word into a
 * mark without turning a headline into markup.
 *
 * **Pure, and driven in Node, because a browser cannot show any of it.** The
 * canary build publishes one month and eight stories, so a scope that reaches
 * two months, a browser that cannot run the encoder, and a month whose vectors
 * are absent are three states the fixture has no way to reach - and the fourth,
 * a real ranked answer, costs a 43 MB download to ask once. The committed
 * `2026-08` shard is the corpus here for the same reason `archive-scope.spec.ts`
 * uses it: real entries, real vectors, real byte offsets, and one item's own
 * vector as the question, so retrieval is checked with no encoder at all.
 *
 * The browser half of the row is in `filter-bar.spec.ts`, beside the panel the
 * field belongs to.
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

const SETTINGS = {
	similarity_floor: 0.35,
	result_limit: 10,
	search_months: 1,
	search_min_days: 7
};

const COST = { here: 43, elsewhere: 50 };

/** Everything a session cannot do for itself, with nothing real behind it. */
function parts(over: Partial<Parameters<typeof newSearch>[0]> = {}) {
	const { index, vectors } = committed();
	return {
		supported: () => true,
		loadIndex: async (month: string) => (month === index.month ? index : null),
		loadVectors: async () => vectors,
		embed: async () => [],
		...over
	};
}

/** One session's phases, in the order they were reported. */
function watcher() {
	const phases: SearchPhase[] = [];
	const scopes: SearchScope[] = [];
	return {
		phases,
		scopes,
		report: {
			onPhase: (phase: SearchPhase) => phases.push(phase),
			onScope: (scope: SearchScope) => scopes.push(scope)
		}
	};
}

test.describe('what a question comes back with', () => {
	test('a story is found by its own vector, from the month the day sits in', async () => {
		const { index, vectors } = committed();
		// One story, and its own vector as the question. It scores 1.0 against
		// itself, so a miss can only be a session that never read that month.
		const target = index.entries.find((entry) => entry.vector !== null);
		expect(target, 'no entry in the committed shard carries a vector').toBeDefined();
		const query = decodeVectorAt(vectors, target!.vector!, ENCODER_DIMENSIONS, index.scale);
		expect(query, 'the target vector did not decode').not.toBeNull();

		const watch = watcher();
		const search = newSearch(parts({ embed: async () => query! }), SETTINGS);
		const found = await search.ask([index.month], 'anything at all', watch.report);

		expect(found, 'the session refused a question it could answer').not.toBeNull();
		expect(
			found!.hits.map((hit) => hit.entry.item_id),
			'the story whose own vector was the question is not in its own answer'
		).toContain(target!.item_id);
		// The ranking is a selector and not a grade, so the best answer leads.
		expect(found!.hits[0]!.entry.item_id).toBe(target!.item_id);
		expect(found!.scope, 'the answer does not say how far back it read').not.toBe('');
		expect(found!.searched).toBeGreaterThan(0);
	});

	test('the answer is dropped when the reader stopped waiting for it', async () => {
		const { index, vectors } = committed();
		const query = decodeVectorAt(
			vectors,
			index.entries.find((entry) => entry.vector !== null)!.vector!,
			ENCODER_DIMENSIONS,
			index.scale
		);
		const watch = watcher();
		const search = newSearch(
			parts({
				// The reader presses Stop while the encoder is still working. The bytes
				// keep arriving - a browser fetch cannot be called back - so the answer
				// does land, and it must not be handed to a page the reader took itself
				// out of.
				embed: async () => {
					search.stop(watch.report);
					return query!;
				}
			}),
			SETTINGS
		);
		const found = await search.ask([index.month], 'anything at all', watch.report);

		expect(found, 'a stopped search still answered').toBeNull();
		expect(watch.phases.at(-1), 'the page was left waiting').toEqual({ name: 'offer' });
	});
});

test.describe('every way a question refuses, and what it says', () => {
	test('a browser that cannot run the encoder is told so, once', async () => {
		const watch = watcher();
		const search = newSearch(parts({ supported: () => false }), SETTINGS);

		expect(await search.ask(['2026-08'], 'anything', watch.report)).toBeNull();
		const last = watch.phases.at(-1)!;
		expect(last.name).toBe('blocked');
		expect(
			stateSentence({ phase: last, held: false, cached: 'absent', cost: COST })
		).toBe(
			'Search is unavailable here - this browser cannot run it. Everything above still works.'
		);
	});

	test('a month with no index leaves the page browsing', async () => {
		const watch = watcher();
		const search = newSearch(parts({ loadIndex: async () => null }), SETTINGS);

		expect(await search.ask(['2026-08'], 'anything', watch.report)).toBeNull();
		expect(watch.phases.at(-1)).toEqual({
			name: 'blocked',
			reason: 'these stories cannot be searched on this device'
		});
	});

	test('a month whose vectors are absent browses and says search cannot', async () => {
		const watch = watcher();
		const search = newSearch(parts({ loadVectors: async () => null }), SETTINGS);

		expect(await search.ask(['2026-08'], 'anything', watch.report)).toBeNull();
		expect(watch.phases.at(-1)!.name).toBe('blocked');
		// Nothing was searched, so nothing may claim a reach. A blocked page hides
		// the scope line, and the scope behind it is empty for the same reason:
		// absent vectors are the designed split, not a half-failure - the list needs
		// no vector and search cannot work without one.
		expect(watch.scopes.at(-1)).toEqual(NO_SCOPE);
	});

	test('a reader who presses Enter again on a blocked page is told again', async () => {
		const watch = watcher();
		let reads = 0;
		const search = newSearch(
			parts({
				loadVectors: async () => {
					reads += 1;
					return null;
				}
			}),
			SETTINGS
		);

		expect(await search.ask(['2026-08'], 'anything', watch.report)).toBeNull();
		expect(await search.ask(['2026-08'], 'anything else', watch.report)).toBeNull();

		// The second ask ends on the same sentence rather than on the working state
		// it opened with. A page left working shows a Stop button for a download
		// that is not running, and waits for an answer that is never coming.
		expect(watch.phases.at(-1)).toEqual({
			name: 'blocked',
			reason: 'these stories cannot be searched on this device'
		});
		// And it is told from what the session already knows: the refused month is
		// not fetched a second time.
		expect(reads, 'the same missing file was asked for twice').toBe(1);
	});

	test('a download that does not finish offers a retry rather than ending the page', async () => {
		const watch = watcher();
		const search = newSearch(
			parts({
				embed: async () => {
					throw new Error('the download did not finish');
				}
			}),
			SETTINGS
		);

		expect(await search.ask(['2026-08'], 'anything', watch.report)).toBeNull();
		const last = watch.phases.at(-1)!;
		expect(last).toEqual({ name: 'failed' });
		expect(stateSentence({ phase: last, held: false, cached: 'absent', cost: COST })).toBe(
			'Search is unavailable right now - the download did not finish.'
		);
	});

	test('the byte count stops counting when the measurement stops', () => {
		const counting: SearchPhase = {
			name: 'working',
			progress: { loaded: 12 * 1024 * 1024, landed: false }
		};
		expect(stateSentence({ phase: counting, held: false, cached: 'absent', cost: COST })).toBe(
			'Downloading - 12.0 MB of 43 MB.'
		);
		// The weights are the last and largest file, so the moment they land a byte
		// count can no longer say anything. A bar that kept moving on no
		// measurement would be a bar that is making it up.
		const landed: SearchPhase = {
			name: 'working',
			progress: { loaded: 12 * 1024 * 1024, landed: true }
		};
		expect(stateSentence({ phase: landed, held: false, cached: 'absent', cost: COST })).toBe(
			'Getting ready to search.'
		);
	});

	test('a reader who has already paid is not asked again', () => {
		const offer: SearchPhase = { name: 'offer' };
		expect(stateSentence({ phase: offer, held: true, cached: 'unknown', cost: COST })).toContain(
			'The download is done'
		);
		expect(stateSentence({ phase: offer, held: false, cached: 'present', cost: COST })).toContain(
			'The download is done'
		);
		// The one state a reader cannot guess at: the weights moved, so the path
		// moved with them and a returning searcher pays the whole download again.
		expect(stateSentence({ phase: offer, held: false, cached: 'stale', cost: COST })).toContain(
			'changed since your last visit'
		);
		// And the cost is named before it is spent, on both surfaces, in one
		// spelling of one promise.
		const first = stateSentence({ phase: offer, held: false, cached: 'absent', cost: COST });
		expect(first).toContain('43 MB');
		expect(first).toContain('Nothing you type leaves your browser');
		expect(costNote(COST)).toContain('43 MB');
		expect(costNote(COST)).toContain('Nothing you type leaves your browser');
		expect(costNote(COST), 'the second origin is named before it is reached').toContain('50 MB');
	});

	test('the scope names days, never a month', () => {
		expect(
			scopeSentence({ indexes: [], searched: 0, label: '', partial: false }),
			'a scope nobody has read yet names nothing'
		).toBe('');
		expect(
			scopeSentence({
				indexes: [],
				searched: 431,
				label: '1 to 20 August 2026',
				partial: false
			})
		).toBe('Searching 1 to 20 August 2026 - 431 stories.');
		expect(
			scopeSentence({ indexes: [], searched: 1, label: '1 September 2026', partial: true })
		).toBe('Searching 1 September 2026 - 1 story. Older stories are not searched.');
	});
});

test.describe('the months a reading page may reach', () => {
	test('the months are taken from the day in the address, newest first', () => {
		expect(monthsBackFrom('2026-09-24', 1)).toEqual(['2026-09', '2026-08']);
		// Over a year boundary, which is the case a month arithmetic written by
		// hand gets wrong.
		expect(monthsBackFrom('2026-01-03', 2)).toEqual(['2026-01', '2025-12', '2025-11']);
		// A day page reaching back from its own date, not from today: a reader deep
		// in the archive searches around what they are reading.
		expect(monthsBackFrom('2026-03-15', 0)).toEqual(['2026-03']);
	});

	test('anything that is not a published date reaches nothing', () => {
		// One shell answers every dated URL, so `/nonsense/` gets this far. A path
		// built out of whatever arrived is the shape of mistake Guardrail #11 is
		// about, so it is checked rather than trusted.
		expect(monthsBackFrom('not-a-date', 1)).toEqual([]);
		expect(monthsBackFrom('', 1)).toEqual([]);
	});
});

test.describe('the mark a field leaves behind', () => {
	test('the needle is sliced out of the story, in the capitalisation the story used', () => {
		const parts = markParts('A Reactor in Kerala', 'reactor');
		expect(parts).toEqual([
			{ text: 'A ', hit: false },
			{ text: 'Reactor', hit: true },
			{ text: ' in Kerala', hit: false }
		]);
		// Joined back it is the string it came from, every time. A mark that ate a
		// character would be a card quietly publishing something else.
		expect(parts.map((part) => part.text).join('')).toBe('A Reactor in Kerala');
	});

	test('every run is marked, including one that opens or closes the line', () => {
		expect(markParts('reactor and reactor', 'reactor').filter((part) => part.hit)).toHaveLength(2);
		expect(markParts('reactor', 'reactor')).toEqual([{ text: 'reactor', hit: true }]);
	});

	test('no needle and no match are the page as it always was', () => {
		expect(markParts('A reactor', null)).toEqual([{ text: 'A reactor', hit: false }]);
		expect(markParts('A reactor', '')).toEqual([{ text: 'A reactor', hit: false }]);
		expect(markParts('A reactor', 'pumpjack')).toEqual([{ text: 'A reactor', hit: false }]);
	});

	test('neither the query nor the story is ever turned into markup', () => {
		// The needle is untrusted reader text and the story is untrusted payload
		// text. This function returns text and the caller renders each part as a
		// text node, so there is nothing here for `{@html}` to be handed
		// (`CLAUDE.md` Guardrail #11).
		const nasty = '<script>alert(1)</script>';
		const parts = markParts(`A ${nasty} story`, nasty.toLowerCase());
		expect(parts.map((part) => part.text).join('')).toBe(`A ${nasty} story`);
		for (const part of parts) {
			expect(typeof part.text).toBe('string');
		}
		// And a needle carrying a tag marks the tag as text rather than opening one:
		// the hit is the angle brackets themselves, handed to the page as a string.
		expect(parts.filter((part) => part.hit).map((part) => part.text)).toEqual([nasty]);
	});
});
