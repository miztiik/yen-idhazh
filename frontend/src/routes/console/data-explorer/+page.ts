
export const prerender = false;
export const ssr = false;

export function load() {
	return {
		console: __CONSOLE_CONFIG__,
		explorer: __EXPLORER_CONFIG__,
		publishedLedgers: __PUBLISHED_LEDGERS__,
		frame: __FRAME_CONFIG__,
		docsBase: __UI_CONFIG__.repo_url.replace(/\/+$/, ''),
		panelGroups: [{ id: 'data-explorer', title: '', panels: ['data-explorer-ask', 'data-explorer-rows', 'data-explorer-shape'] }]
	};
}
