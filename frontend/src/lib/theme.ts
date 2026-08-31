/** Theme resolution. Two themes, and the stored choice is one of them.
 *
 * Dark is the base: `:root` in `tokens.css` carries it, so a document with no
 * `data-theme` attribute - no script yet, or no script at all - paints dark on
 * its first frame. Light is the override.
 *
 * A choice is always written to storage as `light` or `dark`. Absence of the
 * key means the reader has never touched the control, and never means "the
 * default" - encode the default as absence and the day the default moves,
 * every reader who chose it moves with it without being asked.
 */

export type ThemeChoice = 'light' | 'dark';

const KEY = 'idhazh:theme';

/** The theme in force: the reader's stored choice, or the base. */
export function storedChoice(): ThemeChoice {
	if (typeof localStorage === 'undefined') return 'dark';
	return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark';
}

export function apply(choice: ThemeChoice): void {
	if (typeof document === 'undefined') return;
	document.documentElement.setAttribute('data-theme', choice);
	paintBrowserChrome();
	localStorage.setItem(KEY, choice);
}

/** Bring the chrome to the theme already on the page, storing nothing.
 *
 * Called on mount. `apply` cannot do this job, because it writes the choice -
 * and a reader who has never touched the control has not made one.
 */
export function syncBrowserChrome(): void {
	if (typeof document === 'undefined') return;
	paintBrowserChrome();
}

/** Keep the browser's own chrome on the same theme as the page.
 *
 * `app.html` ships one unconditional `theme-color` tag holding the base
 * theme's background, which is what an installed window uses before any script
 * runs. This rewrites that same tag from the resolved `--color-bg`, so a
 * reader who picked light does not sit under dark chrome.
 */
function paintBrowserChrome(): void {
	const colour = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim();
	if (!colour) return;
	let tag = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
	if (!tag) {
		tag = document.createElement('meta');
		tag.name = 'theme-color';
		document.head.appendChild(tag);
	}
	tag.content = colour;
}
