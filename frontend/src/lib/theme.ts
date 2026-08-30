/** Theme resolution. Three toggle states, two themes.
 *
 * `system` is not a third theme - it is the absence of an override, and it
 * re-resolves when the device changes so a phone switching at sunset takes the
 * reader with it.
 */

export type ThemeChoice = 'system' | 'light' | 'dark';

const KEY = 'idhazh:theme';

export function storedChoice(): ThemeChoice {
	if (typeof localStorage === 'undefined') return 'system';
	const value = localStorage.getItem(KEY);
	return value === 'light' || value === 'dark' ? value : 'system';
}

export function resolve(choice: ThemeChoice): 'light' | 'dark' {
	if (choice !== 'system') return choice;
	if (typeof window === 'undefined') return 'light';
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function apply(choice: ThemeChoice): void {
	if (typeof document === 'undefined') return;
	const theme = resolve(choice);
	document.documentElement.setAttribute('data-theme', theme);
	paintBrowserChrome(theme);
	if (choice === 'system') localStorage.removeItem(KEY);
	else localStorage.setItem(KEY, choice);
}

/** Keep the browser's own chrome on the same theme as the page.
 *
 * `app.html` ships two `theme-color` tags behind media queries, which is what
 * an installed window uses before any script runs. They only know what the
 * system wants, so a manual choice would leave a light page under dark chrome.
 * One unconditional tag, written here, wins over both.
 */
function paintBrowserChrome(theme: 'light' | 'dark'): void {
	const colour = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim();
	if (!colour) return;
	let tag = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]:not([media])');
	if (!tag) {
		tag = document.createElement('meta');
		tag.name = 'theme-color';
		document.head.appendChild(tag);
	}
	tag.content = colour;
}

export function watchSystem(onChange: () => void): () => void {
	if (typeof window === 'undefined') return () => {};
	const query = window.matchMedia('(prefers-color-scheme: dark)');
	query.addEventListener('change', onChange);
	return () => query.removeEventListener('change', onChange);
}
