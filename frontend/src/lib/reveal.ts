/** One watcher for every story still waiting for its drawing.
 *
 * A story past the document's seed arrives with a path rather than a picture,
 * and asks for the file when the reader is nearly on it. Until 2026-09-06 each
 * of those stories built its own `IntersectionObserver`, so a day that
 * published more drawings held more watchers - one object, one callback and one
 * observed target per waiting story, for the life of the page. That is a cost
 * that rises because a run published more, which is what CLAUDE.md Rule #12
 * refuses.
 *
 * One watcher answers the same question for all of them. The browser already
 * hands a single observer every crossing in one callback, and the margin is the
 * same for every story, so nothing about the reveal changes: a story is still
 * asked for one screen early, still asked for once, and still drawn in its own
 * place.
 *
 * **A story that leaves the page is forgotten.** The watch is dropped and the
 * target unobserved, so a story scrolled past and destroyed cannot hold the
 * page's memory or fire later. The caller's own reply - the fetch it started -
 * is its own to cancel; this module owns the watching and nothing else.
 */

/** What a waiting story does once it is nearly on screen. */
type Arrival = () => void;

/** How early to ask.
 *
 * One screen of the scrolling root rather than a pixel count, so a phone asks
 * one phone-screen early and a desktop one desktop-screen, and there is no
 * number here to maintain.
 */
const NEAR = '100% 0px';

/** The one watcher, built when the first story waits and kept after that.
 *
 * Kept rather than rebuilt: a watcher with nothing to watch costs nothing, and
 * rebuilding it would make the count rise again on a page a reader scrolls up
 * and down.
 */
let watcher: IntersectionObserver | null = null;

/** Every story still waiting, and what each one does when it arrives. */
const waiting = new Map<Element, Arrival>();

/** Stop watching one story, whether it arrived or left. */
function forget(node: Element): void {
	if (!waiting.delete(node)) return;
	watcher?.unobserve(node);
}

/** One crossing report, for however many stories crossed together. */
function crossed(entries: IntersectionObserverEntry[]): void {
	for (const entry of entries) {
		if (!entry.isIntersecting) continue;
		const run = waiting.get(entry.target);
		if (!run) continue;
		// Forgotten before it runs, so a story asks once even if the reader
		// scrolls it past and back before the answer lands.
		forget(entry.target);
		run();
	}
}

/** Watch one story, and run `run` once when it is nearly on screen.
 *
 * Returns the way to stop: a caller unmounting a story calls it, and the story
 * is neither watched nor run afterwards.
 */
export function whenNear(node: Element, run: Arrival): () => void {
	watcher ??= new IntersectionObserver(crossed, { rootMargin: NEAR });
	waiting.set(node, run);
	watcher.observe(node);
	return () => forget(node);
}
