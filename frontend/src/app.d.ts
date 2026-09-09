/// <reference types="@sveltejs/kit" />

declare global {
	/** `visuals.asset_base_url`. Empty means this site, and empty is what ships. */
	const __ASSET_BASE_URL__: string;

	namespace App {}
}

export {};
