/** When does a floating list on the Data explorer close itself? On a press or a focus outside it,
 * on Escape, and after a pick inside it.
 *
 * An open list lies over the regions below it, so a list that waits to be closed covers what a
 * person reaches for next. A press outside closes it on `pointerdown` and still does what it
 * pressed: the list floats, so closing it moves nothing under the pointer. Escape hands focus back
 * to the list's summary when focus was inside it. A pick leaves focus on the summary, never in the
 * editor, where a phone's keyboard would rise over the question that was just loaded.
 */
import { tick } from 'svelte';

/** Close `details` on a press or a focus outside it, and on Escape. */
export function closesWhenLeft(details: HTMLDetailsElement): { destroy(): void } {
	const outside = (event: Event) => {
		if (details.open && !details.contains(event.target as Node)) details.open = false;
	};
	const escape = (event: KeyboardEvent) => {
		if (event.key !== 'Escape' || !details.open) return;
		const inside = details.contains(document.activeElement);
		details.open = false;
		if (inside) details.querySelector('summary')?.focus();
	};
	document.addEventListener('pointerdown', outside);
	document.addEventListener('focusin', outside);
	document.addEventListener('keydown', escape);
	return {
		destroy() {
			document.removeEventListener('pointerdown', outside);
			document.removeEventListener('focusin', outside);
			document.removeEventListener('keydown', escape);
		}
	};
}

/** Close `details` after a pick inside it, and leave focus on its summary. */
export async function closeAfterPick(details: HTMLDetailsElement | null): Promise<void> {
	if (details !== null) details.open = false;
	await tick();
	details?.querySelector('summary')?.focus();
}
