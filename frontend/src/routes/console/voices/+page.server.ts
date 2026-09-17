import { chartConfig, collectConfig, consoleConfig } from '$lib/server/config';
import {
	feedResults,
	reliabilityPublished,
	shardDays,
	sourceHealthView,
	itemHealthRows,
	type DayYield,
	type FeedResult,
	type SourceHealthRow,
	type SourceHealthView
} from '$lib/server/payload';
import { sourceCuts, SOURCE_CUT_ROWS } from '$lib/server/model-work';
import {
	chronological,
	failing,
	feedDays,
	reliability,
	resting,
	resultLabel,
	skipped,
	streak,
	type FeedDay,
	type FeedDayOutcome,
	type Reliability
} from '$lib/feed-health';
import { percentOf } from '$lib/charts/rank';
import { shortDate } from '$lib/format';
import { targetGeometry, targetMarks, type TargetMarks } from '$lib/charts/targetbar';

export const prerender = true;

// The page prints these; the derivation is server-only, so the shape crosses as
// a type and the ledger reader never reaches a browser bundle.
export type { CapPoint, LengthRange, SourceCut, SourceCuts } from '$lib/server/model-work';
export type { FeedDay, FeedDayOutcome, Reliability };

/** The bar for a share that is already bounded at 1.0.
 *
 * `targetMarks` sizes its own track to `max(value, target) * 1.15`, which is
 * right for a measure with no ceiling - a failure count has no natural full -
 * and wrong here. This factor cannot exceed 1.0, so the track IS 1.0: a full
 * bar means a feed the ranker did not discount, and two feeds' bars can be read
 * against each other because they are drawn to the same scale. An auto-sized
 * track would give a feed at 1.0 and a feed at 0.5 the same 87 percent fill.
 *
 * The band and the sense come from `targetGeometry` rather than from a second
 * rule written here, so the colour a bar takes and the colour a delta on the
 * same figure takes cannot disagree.
 */
function shareMarks(factor: number, floor: number): TargetMarks {
	const geometry = targetGeometry(factor, floor, 'higher-is-better');
	return {
		...geometry,
		track: 1,
		valueFraction: factor,
		markerFraction: floor,
		valuePercent: percentOf(factor),
		markerPercent: percentOf(floor)
	};
}

/** One feed's standing with the ranker, as the page draws it.
 *
 * `factor` is what the run applied and `reads` is what it was reduced over.
 * They travel together because a factor with no denominator is not a
 * measurement: a feed nobody asked scores the same 1.0 as a feed that never
 * missed, and the page has to be able to tell those apart.
 *
 * `marks` is computed here rather than in the browser, so the bar is on the
 * page before any script runs - the same trade the feed-failure bars take.
 */
export interface FeedStanding {
	sourceId: string;
	title: string;
	vertical: string;
	/** The multiplier, in the range the floor and 1.0 bound. */
	factor: number;
	/** Evidence-bearing reads behind it. Zero means the factor is a default. */
	reads: number;
	/** True when the ranker has taken this feed as far down as it goes. */
	onTheFloor: boolean;
	/** Null where `reads` is zero - there is no bar to draw over no evidence. */
	marks: TargetMarks | null;
}

/** What the ranking did about the record, ready to draw. */
export interface Standing {
	headline: string;
	floor: number;
	windowDays: number;
	/** Worst first, then by id, so two builds over one view draw one order. */
	feeds: FeedStanding[];
	/** Feeds the row cap left out, and how many of those are on the floor. */
	hidden: number;
	hiddenOnTheFloor: number;
	/** Feeds with no evidence behind their factor, over how many were counted. */
	unmeasured: number;
	counted: number;
	generatedAt: string;
	runId: string;
}

