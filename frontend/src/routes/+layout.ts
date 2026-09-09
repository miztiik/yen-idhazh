import type { UiConfig } from '$lib/server/config';

export const trailingSlash = 'always';

/** The knobs every page draws itself from, and nothing else.
 *
 * **This is a universal load, and that is a decision rather than a style.** A
 * server load is not only a read - it is a promise that a file called
 * `<route>/__data.json` exists, and SvelteKit's client asks a static host for
 * one whenever any node in the branch has a server load. Only a prerendered
 * route has such a file. This layout sits above every route on the site, so
 * keeping its `load` on the server would decide that for all of them: a route
 * that ever stops being prerendered would meet the framework's error screen
 * instead of its own page, over a data file no build ever wrote.
 *
 * The knobs arrive through `__UI_CONFIG__`, which `vite.config.ts` resolves
 * once per build out of the same `uiConfig()` the server reader owns. A
 * universal module may not import `$lib/server/`, and a knob a surface needs is
 * imported into the bundle at build time rather than fetched
 * (`docs/concepts/config.md`). The import below is a type and is erased with
 * the annotation.
 *
 * Whatever this returns is handed to every page beneath it, so **nothing here
 * may come from a day**. One fact about the newest day rewrites the bytes of
 * every older page the next time a day publishes - a page a reader already
 * holds goes stale for a reason that has nothing to do with what it says. The
 * config is what is left, and it moves only when a person edits it.
 */
export function load(): { ui: UiConfig } {
	return { ui: __UI_CONFIG__ };
}
