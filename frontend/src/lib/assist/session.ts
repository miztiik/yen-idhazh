/** One reader's on-device search: the phases it moves through, and the
 * sentences that report them.
 *
 * **Lifted out of `ArchiveSearch.svelte` on 2026-09-24, and the reason is that
 * a second surface now searches.** The day page gained a semantic tier, and the
 * archive's control already held the whole machine - the phase it is in, which
 * months it may rank over, the one gesture, and the five sentences a reader
 * reads. Copying that into a second component would have left two phase
 * machines and two spellings of one privacy promise, which is how they drift
 * apart (Guardrail #5, Guardrail #8). There is one of each, here, and both
 * components are renderers over it.
 *
 * **It fetches nothing itself.** The three side-effecting calls - read a month
 * index, read a month's vectors, embed a query - arrive as arguments. That is
 * not ceremony: `index.ts` and `loader.ts` both import `$app/paths`, so a module
 * that reached for them could only ever run in a browser, and this rule set is
 * exactly the part worth driving in Node. `readScope` in `search.ts` already
 * takes its loader the same way, for the same reason.
 *
 * **The two download figures are arguments too.** `DOWNLOAD_MB` and
 * `DOWNLOAD_MB_ELSEWHERE` are measured quantities and they stay in
 * `loader.ts`, beside the code that does the downloading. The words that print
 * them live here, once. One spelling of the promise, one home for the numbers.
 */

import type { MonthIndex } from './month';
import type { CachedEncoder, EncoderProgress } from './loader';
import {
	dayRange,
	rank,
	readScope,
	searchedDays,
	type SearchableMonth,
	type SearchOutcome
} from './search';

/** What a search is doing right now. Each one is a sentence a reader reads. */
export type SearchPhase =
	| { name: 'offer' }
	| { name: 'working'; progress: EncoderProgress }
	/** The download did not finish. One flaky connection, and a way back. */
	| { name: 'failed' }
	/** Nothing to retry: this browser, or these stories, cannot do it. */
	| { name: 'blocked'; reason: string };

/** The months a search may rank over, and what they can answer for. */
export interface SearchScope {
	indexes: MonthIndex[];
	/** How many stories carry a vector across those months. */
	searched: number;
	/** "1 to 20 August 2026", or the empty string when nothing is in scope. */
	label: string;
	/** True when a month this session asked for could not be searched, so the
	 * page can say that older stories are out of reach. */
	partial: boolean;
}

/** The empty scope. Returned whenever a session cannot search at all, so a
 * caller never has to tell "nothing yet" from "nothing ever". */
export const NO_SCOPE: SearchScope = {
	indexes: [],
	searched: 0,
	label: '',
	partial: false
};

/** The three things a session cannot do for itself. */
export interface SearchParts {
	/** True when this browser can run the encoder at all. */
	supported(): boolean;
	loadIndex(month: string): Promise<MonthIndex | null>;
	loadVectors(month: string): Promise<Int8Array | null>;
	embed(text: string, onProgress: (progress: EncoderProgress) => void): Promise<number[]>;
}

/** How wide and how close, straight off `config/idhazh.json`. */
export interface SearchSettings {
	similarity_floor: number;
	result_limit: number;
	search_months: number;
	search_min_days: number;
}

/** Told on every change, so a component holds no phase machine of its own.
 *
 * The same shape `watchDay` uses in `day.ts`: one call, statuses through a
 * callback, the answer returned.
 */
export interface SearchReport {
	onPhase(phase: SearchPhase): void;
	/** Told once the months in scope are known, so the page can say how far back
	 * a search reached before the answer lands. */
	onScope?(scope: SearchScope): void;
}

export interface Search {
	/** Read the months a search would rank over. Idempotent - the second call
	 * costs nothing - and it is the first thing that fetches, so a surface that
	 * has not been asked for a search never calls it. */
	open(months: string[], report: SearchReport): Promise<SearchScope>;
	/** One question. Null when the search did not run, and the phase says why. */
	ask(months: string[], text: string, report: SearchReport): Promise<SearchOutcome | null>;
	/** Leave the page exactly as it was.
	 *
	 * The bytes already asked for keep arriving - a browser fetch cannot be
	 * called back - and the loader holds that one request, so a later search
	 * joins it rather than starting another. What stops is the waiting.
	 */
	stop(report: SearchReport): void;
	/** True once the encoder has answered in this tab, which is the difference
	 * between "the download is done" and "the first search downloads". */
	held(): boolean;
}