/** The ranking factor per feed, from the view the pipeline published.
 *
 * Read and never re-derived. `ledger.feed_reliability` reduced these rows when
 * the run happened; reducing them again in a page would be a second answer to
 * one question, and the day the two disagreed neither would be worth drawing
 * (`docs/architecture/sources/health.md`).
 *
 * Retired addresses are left out. Their factor is whatever the window still
 * holds from before we stopped asking, so drawing it would put a bar on a feed
 * no run will ever ask again.
 *
 * **Null for a view written before the reliability fields existed**, which is
 * the read-side migration this panel owes (`CLAUDE.md` section 11). A view the
 * pipeline wrote yesterday carries no `reliability`, no `reliability_reads`, no
 * floor, no window and no headline; the page has to draw its named absence for
 * that rather than die, and a build that dies takes the census and the failure
 * list down with it. It is one guard rather than five optional fields because
 * the five arrived together and no run can write a subset of them.
 *
 * Not exported. SvelteKit allows a `+page.server.ts` to export `load` and a
 * short list of options and nothing else, so an exported helper here fails the
 * build rather than a lint - which is what took `site`, `browser` and
 * `whole-day` red on this branch. The route next door keeps `sourceHealth` the
 * same way.
 */
function standing(view: SourceHealthView | null, rows: number): Standing | null {
	if (view === null || !reliabilityPublished(view)) return null;
	const live = view.sources.filter((row) => !row.retired);
	const ranked = live
		.map((row) => ({
			sourceId: row.source_id,
			title: row.title,
			vertical: row.vertical,
			factor: row.reliability,
			reads: row.reliability_reads,
			onTheFloor: row.reliability_reads > 0 && row.reliability <= view.reliability_floor,
			// Higher is better here, so the fill runs from nothing up to 1.0 and the
			// mark sits on the floor the ranker will not discount past.
			marks: row.reliability_reads > 0 ? shareMarks(row.reliability, view.reliability_floor) : null
		}))
		.sort(
			(a, b) =>
				a.factor - b.factor || b.reads - a.reads || a.sourceId.localeCompare(b.sourceId)
		);
	const drawn = ranked.slice(0, rows);
	const hidden = ranked.slice(drawn.length);
	return {
		headline: view.headline_sentence,
		floor: view.reliability_floor,
		windowDays: view.reliability_window_days,
		feeds: drawn,
		hidden: hidden.length,
		hiddenOnTheFloor: hidden.filter((feed) => feed.onTheFloor).length,
		unmeasured: ranked.filter((feed) => feed.reads === 0).length,
		counted: ranked.length,
		generatedAt: view.generated_at,
		runId: view.run_id
	};
}

/** One feed the pipeline is having trouble reading, and how near a rest it is. */
export interface FeedTrouble {
	feedId: string;
	attempts: number;
	failures: number;
	/** Failures in a row, ending at the newest read. This is the number the
	 * pipeline quarantines on, so it is the number the page prints. */
	streak: number;
	lastResult: string;
	lastDetail: string;
	lastDate: string;
	/** The pipeline's own decision, recomputed by its own rule. */
	resting: boolean;
	/** Where the fill ends and where the rest threshold sits. Drawn here, so the
	 * bar is on the page before any script runs and the browser never has to
	 * agree with it. */
	marks: TargetMarks;
	/** One entry per day this feed has a record on, oldest first. */
	days: FeedDay[];
}

/** One state, how many sources are in it, and what it costs while it holds.
 *
 * `id` is the address a test and a stylesheet use; `label` is the words. The
 * two are deliberately different strings: a label may change where an address
 * may not (`docs/concepts/ui-shell.md`).
 */
export interface SourceFact {
	id: string;
	label: string;
	count: number;
	/** What the reader loses while this state holds, or null where the state
	 * costs nothing. Every automatic state that withholds a source says so -
	 * that is the whole reason the four facts are drawn separately rather than
	 * averaged into a score. */
	withheld: string | null;
}

/** One source the pipeline is not reading normally, and why. */
export interface SourceNote {
	sourceId: string;
	title: string;
	vertical: string;
	permission: string;
	availability: string;
	retired: boolean;
	retiredOn: string | null;
	opportunities: number;
	publications: number;
	sourceFailures: number;
	withheld: string;
}

