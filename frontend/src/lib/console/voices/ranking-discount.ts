/** What ranking weight did the published source view apply to each live feed? */
import { shareMarks, type TargetMarks } from '$lib/charts/targetbar';
import { reliabilityPublished, type SourceHealthView } from '$lib/server/payload';

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