/** Everything one reader's searching keeps between asks. */
export function newSearch(parts: SearchParts, settings: SearchSettings): Search {
	let scope: SearchScope | null = null;
	/** Why this session cannot search, once something has ruled that it cannot.
	 *
	 * Held separately from the scope because the two answer different questions.
	 * The scope is a download, and it is not taken twice. The reason is a
	 * sentence, and it is owed on every ask - a reader who presses Enter again
	 * gets told again, rather than watching a Stop button that never resolves.
	 */
	let blocked: string | null = null;
	/** The months whose vectors are in hand. Read once per session, not per ask. */
	let ranked: SearchableMonth[] | null = null;
	let hasHeld = false;
	// Which download the sentence is allowed to describe. Bumped by a stop, by
	// every new search, and by a failure, so a file that lands after any of those
	// is dropped rather than reviving a state the reader was taken out of.
	let attempt = 0;

	function refuse(report: SearchReport, reason: string): SearchScope {
		blocked = reason;
		scope = NO_SCOPE;
		report.onPhase({ name: 'blocked', reason });
		report.onScope?.(NO_SCOPE);
		return NO_SCOPE;
	}

	async function open(months: string[], report: SearchReport): Promise<SearchScope> {
		if (blocked !== null) return refuse(report, blocked);
		if (scope !== null) return scope;
		if (!parts.supported()) return refuse(report, 'this browser cannot run it');
		const indexes = await readScope(
			months,
			{ months: settings.search_months, minDays: settings.search_min_days },
			parts.loadIndex
		);
		if (indexes.length === 0) {
			return refuse(report, 'these stories cannot be searched on this device');
		}
		const days = searchedDays(indexes);
		const searched = indexes.reduce(
			(count, index) =>
				count + index.entries.filter((entry) => entry.vector !== null).length,
			0
		);
		scope = {
			indexes,
			searched,
			label: days.length === 0 ? '' : dayRange(days[0]!, days[days.length - 1]!),
			partial: indexes.length < months.length
		};
		report.onScope?.(scope);
		return scope;
	}

	/** Fetch the vectors of every month in scope, before the encoder and not after.
	 *
	 * 2.53 MB a month against 43 MB, measured 2026-08-26 at the rate the committed
	 * days ran. A reader the big download cannot help is not asked to spend it,
	 * which is the same rule the encoder-identity check follows.
	 */
	async function readVectors(open: SearchScope): Promise<boolean> {
		if (ranked !== null) return ranked.length > 0;
		const ready: SearchableMonth[] = [];
		for (const index of open.indexes) {
			const vectors = await parts.loadVectors(index.month);
			if (vectors) ready.push({ index, vectors });
		}
		ranked = ready;
		return ready.length > 0;
	}

	async function ask(
		months: string[],
		text: string,
		report: SearchReport
	): Promise<SearchOutcome | null> {
		const query = text.trim();
		if (query === '') return null;

		const mine = ++attempt;
		report.onPhase({ name: 'working', progress: { loaded: 0, landed: false } });
		try {
			const reach = await open(months, report);
			if (reach.indexes.length === 0) return null;
			if (!(await readVectors(reach))) {
				if (mine !== attempt) return null;
				refuse(report, 'these stories cannot be searched on this device');
				return null;
			}
			const vector = await parts.embed(query, (progress) => {
				if (mine === attempt) report.onPhase({ name: 'working', progress });
			});
			if (mine !== attempt) return null;
			hasHeld = true;
			report.onPhase({ name: 'offer' });
			const hits = rank(ranked ?? [], vector, {
				limit: settings.result_limit,
				minScore: settings.similarity_floor
			});
			return {
				query,
				hits,
				searched: reach.searched,
				scope: reach.label,
				capped: hits.length >= settings.result_limit
			};
		} catch (error) {
			console.error('[search] the search did not run', error);
			if (mine !== attempt) return null;
			// This attempt is over. Its other files are still arriving - the library
			// loads the tokenizer and the weights at the same time, and only one of
			// them failed - and each one still reports its progress. Ending the
			// attempt here is what stops the next report reviving a download the
			// reader has already been told did not finish, and taking the retry with
			// it for the rest of the page's life.
			attempt += 1;
			report.onPhase({ name: 'failed' });
			return null;
		}
	}

	return {
		open,
		ask,
		stop(report: SearchReport) {
			attempt += 1;
			report.onPhase({ name: 'offer' });
		},
		held: () => hasHeld
	};
}

