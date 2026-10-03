import { fetchedBytes } from '../../../src/lib/data/fetched-bytes';
import { pageKeeper } from '../../../src/lib/data/page-keeper';
import { readAsk } from '../../../src/lib/data/ask-reader';
import type { AskOptions, AskResult } from '../../../src/lib/data/slice-shapes';

declare global {
	interface Window {
		explorerAsk(options: AskOptions): Promise<AskResult>;
	}
}

const keeper = pageKeeper(
	fetchedBytes(__ASSET_BASE_URL__, (url, init) => fetch(url, init)),
	() => import('../../../src/lib/data/engine').then((engine) => engine.browserEngine(new URL('/ext', location.href).href))
);

window.explorerAsk = (options) => readAsk(keeper, options, {});
