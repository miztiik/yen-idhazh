import { getContext, setContext } from 'svelte';
import type { NumberFormatConfig } from './number-format';

export const NUMBER_FORMAT_CONTEXT = Symbol('number-format');

export function provideNumberFormat(config: NumberFormatConfig): void {
	setContext(NUMBER_FORMAT_CONTEXT, config);
}

export function useNumberFormat(): NumberFormatConfig {
	const config = getContext<NumberFormatConfig | undefined>(NUMBER_FORMAT_CONTEXT);
	if (config === undefined) throw new Error('Number formatting was not provided by the page.');
	return config;
}
