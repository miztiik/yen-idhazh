
export const prerender = false;
export const ssr = false;

export function load() {
	return {
		console: __CONSOLE_CONFIG__,
		explorer: __EXPLORER_CONFIG__,
		publishedLedgers: __PUBLISHED_LEDGERS__,
		panelGroups: [{ id: 'data-explorer', title: '', panels: ['data-explorer-ask', 'data-explorer-rows'] }]
	};
}
