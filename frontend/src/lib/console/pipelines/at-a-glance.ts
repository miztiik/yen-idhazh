/** The two published counts, kept private and shaped at build time. */
import { publishedSkyline } from '../../charts/glance';
import type { ChartDay } from '../../server/chart-days';
import type { TimeWindow } from '../../charts/viewport';

export function atAGlance(days: ChartDay[], window: TimeWindow, publishedItems: Readonly<Record<string, number>>) {
	const measured = days.filter((day) => Object.hasOwn(publishedItems, day.date));
	return { articles: publishedSkyline(measured, window, 'items'), visuals: publishedSkyline(measured, window, 'published') };
}
