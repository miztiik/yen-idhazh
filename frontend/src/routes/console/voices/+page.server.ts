/** Which unpublished source decisions and feed reads belong in the built Voices page? */
import { chartConfig, consoleConfig } from '$lib/server/config';
import { windowOfDays } from '$lib/charts/viewport';
import { sourceHealthView } from '$lib/server/payload';
import { feedHealthRows } from '$lib/server/ledger-rows';
import { windowDay } from '$lib/server/window-day';
import { retiring } from '$lib/server/source-retiring';
import { feedInput } from '$lib/console/voices/feeds-failed';

export const prerender = true;
export type { CapPoint, LengthRange, SourceCut, SourceCuts } from '$lib/server/model-work';
export type { FeedDay, FeedDayOutcome, Reliability } from '$lib/feed-health';
export type { YieldDay } from '$lib/server/source-retiring';
export type { FeedStanding, Standing } from '$lib/console/voices/ranking-discount';

export async function load() {
	const knobs = consoleConfig();
	const day = windowDay();
	const view = sourceHealthView();
	const feeds = await feedHealthRows(windowOfDays(day, Math.max(...knobs.window_presets), knobs.today_anchor));
	return {
		sourceView: view,
		retiring: retiring(view, knobs.source_rows),
		feedInput: feedInput(feeds),
		chart: chartConfig()
	};
}
