/** Share the mounted window choice and the active route's record reach. */
import { getContext, onDestroy, setContext } from 'svelte';
import type { TimeWindow } from '../charts/viewport';
import type { RecordWindow } from './waiting';
import type { WindowChoice } from './window-preference';
import type { ConsoleDestinationId } from './console-destinations';

/** What the control reads off the route under it.
 *
 * Getters rather than values, so the control follows the route's own state for
 * as long as the route is on the page instead of a copy taken when it opened.
 */
export interface WindowSource {
	/** Read these getters only while this route owns the layout. */
	readonly route: ConsoleDestinationId;
	readonly days: number;
	readonly presets: readonly number[];
	/** True while the route is fetching what the window reaches into. */
	readonly busy: boolean;
	/** False until a browser has run the route. */
	readonly ready: boolean;
	/** Optional replacement for the window's evidence sentence. */
	readonly statusLine?: string | null;
	readonly record?: RecordWindow | null;
	/** Private evidence keeps its published-day endpoint, independent of the native record. */
	readonly publishedWindow?: TimeWindow | null;
	/** Month files a preset would fetch that the route does not hold yet. */
	monthsFor(days: number): number;
	onChange(days: number): void;
}

/** Where a route hands its window. */
interface WindowSlot {
	choice: WindowChoice;
	utcDay(): string | null;
	fill(source: WindowSource): void;
	/** Empty the slot, but only if it still holds this source. */
	clear(source: WindowSource): void;
}

const SLOT = Symbol('console-window');

/** A plain holder prevents an outgoing teardown from clearing its replacement. */
export function provideWindowSlot(
	show: (source: WindowSource | null) => void,
	choice: WindowChoice,
	utcDay: () => string | null
): void {
	let holder: WindowSource | null = null;
	setContext<WindowSlot>(SLOT, {
		choice,
		utcDay,
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

/** The mounted layout keeps this choice when its route changes. */
export function useWindowChoice(): WindowChoice {
	const slot = getContext<WindowSlot | undefined>(SLOT);
	if (slot === undefined) throw new Error('A console route needs the layout window slot.');
	return slot.choice;
}

export function useConsoleUtcDay(): () => string | null {
	const slot = getContext<WindowSlot | undefined>(SLOT);
	if (slot === undefined) throw new Error('A console route needs the layout window slot.');
	return slot.utcDay;
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
