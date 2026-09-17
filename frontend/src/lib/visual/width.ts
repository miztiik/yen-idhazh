/** How much room a chart has, and one watcher that answers for all of them.
 *
 * **The drawing takes the width it is given.** Until this
 * module existed the drawing was laid out at a fixed 720 units and the figure
 * took the card's width, so the browser scaled every user unit to fit - and a
 * `--text-xs` string set at 12 units resolved at 4.8 CSS px on a 390 px phone.
 * The type was the right size in a coordinate space nobody reads. Here the
 * width is measured first and the marks are placed in it, so one drawn unit is
 * one CSS pixel and a token means on the drawing what it means everywhere else.
 *
 * **One watcher for every chart on the page rather than one each**, which is
 * the shape `$lib/reveal` already uses for the same reason: a day runs to
 * hundreds of stories, and an observer apiece is a cost that rises because a
 * run published more (CLAUDE.md Guardrail #12).
 *
 * **The room is floored to whole pixels, and that is a rule rather than
 * rounding taste.** A drawing rounded up is wider than the box it was measured
 * in; on a card that fits its contents that resizes the box, which reports a
 * new width, which redraws - a loop whose only exit is a browser's resize-depth
 * limit. Floored, the drawing can only ever sit up to one pixel short, which
 * is the tolerance `frontend/tests/item-visual.spec.ts` holds it to.
 */

/** What a chart does when it learns how much room it has. */
type Placed = (room: number) => void;

/** The one watcher, built when the first chart asks and kept after that.
 *
 * Kept rather than rebuilt for the reason `$lib/reveal` keeps its own: a
 * watcher with nothing to watch costs nothing, and rebuilding it would make the
 * count rise again on a page a reader scrolls up and down.
 */
let watcher: ResizeObserver | null = null;

/** Every chart being watched, and what each one does when its box moves. */
const drawn = new Map<Element, Placed>();

/**
 * The content width of one box, in whole CSS pixels.
 *
 * Taken off the fractional border box rather than off `clientWidth`, which a
 * browser rounds to a whole pixel in either direction - and a round up would
 * hand the drawing a pixel the card does not have. This is the one definition
 * of "the room", used for the first reading and for every later one, so a
 * drawing cannot be measured two ways.
 */
export function roomIn(node: Element): number {
	const style = getComputedStyle(node);
	const inside =
		node.getBoundingClientRect().width -
		parseFloat(style.paddingLeft) -
		parseFloat(style.paddingRight) -
		parseFloat(style.borderLeftWidth) -
		parseFloat(style.borderRightWidth);
	return Number.isFinite(inside) ? Math.max(0, Math.floor(inside)) : 0;
}

/** Stop watching one box. */
function forget(node: Element): void {
	if (!drawn.delete(node)) return;
	watcher?.unobserve(node);
}

/** One resize report, for however many charts moved together. */
function moved(entries: ResizeObserverEntry[]): void {
	for (const entry of entries) drawn.get(entry.target)?.(roomIn(entry.target));
}

/**
 * Watch one box, and say how much room it has now and whenever that changes.
 *
 * **The first reading is synchronous**, taken before this returns rather than
 * waiting for the watcher's own first delivery. A chart that had to wait would
 * have one frame with no width, and a drawing placed in no width is a picture
 * that flashes empty on every story a reader scrolls to.
 *
 * Returns the way to stop: a caller unmounting a chart calls it, and the box is
 * neither watched nor reported afterwards.
 */
export function whenWide(node: Element, run: Placed): () => void {
	watcher ??= new ResizeObserver(moved);
	drawn.set(node, run);
	watcher.observe(node);
	run(roomIn(node));
	return () => forget(node);
}
