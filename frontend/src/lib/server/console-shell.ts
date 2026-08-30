/** What every console route carries above its own panels.
 *
 * The console is three routes now, and a route is where a metric goes to die
 * unless something outside it says a metric is there. So two things are derived
 * once here and drawn identically on all three: a standing band that answers
 * "did it work, what is worst, how much room is left", and a navigation strip
 * whose every label carries its own worst state.
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

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

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
	text: string;
	severity: number;
}

export interface ConsoleRoute {
	id: RouteId;
	/** Verbatim as the owner wrote them on 2026-08-30. */
	label: string;
	/** Route-relative and trailing-slashed. A component prefixes `base`. */
	href: string;
	/** One line under the strip, and the same text as the link's title. */
	description: string;
	/** The route's own worst state, appended to its label. Null when clear. */
	worst: string | null;
	severity: number;
}

export interface ConsoleBandFacts {
	/** The newest day the manifests hold, as a sentence. */
	verdict: { date: string | null; sentence: string; health: Health };
	/** The one worst thing on the whole console, and which route it is on. */
	worst: { id: RouteId; label: string; href: string; text: string } | null;
	size: {
		/** The committed payload tree at the newest run, or null if unmeasured. */
		bytes: number | null;
		/** That tree against the 1 GB Pages cap. */
		capFraction: number | null;
		/** Megabytes left under the cap. */
		leftMb: number | null;
		/** Published days to the cap, at the cost the whole record measured. */
		daysToCap: number | null;
		/** Published days the runway was measured over. */
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

/** Whole days where there are enough of them to be worth a whole number. */
function days(value: number): string {
	const whole = Math.round(value);
	return whole >= 10 ? whole.toLocaleString('en-GB') : value.toFixed(1);
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

/** How many feeds are resting, and how many are failing without resting yet. */
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

function pipelinesCandidates(
	newest: { date: string; records: RunRecord[] } | null,
	feeds: { rested: number; failed: number }
): Candidate[] {
	const found: Candidate[] = [];
	if (feeds.rested > 0) {
		found.push({ text: `${plural(feeds.rested, 'feed', 'feeds')} resting`, severity: BROKEN });
	}
	if (newest !== null) {
		const verdicts = newest.records.map((run) => health(run, runConfig().success_floor_pct));
		const red = verdicts.filter((v) => v === 'red').length;
		const amber = verdicts.filter((v) => v === 'amber').length;
		if (red > 0) found.push({ text: `${plural(red, 'run', 'runs')} failed`, severity: BROKEN });
		if (amber > 0) {
			found.push({ text: `${plural(amber, 'run', 'runs')} worth a look`, severity: WORTH_A_LOOK });
		}
	}
	if (feeds.failed > 0) {
		found.push({
			text: `${plural(feeds.failed, 'feed', 'feeds')} failing`,
			severity: WORTH_A_LOOK
		});
	}
	return found;
}

function modelCandidates(day: ModelDay | null): Candidate[] {
	if (day === null) return [];
	const found: Candidate[] = [];
	if (day.failed !== null && day.failed > 0) {
		found.push({ text: `${plural(day.failed, 'item', 'items')} failed`, severity: BROKEN });
	}
	// Zero is the expected reading here: at the cap in force no prompt can reach
	// the window, so anything above zero says the cap moved past what fits.
	if (day.refusedForLength !== null && day.refusedForLength > 0) {
		found.push({
			text: `${plural(day.refusedForLength, 'item', 'items')} too long to send`,
			severity: WORTH_A_LOOK
		});
	}
	if (day.notSure !== null && day.notSure > 0) {
		found.push({ text: `${day.notSure} marked "not sure"`, severity: WORTH_A_LOOK });
	}
	if (day.readInPart !== null && day.readInPart > 0) {
		found.push({
			text: `${plural(day.readInPart, 'article', 'articles')} read only in part`,
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
	const itemCeiling = runConfig().safety_ceiling_per_run;
	const budgetBytes = retentionConfig().site_budget_mb * 1024 * 1024;
	const feeds = feedTrouble(feedResults(), collectConfig().quarantine_after_failures);

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
	const worstPipelines = worstOf(pipelinesCandidates(newest, feeds));
	const worstModel = worstOf(modelCandidates(newestModelDay));
	// `$lib/server/runtime-counters.ts` reads the ledger since 2026-08-30, and no
	// panel renders a cell of it - so the honest worst state is that the route
	// exists before its panels do, which is a state a route has to say out loud or
	// nobody knows to come back.
	const worstMachine: Candidate = {
		text: 'no panel reads the counters yet',
		severity: WORTH_KNOWING
	};

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
			label: 'Model',
			href: '/console/model/',
			description: DESCRIPTIONS.model,
			worst: worstModel?.text ?? null,
			severity: worstModel?.severity ?? CLEAR
		},
		{
			id: 'machine',
			label: 'Machine',
			href: '/console/machine/',
			description: DESCRIPTIONS.machine,
			worst: worstMachine.text,
			severity: worstMachine.severity
		}
	];

	const loudest = [...routes]
		.filter((route) => route.worst !== null)
		.sort((a, b) => b.severity - a.severity)[0];

	// --- Site size ---------------------------------------------------------
	// Not windowed, and that is the difference between this and the panel on
	// Pipelines. The band stands on all three routes, so a figure that moved
	// when a control on one route moved would read as three different sites.
	const bytes = newest?.siteBytes ?? null;
	const cost = siteCost(manifests, publishedItems(), null);
	const runway =
		bytes === null ? null : siteRunway(bytes, cost.median, itemCeiling, budgetBytes);
	const capFraction = bytes === null ? null : bytes / PAGES_CAP_BYTES;
	// The level says which tree it measured before it says anything else about
	// it. `site_bytes` is the committed payload tree and the cap is measured on
	// the built site, which is larger - so the share is a floor on the real one,
	// and a percentage printed without that clause is optimistic by a multiple.
	const TREE =
		'That is the committed payload tree, not the published site: the site is larger, it is what the cap measures, and idhazh site-weight prints its runway after every build.';
	const sizeSentence =
		bytes === null
			? 'No run has recorded a size yet, so there is nothing to hold against the 1 GB Pages cap.'
			: runway === null
				? `${mb(bytes)} of the 1 GB Pages cap. ${TREE} No published day grew the tree over an article it published, so there is no rate and no runway.`
				: `${mb(bytes)} of the 1 GB Pages cap. ${TREE} At ${Math.round(cost.median ?? 0).toLocaleString('en-GB')} B an article over ${plural(cost.days.length, 'published day', 'published days')}, ${itemCeiling} articles a day fills it in about ${days(runway.toCap)} more.`;

	// --- The three carries --------------------------------------------------
	// One sentence each, no chart. They are what stops a route hiding the panel
	// that explains another, and every number in them is derived rather than
	// stated: a carry quoting a figure nobody measured is worse than no carry.
	const modelClock = clock(newestModelDay?.totalMs ?? null);
	const runSpread = readSpreadOf(newest?.date ?? null, itemRows);
	const articlesToday = newest === null ? null : (publishedItems().get(newest.date) ?? null);

	return {
		band: {
			verdict: { date: newest?.date ?? null, sentence, health: verdictHealth },
			worst:
				loudest === undefined || loudest.worst === null
					? null
					: { id: loudest.id, label: loudest.label, href: loudest.href, text: loudest.worst },
			size: {
				bytes,
				capFraction,
				leftMb: bytes === null ? null : (PAGES_CAP_BYTES - bytes) / 1024 / 1024,
				daysToCap: runway?.toCap ?? null,
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
