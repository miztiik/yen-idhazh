/** The page's own word for "the whole day is in this document".
 *
 * One document answers every dated address, so a dated page carries no stories
 * at all when its HTML arrives - they land when the day's fetch resolves. That
 * is true of a first load, of a reload, and of an offline read where the service
 * worker answers instead of the host. So a locator read straight after `goto`
 * or `reload` measures the shell, and whether it happens to catch the day is a
 * property of the machine rather than of the code: measured 2026-09-09 on an
 * Intel Core i7-1265U, the day was already on the page every time, while the
 * same read on `ubuntu-latest` found nothing and took `main` red.
 *
 * `ready` is the one `DayStatus` that means the stories arrived, and the route
 * sets the status and the day in one callback, so the attribute and the stories
 * land in the same flush. Waiting for it is therefore the whole synchronisation
 * a dated page needs, and there is nothing else to use.
 *
 * **Wait for the state you want, never for the absence of one you do not.** A
 * negated `toHaveAttribute` passes when the element is missing, so it cannot
 * fail on a page that never hydrated.
 */

import { expect, type Page } from '@playwright/test';

export async function dayReady(page: Page, why = 'the day never arrived'): Promise<void> {
	await expect(page.locator('[data-payload-state]'), why).toHaveAttribute(
		'data-payload-state',
		'ready'
	);
}
