import { base } from '$app/paths';
import { BAND_UNREAD, readBand } from '$lib/console/band';
import type { LayoutLoad } from './$types';

export const prerender = true;

/** Read the producer's shared navigation, settings and completion record once per layout. */
export const load: LayoutLoad = async ({ fetch }) => {
	const number_format = __UI_CONFIG__.number_format;
	try {
		const response = await fetch(`${base}/console/band.json`);
		if (!response.ok) {
			console.warn(`[console] band unavailable (${response.status}); drawing the absence`);
			return { ...BAND_UNREAD, number_format };
		}
		return { ...readBand(await response.json()), number_format };
	} catch (cause) {
		console.warn(`[console] band could not be read; drawing the absence - ${String(cause)}`);
		return { ...BAND_UNREAD, number_format };
	}
};
