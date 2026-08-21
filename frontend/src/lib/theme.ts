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
	document.documentElement.setAttribute('data-theme', resolve(choice));
	if (choice === 'system') localStorage.removeItem(KEY);
	else localStorage.setItem(KEY, choice);
}

export function watchSystem(onChange: () => void): () => void {
	if (typeof window === 'undefined') return () => {};
	const query = window.matchMedia('(prefers-color-scheme: dark)');
	query.addEventListener('change', onChange);
	return () => query.removeEventListener('change', onChange);
}
