/** What every console route carries above its own panels.
 *
 * The console is three routes now, and a route is where a metric goes to die
 * unless something outside it says a metric is there. So two things are derived
 * once here and drawn identically on all three: a standing band that answers
 * "did it work, what is worst, how much room is left", and a navigation strip
 * whose every label carries its own worst state.
 *
 * Three facts and no control. The window governs nothing in the band - the band
 * stands on all three routes and is deliberately not windowed - so the control
 * sits below it, in a container of its own.
 *
 * It is server-only for the same reason `model-work.ts` is: it reads the
 * committed ledger under `state/`, which is not published, and SvelteKit
 * refuses to bundle `$lib/server/` for a browser.
 */

import { PAGES_CAP_BYTES, siteCost, siteRunway } from '$lib/charts/glance';
import { chronological, failing, resting, skipped } from '$lib/feed-health';
import { modelWork, type ModelDay } from '$lib/server/model-work';
import {
	evalRows,
	feedResults,
	itemHealthRows,
	loadManifests,
	publishedItems,
	type FeedResult,
	type RunRecord
} from '$lib/server/payload';
import { collectConfig, retentionConfig, runConfig } from '$lib/server/config';
import { loadMachineCounters, type MachineCounters } from '$lib/server/runtime-counters';

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

/** What a square means, in words. Colour is one signal and never the only one,
 * and the same three words the run strip 800 px below prints. */
const VERDICT_WORD: Record<Health, string> = {
	green: 'ran clean',
	amber: 'is worth a look',
	red: 'failed'
};

/** Squares the band draws before it starts counting instead.
 *
 * The schedule fires five runs a day, so twelve covers every day on record with
 * room to spare. Past that a row of squares stops being a row and becomes a
 * chart, and the band is not where a chart goes.
 */
const BAND_RUN_SQUARES = 12;

export type RouteId = 'pipelines' | 'model' | 'machine';

/** How loud a route's worst state is.
 *
 * Ranked rather than coloured. The strip never takes the health ramp - green,
 * amber and red on a label would say a route is failing, and a route is a noun -
 * so this ordering exists to pick the one worst thing across three routes and
 * to sort a route's own candidates, and never to paint anything.
 */
export const BROKEN = 3;
export const WORTH_A_LOOK = 2;
export const WORTH_KNOWING = 1;
export const CLEAR = 0;

interface Candidate {
	/** The strip's fragment: short enough to sit beside a label. */
	text: string;
	/** The band's version, which says what the state costs rather than naming
	 * it. The strip has room for two words and the band has room for a sentence,
	 * so one string for both was always going to be the strip's. */
	sentence: string;
	severity: number;
}

export interface ConsoleRoute {
	id: RouteId;
	/** The strip's word for the route. `Pipelines` is the owner's own, taken
	 * verbatim on 2026-08-30; `Summaries` and `Hardware` replaced `Model` and
	 * `Machine` on 2026-08-31. The id and the href did not move with them. */
	label: string;
	/** Route-relative and trailing-slashed. A component prefixes `base`. */
	href: string;
	/** One line under the strip, and the same text as the link's title. */
	description: string;
	/** The route's own worst state, appended to its label. Null when clear. */
	worst: string | null;
	severity: number;
}

/** One run of the newest day, as the band draws it. */
export interface BandRun {
	health: Health;
	/** What the square means, for a reader who cannot see the colour. */
	label: string;
}

export interface ConsoleBandFacts {
	/** The newest day the manifests hold, as a sentence. */
	verdict: {
		date: string | null;
		sentence: string;
		health: Health;
		/** One square a run, in the order they ran. It says what the sentence
		 * cannot: whether one run ate every failure or all five limped. */
		runs: BandRun[];
		/** Runs past the twelve drawn. A day of thirty squares is a chart. */
		moreRuns: number;
	};
	/** The one worst thing on the whole console, and which route it is on. */
	worst: { id: RouteId; label: string; href: string; sentence: string } | null;
	size: {
		/** The committed payload tree at the newest run, or null if unmeasured. */
		bytes: number | null;
		/** That tree against the 1 GB Pages cap. */
		capFraction: number | null;
		/** Megabytes left under the cap. */
		leftMb: number | null;
		/** Articles to the cap, at the cost the whole record measured. */
		articlesToCap: number | null;
		/** Published days the per-article cost was measured over. */
		measuredDays: number;
		sentence: string;
	};
}

export interface ConsoleShell {
	band: ConsoleBandFacts;
	routes: ConsoleRoute[];
	/** One sentence per route pointing at the panel another route owns. */
	carries: Record<RouteId, string>;
}

