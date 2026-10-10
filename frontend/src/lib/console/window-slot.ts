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
import type { RecordWindow } from './waiting';

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
	readonly record?: RecordWindow | null;
	/** Month files a preset would fetch that the route does not hold yet. */
	monthsFor(days: number): number;
	onChange(days: number): void;
}

/** Where a route hands its window. */
interface WindowSlot {
	fill(source: WindowSource): void;
	/** Empty the slot, but only if it still holds this source. */
	clear(source: WindowSource): void;
}

const SLOT = Symbol('console-window');

/** Open the slot. The layout calls this once, while it initialises, and draws
 * whatever `show` hands it: the window of the route that holds the slot, or
 * null once no route does.
 *
 * **Which route holds the slot is kept here, in a plain variable, and never in
 * the layout's state.** A move between routes with no page load, such as a tab
 * click, mounts the next route and tears the last one down in the same update.
 * When the next route's `fill` comes first, the last route's `clear` runs as a
 * teardown after it, and Svelte answers a teardown's read of state that changed
 * in that update with the value from before it. So a check against the layout's
 * state saw the last route still holding the slot and emptied it: the control
 * fell back to the configured window, disabled, above panels that drew the
 * stored one. A plain variable is read as it is, in either order.
 */
export function provideWindowSlot(show: (source: WindowSource | null) => void): void {
	let holder: WindowSource | null = null;
	setContext<WindowSlot>(SLOT, {
		fill(source) {
			holder = source;
			show(source);
		},
		clear(source) {
			if (holder !== source) return;
			holder = null;
			show(null);
		}
	});
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
