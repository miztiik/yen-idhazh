/** What ranking weight did the published source view apply to each live feed? */
import { shareMarks, type TargetMarks } from '$lib/charts/targetbar';
import type { SourceHealthView } from '../../server/payload';
import { rankedList } from '../../charts/d3/rankedList';

export interface FeedStanding {
	sourceId: string;
	title: string;
	vertical: string;
	factor: number;
	reads: number;
	onTheFloor: boolean;
	marks: TargetMarks | null;
}

export interface Standing {
	headline: string;
	floor: number;
	windowDays: number;
	feeds: FeedStanding[];
	hidden: number;
	hiddenOnTheFloor: number;
	unmeasured: number;
	counted: number;
	generatedAt: string;
	runId: string;
}

export function standing(view: SourceHealthView | null, rows: number): Standing | null {
	if (view === null || typeof view.reliability_floor !== 'number' || typeof view.reliability_window_days !== 'number') return null;
	const live = view.sources.filter((row) => !row.retired);
	const ranked = live
		.map((row) => ({
			sourceId: row.source_id,
			title: row.title,
			vertical: row.vertical,
			factor: row.reliability,
			reads: row.reliability_reads,
			onTheFloor: row.reliability_reads > 0 && row.reliability <= view.reliability_floor,
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

export function rankingDiscount(view: SourceHealthView | null, cap: number) {
	const snapshot = standing(view, Number.MAX_SAFE_INTEGER);
	if (snapshot === null) return null;
	const discounted = snapshot.feeds.filter((row) => row.reads > 0 && row.factor < 1);
	const drawn = discounted.slice(0, cap);
	const geometry = rankedList(drawn.map((row) => ({
		label: row.sourceId, value: 1 - row.factor,
		context: `${row.reads} evidence-bearing reads; ${row.vertical}`,
		status: row.onTheFloor ? 'on the floor' : undefined
	})), { rules: [{ at: 1 - snapshot.floor, label: 'the most the ranking takes' }] });
	if (geometry) {
		geometry.rows.sort((a, b) => drawn.findIndex((row) => row.sourceId === a.key) - drawn.findIndex((row) => row.sourceId === b.key));
		for (const row of geometry.rows) row.row.value = `${Math.round(row.value * 100)}% discount`;
	}
	return {
		snapshot, geometry,
		lede: `${discounted.length} feeds were discounted by run ${snapshot.runId}.`,
		maxText: geometry ? `${Math.round(geometry.max * 100)}% discount` : '',
		tail: `${Math.max(0, discounted.length - cap)} more discounted, ${discounted.slice(cap).filter((row) => row.onTheFloor).length} on the floor; ${snapshot.feeds.filter((row) => row.reads > 0 && row.factor === 1).length} answered every evidence-bearing read. ${snapshot.unmeasured} unread feeds keep full weight; they were not read in ${snapshot.windowDays} days.`
	};
}
