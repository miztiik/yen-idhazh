/// <reference types="@sveltejs/kit" />

declare global {
	/** `visuals.asset_base_url`. Empty means this site, and empty is what ships. */
	const __ASSET_BASE_URL__: string;

	/** What `uiConfig()` resolved at build time, injected by `vite.config.ts`.
	 *
	 * The root layout is a universal load, so it cannot open `config/` itself -
	 * see the note beside the definition. */
	const __UI_CONFIG__: import('$lib/server/config').UiConfig;

	/** The encoder's failover leg, injected by `vite.config.ts` from `config/`.
	 *
	 * Our own origin is primary. Every field is empty or zero when the block is
	 * incomplete, and `baseUrl === ''` means there is no second origin at all. */
	const __ENCODER_SOURCE__: {
		baseUrl: string;
		cdnOrigins: string[];
		revision: string;
		digests: Record<string, string>;
		deadlineMs: number;
	};

	namespace App {}
}

export {};
