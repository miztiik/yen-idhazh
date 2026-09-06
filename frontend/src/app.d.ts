/// <reference types="@sveltejs/kit" />

declare global {
	/** Injected by Vite at build time. Never fetched, never read from a file. */
	const __BUILD_COMMIT__: string;
	const __BUILD_DATE__: string;
	/** `visuals.asset_base_url`. Empty means this site, and empty is what ships. */
	const __ASSET_BASE_URL__: string;

	namespace App {}
}

export {};
