/** Published payload bytes per article require two measured manifest sizes. */
import { siteCost as measuredCost, sizeGain as measuredGain } from '../../charts/glance';
import type { RunSummary } from '../../server/payload';
import { daysInWindow, type TimeWindow } from '../../charts/viewport';
export { publishingHorizon } from '../../charts/glance';

function measured(value: unknown): value is number {
	return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

export function newestSize(manifests: readonly RunSummary[]): number | null {
	const value = [...manifests].sort((a, b) => a.date.localeCompare(b.date)).at(-1)?.siteBytes;
	return measured(value) ? value : null;
}

export function siteCost(...[manifests, articles, window]: Parameters<typeof measuredCost>) {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date));
	const paired = new Map(ordered.flatMap((day, index) => {
		const count = articles.get(day.date);
		return index > 0 && measured(day.siteBytes) && measured(ordered[index - 1].siteBytes) &&
			typeof count === 'number' && Number.isFinite(count) && count > 0 ? [[day.date, count] as const] : [];
	}));
	return measuredCost(manifests, paired, window);
}

export function sizeGain(manifests: readonly RunSummary[]) {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date));
	return measured(ordered[0]?.siteBytes) && measured(ordered.at(-1)?.siteBytes) ? measuredGain(ordered) : null;
}

export function siteCostPoints(cost: ReturnType<typeof siteCost>, window: TimeWindow) {
	const measured = new Map(cost.days.map((day) => [day.date, day.bytesPerItem]));
	return daysInWindow(window).map((date) => {
		const value = measured.get(date);
		return { date, value: value === undefined || value < 0 ? null : value };
	});
}
