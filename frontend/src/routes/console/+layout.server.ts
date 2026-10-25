import { numberFormatConfig } from '$lib/server/config';

export function load() {
	return { number_format: numberFormatConfig() };
}
