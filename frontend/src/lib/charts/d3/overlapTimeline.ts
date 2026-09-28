/** What was happening at the same time: work items as lanes on one real clock.
 *
 * Each item runs its steps back to back from its own start, and every lane is
 * placed on the same span - from the earliest start to the latest end - so two
 * items that overlapped are drawn overlapping. Where the queue is the finding,
 * the peak says how many items were in flight at once.
 *
 * Positions leave as CSS lengths of that span, because
 * `RunTimelinePanel.svelte` draws its lanes as markup, and a timeline is the
 * worst shape there is for a sum: a reader who wants totals wants another type.
 */
import { percentOf } from '../rank';

export interface TimelineInput {
	id: string;
	source: string;
	shard: number;
	/** Epoch milliseconds, UTC. */
	startMs: number;
	steps: readonly { label: string; ms: number }[];
}

export interface PlacedStep {
	label: string;
	startMs: number;
	endMs: number;
	/** From the span's start, as a CSS length. */
	left: string;
	width: string;
}

export interface TimelineLane {
	id: string;
	source: string;
	shard: number;
	startMs: number;
	endMs: number;
	left: string;
	width: string;
	steps: PlacedStep[];
}

export interface TimelineGeometry {
	startMs: number;
	endMs: number;
	/** In shard order, then by start, then by id. */
	lanes: TimelineLane[];
	/** The most items in flight at one instant. */
	peak: number;
}

/** The lanes on one clock, or null where nothing ran for any time at all. */
export function overlapTimeline(items: readonly TimelineInput[]): TimelineGeometry | null {
	const lanes = items.map((item) => {
		if (!Number.isFinite(item.startMs)) throw new RangeError(`"${item.id}" has no start.`);
		let at = item.startMs;
		const steps = item.steps.map((step) => {
			if (!Number.isFinite(step.ms) || step.ms < 0) {
				throw new RangeError(`"${item.id}" has a step "${step.label}" of ${step.ms} ms; a step takes time or none.`);
			}
			const placed = { label: step.label, startMs: at, endMs: at + step.ms };
			at += step.ms;
			return placed;
		});
		return { ...item, endMs: at, steps };
	});
	if (lanes.length === 0) return null;
	const startMs = Math.min(...lanes.map((lane) => lane.startMs));
	const endMs = Math.max(...lanes.map((lane) => lane.endMs));
	const span = endMs - startMs;
	if (span <= 0) return null;
	const share = (ms: number) => percentOf((ms - startMs) / span);
	const length = (ms: number) => percentOf(ms / span);

	// Ends sort before starts at one instant: an item that finished as another
	// began was not in flight beside it.
	const edges = lanes
		.flatMap((lane) => [
			{ at: lane.startMs, change: 1 },
			{ at: lane.endMs, change: -1 }
		])
		.sort((left, right) => left.at - right.at || left.change - right.change);
	let flying = 0;
	let peak = 0;
	for (const edge of edges) {
		flying += edge.change;
		peak = Math.max(peak, flying);
	}

	return {
		startMs,
		endMs,
		lanes: lanes
			.sort(
				(left, right) =>
					left.shard - right.shard ||
					left.startMs - right.startMs ||
					(left.id < right.id ? -1 : left.id > right.id ? 1 : 0)
			)
			.map((lane) => ({
				id: lane.id,
				source: lane.source,
				shard: lane.shard,
				startMs: lane.startMs,
				endMs: lane.endMs,
				left: share(lane.startMs),
				width: length(lane.endMs - lane.startMs),
				steps: lane.steps.map((step) => ({
					...step,
					left: share(step.startMs),
					width: length(step.endMs - step.startMs)
				}))
			})),
		peak
	};
}
