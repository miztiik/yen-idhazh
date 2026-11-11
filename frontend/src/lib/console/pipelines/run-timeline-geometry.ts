/** How do recorded shard windows and cumulative costs occupy two independent axes? */
import { scaleLinear } from 'd3-scale';
import { percentOf } from '../../charts/rank';
import { thinLabels, tickAnchor, type ChartLabels } from '../../charts/frame';
import type { RunTimelineView, TimelineShard, TimelineItem } from './run-timeline';

export type TimelineMeasure = 'elapsed' | 'work';
export type TimelineOrder = 'cost' | 'start';

export function timelineItems(items: readonly TimelineItem[], order: TimelineOrder): TimelineItem[] {
	const value = (item: TimelineItem) => order === 'cost' ? item.workMs : item.startMs;
	return [...items].sort((a, b) => {
		const left = value(a), right = value(b);
		if (left === null || right === null) return Number(left === null) - Number(right === null) || a.itemId.localeCompare(b.itemId);
		return (order === 'cost' ? right - left : left - right) || a.itemId.localeCompare(b.itemId);
	});
}

export function timelineGeometry(
	view: RunTimelineView, measure: TimelineMeasure, tickDensity: number,
	width: number, labels: ChartLabels, format: (ms: number) => string
) {
	const value = (shard: TimelineShard) => measure === 'elapsed' ? shard.elapsedMs : shard.workMs;
	const ordered = [...view.shards].sort((a, b) => {
		const left = value(a), right = value(b);
		if (left === null || right === null) return Number(left === null) - Number(right === null) || a.shard - b.shard;
		return right - left || a.shard - b.shard;
	});
	const costs = ordered.flatMap((shard) => shard.workMs === null ? [] : [shard.workMs]);
	const domainMs = measure === 'elapsed' ? view.spanMs : costs.length === 0 ? null : Math.max(...costs);
	const scale = scaleLinear().domain([0, domainMs ?? 0]).range([0, 1]);
	const positions = domainMs === null ? [] : domainMs === 0 ? [0]
		: [...new Set([0, ...scale.ticks(tickDensity), domainMs])].sort((a, b) => a - b);
	const ticks = positions.map((ms, index) => ({
		ms, at: percentOf(domainMs === 0 ? 0 : scale(ms)), text: format(ms),
		x: domainMs === 0 ? 0 : scale(ms) * width, anchor: tickAnchor(index, positions.length)
	}));
	const visible = new Set(thinLabels(ticks.map((tick) => ({ ...tick, text: tick.text })), labels).map((tick) => tick.x));
	return {
		domainMs, ticks: ticks.map((tick) => ({ ...tick, text: visible.has(tick.x) ? tick.text : '' })),
		bars: ordered.map((shard) => {
			const ms = value(shard);
			const offsetMs = measure === 'elapsed' && shard.startMs !== null && view.startMs !== null
				? shard.startMs - view.startMs : 0;
			return {
				shard, ms, offsetMs,
				offset: percentOf(domainMs === null || domainMs === 0 ? 0 : scale(offsetMs)),
				width: percentOf(ms === null || domainMs === null || domainMs === 0 ? 0 : scale(ms))
			};
		})
	};
}
