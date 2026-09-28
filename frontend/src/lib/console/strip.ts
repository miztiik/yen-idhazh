/** When the console's tab strip is stuck to the top of the screen, and the two
 * things that follow from it.
 *
 * From `frame.breakpoints_px[1]` up the strip sticks, and a stuck strip is a
 * shorter strip: the tab descriptions leave, so it covers one row of every
 * screen rather than three. Two consequences are handled here and nowhere else.
 *
 * - **The page must not move when the strip shrinks.** The strip gives up its
 *   description lines and the box after it takes the same height in the same
 *   frame, so everything below it stays exactly where it was. A margin on the
 *   strip cannot do it: a margin collapses into the next element's margin, and
 *   the page moves by the smaller of the two.
 * - **Anything the page scrolls to lands below the strip, not behind it.** A
 *   jump link, a `Top` link and a focused control all scroll by the document's
 *   scroll padding, and that is set to the stuck strip's height.
 *
 * The strip sticks only once this has run. With no script there is nothing to
 * shorten it or to keep a jump link clear of it, so it stays in the flow like
 * the heading above it.
 *
 * It reads the strip's own computed `position` to know whether it can stick at
 * this width, so the width it sticks from is written once, in the stylesheet.
 */

/** Present, as `yes`, once the strip is allowed to stick. */
export const STRIP_LIVE = 'data-console-strip-live';
/** `yes` while the strip is stuck to the top of the screen, `no` otherwise. */
export const STRIP_STUCK = 'data-console-strip-stuck';
/** The height the strip gave up when it stuck, held by the box after it. */
const GIVE = '--console-strip-give';

/** Watch one strip. It needs the element immediately before it to be a
 * sentinel whose bottom edge is the strip's top edge in the flow, and the
 * element immediately after it to be the box that takes back what it gives up.
 */
export function stickStrip(strip: HTMLElement): { destroy(): void } {
	const found = strip.previousElementSibling;
	const next = strip.nextElementSibling;
	if (!(found instanceof HTMLElement) || !(next instanceof HTMLElement)) return { destroy() {} };
	const sentinel: HTMLElement = found;
	const give: HTMLElement = next;
	const root = document.documentElement;
	let watching = true;
	strip.setAttribute(STRIP_LIVE, 'yes');

	/** The strip's height with its descriptions and without them, read with no
	 * paint in between, so the reader never sees the strip in the state it was
	 * measured in. */
	function heights(): { full: number; short: number } {
		const was = strip.getAttribute(STRIP_STUCK) ?? 'no';
		strip.setAttribute(STRIP_STUCK, 'no');
		const full = strip.offsetHeight;
		strip.setAttribute(STRIP_STUCK, 'yes');
		const short = strip.offsetHeight;
		strip.setAttribute(STRIP_STUCK, was);
		return { full, short };
	}

	function settle(): void {
		// A font can finish loading after the route has gone.
		if (!watching) return;
		if (getComputedStyle(strip).position !== 'sticky') {
			strip.setAttribute(STRIP_STUCK, 'no');
			give.style.removeProperty(GIVE);
			root.style.removeProperty('scroll-padding-top');
			return;
		}
		const { full, short } = heights();
		const stuck = sentinel.getBoundingClientRect().bottom <= 0;
		strip.setAttribute(STRIP_STUCK, stuck ? 'yes' : 'no');
		if (stuck) give.style.setProperty(GIVE, `${full - short}px`);
		else give.style.removeProperty(GIVE);
		root.style.setProperty('scroll-padding-top', `calc(${short}px + var(--space-2))`);
	}

	// A window resize and a web font arriving are the two things that change
	// the strip's heights after the first measurement. Not a ResizeObserver:
	// measuring means resizing the strip it would be watching, and a callback
	// that resizes what it observes is the loop that observer reports as an
	// error.
	const crossing = new IntersectionObserver(settle);
	crossing.observe(sentinel);
	window.addEventListener('resize', settle);
	void document.fonts?.ready.then(settle);

	return {
		destroy() {
			watching = false;
			crossing.disconnect();
			window.removeEventListener('resize', settle);
			strip.removeAttribute(STRIP_LIVE);
			strip.removeAttribute(STRIP_STUCK);
			give.style.removeProperty(GIVE);
			root.style.removeProperty('scroll-padding-top');
		}
	};
}
