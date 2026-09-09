/// <reference types="@sveltejs/kit" />

declare global {
	/** `visuals.asset_base_url`. Empty means this site, and empty is what ships. */
	const __ASSET_BASE_URL__: string;

	/** What `uiConfig()` resolved at build time, injected by `vite.config.ts`.
	 *
	 * The root layout is a universal load, so it cannot open `config/` itself -
	 * see the note beside the definition. */
	const __UI_CONFIG__: import('$lib/server/config').UiConfig;

	namespace App {}
}

export {};
