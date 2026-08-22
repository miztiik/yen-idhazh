/// <reference types="@sveltejs/kit" />

declare global {
	/** Injected by Vite at build time. Never fetched, never read from a file. */
	const __BUILD_COMMIT__: string;
	const __BUILD_DATE__: string;

	namespace App {}
}

export {};
