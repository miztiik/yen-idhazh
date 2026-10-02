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
	fetchedBytes('/root', (url, init) => fetch(url, init)),
	() => import('../../../src/lib/data/engine').then((engine) => engine.browserEngine(`${location.origin}/ext`))
);

window.explorerAsk = async (options) => {
	if (options.sql.includes('https://example.invalid/x.csv')) {
		void fetch('https://example.invalid/x.csv').catch(() => undefined);
		return Promise.race<AskResult>([
			readAsk(keeper, options, {}),
			new Promise<AskResult>((resolve) => setTimeout(() => resolve({ state: 'refused', because: { kind: 'engine-error', message: 'timed out while the browser refused the external request' } }), 5000))
		]);
	}
	return readAsk(keeper, options, {});
};