const DESCRIPTIONS: Record<RouteId, string> = {
	pipelines: 'Did the runs work, which feeds broke, and what each stage cost.',
	model: 'What the model wrote, how long it took, and what it got wrong.',
	machine: 'The hardware the model ran on, and how much it varied between runs.'
};

/** A count with its noun, singular where it is one. */
function plural(count: number, one: string, many: string): string {
	return `${count} ${count === 1 ? one : many}`;
}

/** Hours and minutes, or the honest absence of a measurement.
 *
 * Never a decimal hour: an operator reads a clock, and `4.2 h` is a number he
 * has to convert before it means anything. A total that rounds to nothing still
 * ran, so it prints `<1 m` rather than `0 m`.
 */
export function clock(ms: number | null): string | null {
	if (ms === null || ms <= 0) return null;
	const minutes = Math.round(ms / 60_000);
	if (minutes === 0) return '<1 m';
	const hours = Math.floor(minutes / 60);
	return hours === 0 ? `${minutes} m` : `${hours} h ${minutes % 60} m`;
}

/** Megabytes, to one decimal. */
function mb(bytes: number): string {
	return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** A count at the precision its basis supports.
 *
 * The rate under the runway is a median whose spread is near a fifth of itself,
 * so the trailing digits of a six-figure answer are noise. Three significant
 * figures leaves a small answer exact and stops a large one claiming a hundred
 * articles of accuracy nothing measured (Rule #10).
 */
function roughly(value: number): string {
	if (value <= 0) return '0';
	const scale = 10 ** Math.max(0, Math.floor(Math.log10(value)) - 2);
	return (Math.round(value / scale) * scale).toLocaleString('en-GB');
}

/** The same rule the run strip colours a square by, and the same floor CI opens
 * an issue on - so a red square, an open issue and this sentence agree. */
function health(run: RunRecord, floorPct: number): Health {
	if (run.status === 'failed') return 'red';
	const attempted = run.succeeded + run.failed;
	if (attempted === 0) return 'amber';
	if ((run.succeeded / attempted) * 100 < floorPct) return 'red';
	if (run.failed > 0 || run.status !== 'completed' || run.sourceListStale) return 'amber';
	return 'green';
}

/** The loudest candidate, or null when every one of them is clear. */
function worstOf(candidates: Candidate[]): Candidate | null {
	const ranked = [...candidates].sort((a, b) => b.severity - a.severity);
	return ranked[0] ?? null;
}

/** How many feeds are resting, and how many are failing without resting yet.
 *
 * `results` is already one row per feed per run: `feedResults` settles the
 * ledger once, so nothing here can count a re-run twice.
 */
function feedTrouble(results: FeedResult[], quarantineAfter: number) {
	const byFeed = new Map<string, FeedResult[]>();
	for (const row of results) {
		byFeed.set(row.feedId, [...(byFeed.get(row.feedId) ?? []), row]);
	}
	let rested = 0;
	let failed = 0;
	for (const group of byFeed.values()) {
		const ordered = chronological(group);
		// A skipped feed was never asked, so it can neither pass nor fail. It
		// still counts toward the rest, which is why `resting` reads the whole
		// ordered list rather than the asked ones.
		if (resting(ordered, quarantineAfter)) {
			rested += 1;
			continue;
		}
		if (ordered.filter((row) => !skipped(row)).some(failing)) failed += 1;
	}
	return { rested, failed };
}

/** What is wrong on Pipelines, loudest kind first.
 *
 * The runs come before the feeds and the order is load-bearing: a resting feed
 * and a failed run both rank BROKEN, `worstOf` sorts stably, and a rest clears
 * itself after `quarantine_after_failures` skips while a failed run does not.
 * Listing the feeds first handed every tie to the state that fixes itself.
 */
function pipelinesCandidates(
	newest: { date: string; records: RunRecord[] } | null,
	feeds: { rested: number; failed: number },
	quarantineAfter: number
): Candidate[] {
	const found: Candidate[] = [];
	if (newest !== null) {
		const verdicts = newest.records.map((run) => health(run, runConfig().success_floor_pct));
		const red = verdicts.filter((v) => v === 'red').length;
		const amber = verdicts.filter((v) => v === 'amber').length;
		if (red > 0) {
			found.push({
				text: `${plural(red, 'run', 'runs')} failed`,
				sentence: `${plural(red, 'run', 'runs')} failed, so the items ${red === 1 ? 'it' : 'they'} planned are not in the day.`,
				severity: BROKEN
			});
		}
		if (amber > 0) {
			found.push({
				text: `${plural(amber, 'run', 'runs')} worth a look`,
				sentence: `${plural(amber, 'run', 'runs')} finished but not cleanly, so the day may hold fewer items than it planned.`,
				severity: WORTH_A_LOOK
			});
		}
	}
	if (feeds.rested > 0) {
		// The retry count comes from `quarantine_after_failures`, never a literal:
		// an operator who moves the knob would otherwise be reading yesterday's
		// rule in today's sentence.
		const carry =
			feeds.rested === 1
				? '1 feed is resting, so nothing it carries reaches the digest.'
				: `${feeds.rested} feeds are resting, so nothing they carry reaches the digest.`;
		found.push({
			text: `${plural(feeds.rested, 'feed', 'feeds')} resting`,
			sentence: `${carry} Each is asked again after ${quarantineAfter} runs.`,
			severity: BROKEN
		});
	}
	if (feeds.failed > 0) {
		found.push({
			text: `${plural(feeds.failed, 'feed', 'feeds')} failing`,
			sentence: `${plural(feeds.failed, 'feed', 'feeds')} failed on the last ask, so the digest is short of what ${feeds.failed === 1 ? 'it carries' : 'they carry'} until ${feeds.failed === 1 ? 'it answers' : 'they answer'} again.`,
			severity: WORTH_A_LOOK
		});
	}
	return found;
}

/** What the Machine route's own panels would make an operator look at.
 *
 * The read spread is reported as a FACT and not as a verdict: nobody has agreed
 * how far apart two shards of one run may read before it is a problem, and a
 * severity that invented one would publish a threshold this project has not
 * taken. It sits at `WORTH_KNOWING` so it never outranks a real failure, and it
 * is on the strip because the number is the whole reason the route exists.
 */
function machineCandidates(counters: MachineCounters): Candidate[] {
	const found: Candidate[] = [];
	if (counters.refused.length > 0) {
		const n = counters.refused.length;
		found.push({
			text: `${plural(n, 'run', 'runs')} cannot be read`,
			sentence: `${plural(n, 'run', 'runs')} cannot be read, so no figure on the Hardware route counts ${n === 1 ? 'it' : 'them'}.`,
			severity: WORTH_A_LOOK
		});
	}
	const newest = counters.runs[0] ?? null;
	if (newest !== null) {
		const silent = newest.shards - newest.reported.length;
		if (silent > 0) {
			found.push({
				text: `${plural(silent, 'shard', 'shards')} reported nothing`,
				sentence: `${plural(silent, 'shard', 'shards')} of the newest run reported nothing, so the run's totals are short by whatever ${silent === 1 ? 'it' : 'they'} did.`,
				severity: WORTH_A_LOOK
			});
		}
		if (newest.readSpread.value !== null) {
			const spread = newest.readSpread.value.toFixed(2);
			found.push({
				text: `shards read ${spread}x apart`,
				sentence: `The newest run's shards read ${spread}x apart, so a rate taken over the whole run hides how slow the slowest of them was.`,
				severity: WORTH_KNOWING
			});
		}
	}
	return found;
}

function modelCandidates(day: ModelDay | null): Candidate[] {
	if (day === null) return [];
	const found: Candidate[] = [];
	if (day.failed !== null && day.failed > 0) {
		const n = day.failed;
		found.push({
			text: `${plural(n, 'item', 'items')} failed`,
			sentence: `${plural(n, 'item', 'items')} failed, so ${n === 1 ? 'it is' : 'they are'} not in the day the digest published.`,
			severity: BROKEN
		});
	}
	// Zero is the expected reading here: at the cap in force no prompt can reach
	// the window, so anything above zero says the cap moved past what fits.
	if (day.refusedForLength !== null && day.refusedForLength > 0) {
		const n = day.refusedForLength;
		found.push({
			text: `${plural(n, 'item', 'items')} too long to send`,
			sentence: `${plural(n, 'item', 'items')} ${n === 1 ? 'was' : 'were'} too long to send, so the model never saw ${n === 1 ? 'it' : 'them'} and the truncation cap is past what fits.`,
			severity: WORTH_A_LOOK
		});
	}
	if (day.notSure !== null && day.notSure > 0) {
		const n = day.notSure;
		found.push({
			text: `${n} marked "not sure"`,
			sentence: `${n} ${n === 1 ? 'summary is' : 'summaries are'} marked "not sure", so the checker could not hold ${n === 1 ? 'it' : 'them'} against the article.`,
			severity: WORTH_A_LOOK
		});
	}
	if (day.readInPart !== null && day.readInPart > 0) {
		const n = day.readInPart;
		found.push({
			text: `${plural(n, 'article', 'articles')} read only in part`,
			sentence: `${plural(n, 'article', 'articles')} ${n === 1 ? 'was' : 'were'} read only in part, so the summary was written from less than the whole piece.`,
			severity: WORTH_KNOWING
		});
	}
	return found;
}

/** What every console route draws above its own panels.
 *
 * One read of the committed ledger, one derivation, three routes. The band and
 * the strip cannot disagree between routes because neither is computed twice.
 */
export function consoleShell(): ConsoleShell {
	const manifests = loadManifests();
	const newest = manifests[0] ?? null;
	const floorPct = runConfig().success_floor_pct;
	const budgetBytes = retentionConfig().site_budget_mb * 1024 * 1024;
	const quarantineAfter = collectConfig().quarantine_after_failures;
	const feeds = feedTrouble(feedResults(), quarantineAfter);

	const scored = evalRows().rows;
	const itemRows = itemHealthRows().rows;
	const modelDays = modelWork(scored, itemRows).flatMap((row) =>
		row.kind === 'day' ? [row.day] : []
	);
	const newestModelDay = modelDays[0] ?? null;

	// --- The verdict -------------------------------------------------------
	// Counts first, then what is wrong with them. An operator who reads only the
	// first clause still knows whether the day published.
	let sentence: string;
	let verdictHealth: Health = 'green';
	let runRow: BandRun[] = [];
	if (newest === null) {
		sentence = 'No run has recorded a manifest yet, so there is nothing to report on.';
		verdictHealth = 'amber';
	} else {
		const planned = newest.records.reduce((total, run) => total + run.planned, 0);
		const succeeded = newest.records.reduce((total, run) => total + run.succeeded, 0);
		const failed = newest.records.reduce((total, run) => total + run.failed, 0);
		const verdicts = newest.records.map((run) => health(run, floorPct));
		verdictHealth = verdicts.includes('red')
			? 'red'
			: verdicts.includes('amber')
				? 'amber'
				: 'green';
		runRow = verdicts.map((value, index) => ({
			health: value,
			label: `Run ${index + 1} ${VERDICT_WORD[value]}`
		}));
		const head = `${newest.date} ran ${plural(newest.records.length, 'run', 'runs')} and published ${succeeded} of ${planned} planned items.`;
		const tail =
			verdictHealth === 'green'
				? 'Every run finished clean.'
				: failed > 0
					? `${plural(failed, 'item', 'items')} failed.`
					: 'One or more runs is worth a look.';
		sentence = `${head} ${tail}`;
	}

	// --- The routes and their worst states ---------------------------------
	const worstPipelines = worstOf(pipelinesCandidates(newest, feeds, quarantineAfter));
	const worstModel = worstOf(modelCandidates(newestModelDay));
	// The Machine route draws the counters since 2026-08-31, so its worst state is
	// derived from them like the other two rather than being a standing note that
	// nothing reads them. A route whose label never changes is a route an operator
	// stops opening.
	const worstMachine = worstOf(machineCandidates(loadMachineCounters()));

	const routes: ConsoleRoute[] = [
		{
			id: 'pipelines',
			label: 'Pipelines',
			href: '/console/',
			description: DESCRIPTIONS.pipelines,
			worst: worstPipelines?.text ?? null,
			severity: worstPipelines?.severity ?? CLEAR
		},
		{
			id: 'model',
			label: 'Summaries',
			href: '/console/model/',
			description: DESCRIPTIONS.model,
			worst: worstModel?.text ?? null,
			severity: worstModel?.severity ?? CLEAR
		},
		{
			id: 'machine',
			label: 'Hardware',
			href: '/console/machine/',
			description: DESCRIPTIONS.machine,
			worst: worstMachine?.text ?? null,
			severity: worstMachine?.severity ?? CLEAR
		}
	];

	const loudest = [...routes]
		.filter((route) => route.worst !== null)
		.sort((a, b) => b.severity - a.severity)[0];
	/** The winning candidate's own long form, kept rather than recomputed. */
	const sentenceFor: Record<RouteId, string | null> = {
		pipelines: worstPipelines?.sentence ?? null,
		model: worstModel?.sentence ?? null,
		machine: worstMachine?.sentence ?? null
	};

	// --- Site size ---------------------------------------------------------
	// Not windowed, and that is the difference between this and the panel on
	// Pipelines. The band stands on all three routes, so a figure that moved
	// when a control on one route moved would read as three different sites.
	const bytes = newest?.siteBytes ?? null;
	const cost = siteCost(manifests, publishedItems(), null);
	const runway = bytes === null ? null : siteRunway(bytes, cost.median, budgetBytes);
	const capFraction = bytes === null ? null : bytes / PAGES_CAP_BYTES;
	// One line. The rate this divides by, the days it was measured over and the
	// clause about which tree the cap measures all live on `What one more article
	// costs`, which already owns the rate, its n and its spread - and a band that
	// repeated them spent sixty of its hundred words on a caveat.
	const sizeSentence =
		bytes === null
			? 'No run has recorded a size yet, so there is nothing to hold against the 1 GB limit.'
			: runway === null
				? `${mb(bytes)} of the 1 GB limit - no published day has grown it over an article yet, so there is no room figure.`
				: `${mb(bytes)} of the 1 GB limit - room for about ${roughly(runway.toCap)} more articles.`;

	// --- The three carries --------------------------------------------------
	// One sentence each, no chart. They are what stops a route hiding the panel
	// that explains another, and every number in them is derived rather than
	// stated: a carry quoting a figure nobody measured is worse than no carry.
	const modelClock = clock(newestModelDay?.totalMs ?? null);
	const runSpread = readSpreadOf(newest?.date ?? null, itemRows);
	const articlesToday = newest === null ? null : (publishedItems().get(newest.date) ?? null);

	return {
		band: {
			verdict: {
				date: newest?.date ?? null,
				sentence,
				health: verdictHealth,
				runs: runRow.slice(0, BAND_RUN_SQUARES),
				moreRuns: Math.max(0, runRow.length - BAND_RUN_SQUARES)
			},
			worst:
				loudest === undefined || sentenceFor[loudest.id] === null
					? null
					: {
							id: loudest.id,
							label: loudest.label,
							href: loudest.href,
							sentence: sentenceFor[loudest.id] as string
						},
			size: {
				bytes,
				capFraction,
				leftMb: bytes === null ? null : (PAGES_CAP_BYTES - bytes) / 1024 / 1024,
				articlesToCap: runway?.toCap ?? null,
				measuredDays: cost.days.length,
				sentence: sizeSentence
			}
		},
		routes,
		carries: {
			pipelines:
				modelClock === null
					? 'Nothing on this day recorded how long the model spent.'
					: `The model spent ${modelClock} of this.`,
			model:
				runSpread === null
					? 'No run on this day recorded a read speed, so there is no spread to compare.'
					: runSpread.runs < 2
						? 'This day ran as one run, so there is nothing to compare it against.'
						: `This day ran in ${runSpread.runs} runs, ${runSpread.ratio.toFixed(2)}x apart on read speed.`,
			machine:
				articlesToday === null
					? 'No article is on record for this day.'
					: `${plural(articlesToday, 'article', 'articles')} on this day.`
		}
	};
}

/** How far apart the day's runs read, fastest over slowest.
 *
 * The read rate and not the write rate: measured over the committed ledger the
 * write rate barely moves and the read rate is where the host lottery bites, so
 * a spread taken on writing would report a steady machine on a day that was
 * anything but. Cached prompt tokens come out of the count - the machine did
 * not read them.
 */
function readSpreadOf(
	date: string | null,
	rows: Record<string, string>[]
): { runs: number; ratio: number } | null {
	if (date === null) return null;
	const perRun = new Map<string, { tokens: number; ms: number }>();
	for (const row of rows) {
		if ((row.date ?? '') !== date) continue;
		const prefillMs = Number(row.prefill_ms);
		const prompt = Number(row.input_tokens);
		const cached = row.cached_tokens === '' ? 0 : Number(row.cached_tokens);
		if (!Number.isFinite(prefillMs) || !Number.isFinite(prompt) || !Number.isFinite(cached)) {
			continue;
		}
		const evaluated = prompt - cached;
		if (prefillMs <= 0 || evaluated <= 0) continue;
		const runId = row.run_id ?? '';
		const bucket = perRun.get(runId) ?? { tokens: 0, ms: 0 };
		bucket.tokens += evaluated;
		bucket.ms += prefillMs;
		perRun.set(runId, bucket);
	}
	const rates = [...perRun.values()].map((bucket) => bucket.tokens / (bucket.ms / 1000));
	if (rates.length === 0) return null;
	const slowest = Math.min(...rates);
	if (slowest <= 0) return null;
	return { runs: rates.length, ratio: Math.max(...rates) / slowest };
}