/** The four facts about every address a run may ask, as the page draws them. */
export interface SourceHealth {
	sources: number;
	permission: SourceFact[];
	availability: SourceFact[];
	retired: number;
	/** Sources held back right now by any of the four - the number an operator
	 * acts on, and the one the clean census does not contain. */
	withheld: number;
	notes: SourceNote[];
	hidden: number;
	record: {
		completeDates: number;
		minCompleteDays: number;
		readable: boolean;
		firstDate: string | null;
		lastDate: string | null;
		opportunities: number;
		publications: number;
		sourceFailures: number;
	};
	generatedAt: string;
	runId: string;
}

/** What a permission state means, and what it withholds while it holds.
 *
 * `unrecorded` withholds nothing: the run asked the address anyway, because an
 * empty cell is a check nobody has run rather than a refusal. Reading it as a
 * refusal would take every desk under its feed floor on the day the column
 * landed (`docs/architecture/sources/health.md`).
 */
const PERMISSION_FACTS: { id: string; label: string; withheld: string | null }[] = [
	{ id: 'allowed', label: 'the site allows us', withheld: null },
	{
		id: 'denied',
		label: 'the site refuses us',
		withheld: 'nothing from it reaches the digest until a later run reads its rules again'
	},
	{
		id: 'unreachable',
		label: 'we could not read its rules',
		withheld: 'the address is not asked at all until a later run establishes permission'
	},
	{ id: 'unrecorded', label: 'no run has recorded an answer', withheld: null }
];

/** What an availability state means, and what it withholds.
 *
 * The rest's own sentence is completed on the page, where the configured retry
 * count is in hand - a literal here would print yesterday's rule after somebody
 * moved the knob.
 */
const AVAILABILITY_FACTS: { id: string; label: string; withheld: string | null }[] = [
	{ id: 'answering', label: 'answering with articles', withheld: null },
	{
		id: 'failing',
		label: 'its last read failed',
		withheld: 'the digest is short of what it carries until it answers again'
	},
	{
		id: 'resting',
		label: 'resting after repeated failures',
		withheld: 'nothing it carries reaches the digest until the run asks it again'
	},
	{
		id: 'never_asked',
		label: 'unread in this record',
		withheld: 'nothing from it is reaching the digest'
	}
];

/** Loudest first, so a capped list drops the states that fix themselves. */
const NOTE_ORDER: Record<string, number> = {
	retired: 5,
	denied: 4,
	unreachable: 3,
	never_asked: 2,
	resting: 1,
	failing: 0
};

function tally(
	facts: { id: string; label: string; withheld: string | null }[],
	states: string[]
): SourceFact[] {
	return facts.map((fact) => ({
		...fact,
		count: states.filter((state) => state === fact.id).length
	}));
}

/** The four facts, from the view the pipeline published and from nothing else.
 *
 * Permission, availability and retirement are the backend's decisions rendered
 * as they were written. Re-deriving any of them here would be a second reducer
 * over the same evidence, and two reducers are two answers.
 */
function sourceHealth(view: SourceHealthView | null, rows: number): SourceHealth | null {
	if (view === null) return null;
	const sources = view.sources;
	const permission = tally(
		PERMISSION_FACTS,
		sources.map((row) => row.permission)
	);
	const availability = tally(
		AVAILABILITY_FACTS,
		sources.map((row) => row.availability)
	);
	const reasonFor = (row: SourceHealthRow): string | null => {
		if (row.retired) return 'retired';
		if (row.permission === 'denied' || row.permission === 'unreachable') return row.permission;
		if (row.availability !== 'answering') return row.availability;
		return null;
	};
	const held = sources
		.map((row) => ({ row, reason: reasonFor(row) }))
		.filter((entry): entry is { row: SourceHealthRow; reason: string } => entry.reason !== null)
		.sort(
			(a, b) =>
				(NOTE_ORDER[b.reason] ?? 0) - (NOTE_ORDER[a.reason] ?? 0) ||
				a.row.source_id.localeCompare(b.row.source_id)
		);
	const withheldFor = (reason: string): string =>
		reason === 'retired'
			? 'no run asks this address again until its configured address changes'
			: ([...PERMISSION_FACTS, ...AVAILABILITY_FACTS].find((fact) => fact.id === reason)
					?.withheld ?? 'nothing it carries reaches the digest');
	return {
		sources: sources.length,
		permission,
		availability,
		retired: sources.filter((row) => row.retired).length,
		withheld: held.length,
		notes: held.slice(0, rows).map(({ row, reason }) => ({
			sourceId: row.source_id,
			title: row.title,
			vertical: row.vertical,
			permission: row.permission,
			availability: row.availability,
			retired: row.retired,
			retiredOn: row.retired_on,
			opportunities: row.opportunities,
			publications: row.publications,
			sourceFailures: row.source_failures,
			withheld: withheldFor(reason)
		})),
		hidden: Math.max(0, held.length - rows),
		record: {
			completeDates: view.complete_dates,
			minCompleteDays: view.min_complete_days,
			readable: view.yield_readable,
			firstDate: view.first_date,
			lastDate: view.last_date,
			opportunities: sources.reduce((total, row) => total + row.opportunities, 0),
			publications: sources.reduce((total, row) => total + row.publications, 0),
			sourceFailures: sources.reduce((total, row) => total + row.source_failures, 0)
		},
		generatedAt: view.generated_at,
		runId: view.run_id
	};
}

