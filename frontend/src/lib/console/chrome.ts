/** Which frame the console layout draws around a route: the full console chrome, or the compact workbench a route asks for in its load. */

export const CONSOLE_CHROMES = ['console', 'workbench'] as const;
export type ConsoleChrome = (typeof CONSOLE_CHROMES)[number];

export function consoleChromeOf(data: { chrome?: unknown } | null | undefined): ConsoleChrome {
	return data?.chrome === 'workbench' ? 'workbench' : 'console';
}
