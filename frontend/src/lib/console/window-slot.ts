/** Which window the console's days control is holding, handed up by the route
 * under the layout that draws it.
 *
 * The control stands in the layout, beside the tabs every route shares, but the
 * window belongs to the route: each one keeps its own span, fetches its own
 * files and prices its own presets. So the route fills this slot and the layout
 * reads it, and neither reaches into the other's state.
 *
 * **Until a route has filled it, the layout draws the configured window.** The
 * layout's markup is written before the route's script has run, so the
 * prerendered control is drawn from `console.window_presets` and
 * `console.default_window_days` alone. It is disabled then, which it is until a
 * browser runs the page in any case.
 */
import { getContext, onDestroy, setContext } from 'svelte';

/** What the control reads off the route under it.
 *
 * Getters rather than values, so the control follows the route's own state for
 * as long as the route is on the page instead of a copy taken when it opened.
 */
export interface WindowSource {
	readonly days: number;
	readonly presets: readonly number[];
	/** True while the route is fetching what the window reaches into. */
	readonly busy: boolean;
	/** False until a browser has run the route. */
	readonly ready: boolean;
	/** Sentence this route wants under the band instead of the default window sentence. */
	readonly statusLine?: string | null;
	/** Month files a preset would fetch that the route does not hold yet. */
	monthsFor(days: number): number;
	onChange(days: number): void;
}

/** Where the layout keeps the source it is drawing. */
export interface WindowSlot {
	fill(source: WindowSource): void;
	/** Empty the slot, but only if it still holds this source. */
	clear(source: WindowSource): void;
}

const SLOT = Symbol('console-window');

/** Open the slot. The layout calls this once, while it initialises. */
export function provideWindowSlot(slot: WindowSlot): void {
	setContext(SLOT, slot);
}

/** Hand the route's window to the layout, for as long as the route is mounted.
 *
 * A move between routes mounts the next route and destroys the last, and the
 * order of those two is not promised - which is why `clear` names the source
 * it is clearing, so the last route cannot empty a slot the next one filled.
 */
export function fillWindowSlot(source: WindowSource): void {
	const slot = getContext<WindowSlot | undefined>(SLOT);
	if (slot === undefined) return;
	slot.fill(source);
	onDestroy(() => slot.clear(source));
}
