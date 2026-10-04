/// <reference types="@sveltejs/kit" />

declare global {
	/** `visuals.asset_base_url`. Empty means this site, and empty is what ships. */
	const __ASSET_BASE_URL__: string;

	/** What `uiConfig()` resolved at build time, injected by `vite.config.ts`.
	 *
	 * The root layout is a universal load, so it cannot open `config/` itself -
	 * see the note beside the definition. */
	const __UI_CONFIG__: import('$lib/server/config').UiConfig;

	/** What `assistConfig()` resolved at build time, injected by `vite.config.ts`.
	 *
	 * The reading routes search on the reader's own device and have no server
	 * load to read it - see the note beside the definition. */
	const __ASSIST_CONFIG__: import('$lib/server/config').AssistConfig;

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

	/** `ledger.engine_extension_repository`: where the query engine downloads its add-ons. */
	const __ENGINE_EXTENSION_REPOSITORY__: string;

	/** The newest staged raw day listing per ledger. */
	const __RAW_LISTED_THROUGH__: Partial<Record<string, string>>;

	/** `icons.stroke_px`: the icon line width in screen pixels. */
	const __ICON_STROKE_PX__: number;

	namespace App {}
}

export {};
