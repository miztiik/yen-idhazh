/** The page's own word for "every chart a reader can see has been drawn".
 *
 * A chart is prerendered as an SVG, and after mount the engine is fetched and
 * handed each chart host. The engine writes `data-chart` on the host: `waiting`
 * until it has drawn, then `live` or `failed`. It only draws a chart within one
 * screen of the viewport, so a chart further down stays `waiting` until a reader
 * comes near it - that is "not yet", never a fault.
 *
 * So the page is settled when every chart figure has a host the engine was
 * handed, and no host near the viewport still says `waiting`. A fixed sleep after
 * `goto` guessed at this; on a slow runner it guessed short, and on a fast one
 * it was time spent doing nothing.
 *
 * **Wait for the state you want, never for the absence of one you do not.** The
 * check fails while a figure has no host at all, so a page whose engine never
 * ran cannot pass it.
 */

import { expect, type Page } from '@playwright/test';

export async function chartsReady(page: Page, why = 'a chart near the viewport never drew'): Promise<void> {
	await expect
		.poll(
			() =>
				page.evaluate(() => {
					const reach = window.innerHeight * 2;
					return [...document.querySelectorAll('figure[data-chart-drawn]')].every((figure) => {
						const host = figure.querySelector('[data-chart]');
						if (host === null) return false;
						if (host.getAttribute('data-chart') !== 'waiting') return true;
						const box = host.getBoundingClientRect();
						// A hidden chart has no box and is never near; one past the
						// engine's reach is drawn when a reader scrolls to it.
						return box.width === 0 || box.top > reach || box.bottom < -reach;
					});
				}),
			{ message: why }
		)
		.toBe(true);
}
