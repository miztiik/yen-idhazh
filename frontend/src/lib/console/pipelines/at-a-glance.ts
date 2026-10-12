/** The two published counts, kept private and shaped at build time. */
import { publishedSkyline } from '../../charts/glance';
import type { ChartDay } from '../../server/chart-days';
import type { TimeWindow } from '../../charts/viewport';

export function atAGlance(days: ChartDay[], window: TimeWindow) {
	return { articles: publishedSkyline(days, window, 'items'), visuals: publishedSkyline(days, window, 'published') };
}
