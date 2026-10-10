import { consoleKnobs, routeConsole } from '$lib/console/route-console';
export const prerender = false;
export const ssr = false;

export function load() {
	return {
		chrome: __EXPLORER_CONFIG__.chrome,
		console: consoleKnobs(),
		explorer: __EXPLORER_CONFIG__,
		publishedLedgers: __PUBLISHED_LEDGERS__,
		frame: __FRAME_CONFIG__,
		docsBase: __UI_CONFIG__.repo_url.replace(/\/+$/, ''),
		panelGroups: routeConsole('data-explorer').panel_groups
	};
}