/** What the two origins cost, in megabytes. Both figures live in `loader.ts`,
 * beside the code that fetches them; this is how they reach the words. */
export interface DownloadCost {
	/** Our own origin, gzipped. The figure almost everybody pays. */
	here: number;
	/** The second origin, which serves the weights uncompressed. */
	elsewhere: number;
}

/** Mebibytes to one place, which is the precision a reader can use. */
export function megabytes(bytes: number): string {
	return (bytes / 1024 / 1024).toFixed(1);
}

/** What a search costs a reader's privacy, said before the download starts.
 *
 * The query clause is unconditional and stays first, because it is the thing a
 * reader is actually worried about: what they type is matched on their own
 * device against vectors this site committed, and it goes nowhere whatever
 * happens to the download.
 *
 * The second clause is conditional and says so. Since 2026-09-10 the encoder
 * has a second origin, reached only after this site has failed to hand a reader
 * the weights - and a fetch to anyone is a fetch that shows them an IP address,
 * a browser string and where the request came from. Almost nobody pays that, so
 * the sentence does not open with it; but a reader deciding whether to spend
 * it is told before they do, not after.
 *
 * `cost.elsewhere` rather than `cost.here` in that clause: the second origin
 * serves the weights uncompressed, so the same encoder costs about 7 MB more
 * when it comes from there.
 */
export function privacyNote(cost: DownloadCost): string {
	return (
		'Nothing you type leaves your browser. If this site cannot serve the ' +
		'files, your browser asks Hugging Face for them instead - about ' +
		`${cost.elsewhere} MB, and they would see your request.`
	);
}

/** Everything the state sentence is a function of. */
export interface SearchState {
	phase: SearchPhase;
	/** True once the encoder has answered in this tab. */
	held: boolean;
	cached: CachedEncoder;
	cost: DownloadCost;
}

/** The model's state as a sentence, never a dot.
 *
 * Five of them: not downloaded, downloading, ready, the encoder changed since
 * last time, and this browser cannot run it. A dot is colour on its own unless
 * it carries a word, and once it carries a word it is a sentence.
 *
 * Progress is bytes, and it stops when the measurement stops. The count is the
 * library's own, so it covers the encoder's files and not the ONNX runtime
 * behind them. When the weights land the counter can no longer see anything, so
 * it gives up and prints a word rather than animating over a number it does not
 * have.
 */
export function stateSentence(state: SearchState): string {
	const { phase, cost } = state;
	if (phase.name === 'blocked') {
		return `Search is unavailable here - ${phase.reason}. Everything above still works.`;
	}
	if (phase.name === 'failed') {
		return 'Search is unavailable right now - the download did not finish.';
	}
	if (phase.name === 'working') {
		return phase.progress.loaded > 0 && !phase.progress.landed
			? `Downloading - ${megabytes(phase.progress.loaded)} MB of ${cost.here} MB.`
			: 'Getting ready to search.';
	}
	if (state.held || state.cached === 'present') {
		return 'Search runs on your device. Nothing you type leaves your browser. The download is done.';
	}
	if (state.cached === 'stale') {
		return (
			'The search files changed since your last visit. The next search downloads ' +
			`${cost.here} MB from this site again, once. ${privacyNote(cost)}`
		);
	}
	return (
		`Search runs on your device. The first search downloads ${cost.here} MB from ` +
		`this site, once. ${privacyNote(cost)}`
	);
}

/** What a reading page says about the cost, before a key can spend it.
 *
 * Shorter than the archive's sentence and it opens on the gesture rather than
 * on the device, because the reader came here to read: the page has to say what
 * the extra key costs, not describe a feature they did not ask for (Susan,
 * 2026-09-24). The promise and the second origin are the archive's own words,
 * because two spellings of one privacy promise is how they drift apart.
 */
export function costNote(cost: DownloadCost): string {
	return (
		`Searching other days downloads ${cost.here} MB from this site, once. ` +
		privacyNote(cost)
	);
}

/** How far back a search reached, in days rather than in month names.
 *
 * A month name is not a window, and printing one over a partial month reads as
 * a promise the search cannot keep: on 1 September "September 2026" looks like
 * thirty days and holds one.
 */
export function scopeSentence(scope: SearchScope): string {
	if (scope.label === '') return '';
	const stories = scope.searched === 1 ? 'story' : 'stories';
	return (
		`Searching ${scope.label} - ${scope.searched} ${stories}.` +
		(scope.partial ? ' Older stories are not searched.' : '')
	);
}