/** Every feed that failed at least once, closest to a rest first.
 *
 * A feed with a clean record is not listed. The operator came here to find what
 * is broken, and a list that names all seventy sources hides the four that are.
 *
 * Ranked by how near the rest is, then by how much has gone wrong in total. A
 * feed four failures into a five-failure rule is one run from being dropped; a
 * feed with twelve failures spread over a month and answering today is not, and
 * a total-failure sort put the second one on top.
 *
 * `rows` is already one row per feed per run - `feedResults` settles the ledger
 * once - so a run a second attempt wrote twice is counted once here.
 */
function trouble(rows: FeedResult[], quarantineAfter: number): FeedTrouble[] {
	const byFeed = new Map<string, FeedResult[]>();
	for (const row of rows) {
		byFeed.set(row.feedId, [...(byFeed.get(row.feedId) ?? []), row]);
	}

	const found: FeedTrouble[] = [];
	for (const [feedId, group] of byFeed) {
		// A skipped feed was never asked, so it can neither pass nor fail. It still
		// has to stay in `ordered`, because the rest it records is what lets the
		// quarantine lift.
		const ordered = chronological(group);
		const asked = ordered.filter((row) => !skipped(row));
		const failures = asked.filter(failing);
		if (failures.length === 0) continue;
		const newest = asked.at(-1) as FeedResult;
		const inARow = streak(ordered);
		found.push({
			feedId,
			attempts: asked.length,
			failures: failures.length,
			streak: inARow,
			lastResult: resultLabel(newest),
			lastDetail: newest.detail,
			lastDate: newest.date,
			resting: resting(ordered, quarantineAfter),
			// Fewer is better, so the fill runs from nothing to the rest and past it.
			marks: targetMarks(inARow, quarantineAfter, 'lower-is-better'),
			days: feedDays(ordered)
		});
	}
	return found.sort(
		(a, b) => b.streak - a.streak || b.failures - a.failures || a.feedId.localeCompare(b.feedId)
	);
}

/** Everything the console knows about who supplied the day.
 *
 * The census, the ranking factor, the failure record and what the truncation cap
 * cost each source were four panels on `/console/` until 2026-09-14. They are
 * one route now because they answer one question, and the Pipelines route kept
 * none of them: a reader asking which feed is broken should not have to know
 * that half the answer is filed under "did the runs work".
 *
 * Two reads walk the day tree, both bounded by the widest span the control can
 * reach rather than by what the archive has accumulated (`CLAUDE.md`
 * Guardrail #12). The ranking factor is not one of them: it is read from the
 * projection the run published.
 */
/** What one square on a reliability strip says. Colour is never the only signal:
 * each of these has a sentence on the square's own label. */
export type YieldDay = 'at-or-above' | 'under' | 'nothing';

/** One day of one source's share, as a square. */
export interface YieldSquare {
	date: string;
	state: YieldDay;
	label: string;
}

/** One source counting down to retiring itself, as the panel draws it. */
export interface Countdown {
	sourceId: string;
	title: string;
	/** The trailing share, or null where the source decided nothing at all. */
	share: number | null;
	publications: number;
	decisions: number;
	opportunities: number;
	/** The bar. Sized here rather than in the browser, so it is on the page
	 * before any script runs - the same trade the feed-failure bars take. */
	marks: TargetMarks;
	daysUnder: number;
	retiresOn: string | null;
	/** Days left on a live dwell, or null where none is running. Derived from the
	 * run's own count and never from a clock. */
	daysLeft: number | null;
	retired: boolean;
	/** True while the source has not met both evidence floors. It is still drawn,
	 * in a block below the ranked rows: hiding it would hide the shape. */
	unjudged: boolean;
	squares: YieldSquare[];
}

/** The reliability strip, as `/console/voices/` reads it. */
export interface Retiring {
	alarmPoint: number;
	minDecisions: number;
	minCompleteDays: number;
	completeDates: number;
	dwellDays: number;
	autoRetire: boolean;
	dates: string[];
	/** Ranked nearest-to-retirement first, then by how far under the mark. */
	rows: Countdown[];
	/** Under one or both evidence floors, so no countdown may be drawn yet. */
	unjudged: Countdown[];
	/** How many judged sources are at or above the mark today. */
	clear: number;
	/** Rows the cap dropped. A ranking is read from the top and its tail is a
	 * number, never another page of rows. */
	hidden: number;
	generatedAt: string;
	runId: string;
}

/** The share a source turned into a story, or null where it decided nothing.
 *
 * `null` rather than 0 for a source nobody has asked: 0 of 0 is not zero, and a
 * page that prints 0 percent for it makes an accusation the record cannot
 * support. The same rule `SourceHealthRow.source_yield` applies in Python.
 */
function shareOf(publications: number, decisions: number): number | null {
	return decisions > 0 ? publications / decisions : null;
}

/** One day's square, with the sentence that says what it means without colour. */
function squareFor(day: DayYield, alarmPoint: number): YieldSquare {
	const decisions = day.publications + day.source_failures;
	const share = shareOf(day.publications, decisions);
	if (share === null) {
		return {
			date: day.date,
			state: 'nothing',
			label: `${shortDate(day.date)}: it decided nothing, so there is no share.`
		};
	}
	const state: YieldDay = share >= alarmPoint ? 'at-or-above' : 'under';
	const wording = state === 'under' ? 'under the mark' : 'at or above the mark';
	return {
		date: day.date,
		state,
		label: `${shortDate(day.date)}: ${day.publications} of ${decisions} read, ${percentOf(
			share
		)} - ${wording}.`
	};
}

/** Every source's countdown, ranked nearest to retiring first.
 *
 * **Nothing here re-derives the dwell.** The run counted the unbroken run of
 * under-the-mark days and named the day it completes, over the same evidence
 * this strip draws, so a person watching `retires in 2 days` sees the number
 * that will fire rather than a second opinion about it.
 *
 * The bar's track is the full 0 to 100 percent share and the marker sits at the
 * alarm point on every row. A per-row maximum would put the marker at a
 * different x on each row, and the whole reason to stack these is that a column
 * means the same thing all the way down.
 */
function retiring(view: SourceHealthView | null, rows: number): Retiring | null {
	if (view === null) return null;
	const alarmPoint = view.yield_alarm_point ?? 0.5;
	const minDecisions = view.yield_alarm_min_decisions ?? 30;
	const dwellDays = view.dwell_days ?? 14;
	const dates = view.dwell_dates ?? [];
	const deepEnough = view.complete_dates >= view.min_complete_days;

	const drawn = view.sources
		.filter((row) => !row.retired || row.retired_on !== null)
		.map((row): Countdown => {
			const decisions = row.publications + row.source_failures;
			const share = shareOf(row.publications, decisions);
			const daysUnder = row.days_under_the_mark ?? 0;
			const retiresOn = row.retires_on ?? null;
			return {
				sourceId: row.source_id,
				title: row.title,
				share,
				publications: row.publications,
				decisions,
				opportunities: row.opportunities,
				marks: shareMarks(share ?? 0, alarmPoint),
				daysUnder,
				retiresOn,
				daysLeft: retiresOn === null ? null : Math.max(dwellDays - daysUnder, 0),
				retired: row.retired,
				unjudged: !deepEnough || decisions < minDecisions,
				squares: (row.recent_days ?? []).map((day) => squareFor(day, alarmPoint))
			};
		});

	const judged = drawn.filter((row) => !row.unjudged);
	const under = judged
		.filter((row) => row.daysUnder > 0 || row.retired)
		.sort(
			(a, b) =>
				(a.daysLeft ?? 0) - (b.daysLeft ?? 0) ||
				(a.share ?? 1) - (b.share ?? 1) ||
				a.sourceId.localeCompare(b.sourceId)
		);
	return {
		alarmPoint,
		minDecisions,
		minCompleteDays: view.min_complete_days,
		completeDates: view.complete_dates,
		dwellDays,
		autoRetire: view.auto_retire ?? false,
		dates,
		rows: under.slice(0, rows),
		unjudged: drawn
			.filter((row) => row.unjudged)
			.sort((a, b) => a.sourceId.localeCompare(b.sourceId)),
		clear: judged.length - under.length,
		hidden: Math.max(under.length - rows, 0),
		generatedAt: view.generated_at,
		runId: view.run_id
	};
}

export async function load() {
	const console = consoleConfig();
	// The widest span the control offers. Nothing older than this can be drawn
	// whatever the operator picks, so one read at this width covers every preset.
	const widest = Math.max(...console.window_presets);
	const days = shardDays(widest);
	const itemRows = itemHealthRows(days).rows;
	const quarantineAfter = collectConfig().availability_strikes_before_rest;
	const results = feedResults(days);
	const troubled = trouble(results, quarantineAfter);
	// Capped here rather than in the browser: this list is inlined into the
	// prerendered document, so the rows the cap drops cost the page nothing.
	const feeds = troubled.slice(0, console.feed_rows);
	const hidden = troubled.slice(feeds.length);
	// Read once. Two panels draw from it and a second read would let them draw
	// two different runs if a run landed between them.
	const view = sourceHealthView();
	return {
		// Null when no run has written the view, when it cannot be read, or when the
		// run that wrote it predates the ranking factor. The page draws a named
		// absence for all three rather than a section that is simply missing.
		standing: standing(view, console.source_rows),
		// Permission, availability, retirement and the publishing record, read from
		// the projection the pipeline published rather than re-derived here.
		sourceHealth: sourceHealth(view, console.source_rows),
		// The reliability strip: one row per source close to retiring itself, with
		// its trailing share against the alarm point and one square a day beneath.
		// Read from the same view, so the dwell drawn here and the retirement the
		// run would file cannot disagree.
		retiring: retiring(view, console.source_rows),
		feeds,
		// What the cap left out, as a count and a sum. A ranking is read from the
		// top and its tail is a number, never another page of rows.
		feedsHidden: hidden.length,
		feedsHiddenFailures: hidden.reduce((total, feed) => total + feed.failures, 0),
		// How many feeds did not fail, out of how many were asked, over how many
		// runs. A count with no denominator is not a reliability record.
		feedRecord: reliability(results),
		// One date axis for every feed's strip, so two rows can be read against each
		// other. A per-feed axis would put each strip on its own days, and "broken
		// since Tuesday" and "flaky all month" would draw the same picture.
		feedDates: [...new Set(results.map((row) => row.date))].sort(),
		quarantineAfter,
		// Ten rows and the two sentences under them, aggregated here rather than in
		// the browser. A window of the ledger is thousands of rows and this page
		// inlines whatever it is given, so the ten rows cross and the rows they were
		// made from do not.
		//
		// One table per preset, because the section follows the page's window and the
		// browser has no ledger to re-aggregate. Four tables of ten rows is cheaper
		// than one fetch, and it keeps the section working with no script at all.
		sourceCutsByWindow: console.window_presets.map((days) =>
			sourceCuts(itemRows, {
				days,
				limit: SOURCE_CUT_ROWS
			})
		),
		console,
		// How a chart labels its axis. The feed strip's date axis reads it, and an
		// operator moves it without editing a component.
		chart: chartConfig(),
		today: new Date().toISOString().slice(0, 10)
	};
}
