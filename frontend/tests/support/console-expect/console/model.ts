/** Summaries keeps its throughput readout and independently declared table columns. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	bansRouter: true,
	cellFormats: {
		summaries: /^(-|\d+)$/,
		'not-sure': /^(-|\d+)$/,
		unsupported: /^(-|\d+)$/,
		hedge: /^(-|\d+)$/,
		part: /^(-|\d+)$/,
		'part-pct': /^(-|\d+%)$/,
		copied: /^(-|\d+%)$/,
		'per-item': /^(-|(<1|\d+)( (<1|\d+) when cut short)?)$/,
		minutes: /^(-|<1|\d+)$/,
		'too-long': /^(-|\d+)$/,
		failed: /^(-|\d+)$/
	},
	unscoredCells: ['not-sure', 'unsupported', 'hedge', 'part', 'part-pct', 'copied'],
	internalColumns: [
		'hhem',
		'coverage',
		'compression',
		'extractiveness',
		'verbatim_run',
		'unsupported_numbers',
		'hedge_dropped',
		'truncation_flagged',
		'extraction_suspect',
		'determinism_violation',
		'evidential_density',
		'speculative_density',
		'scorer_version',
		'score_ms',
		'summarize_ms',
		'prefill_ms',
		'decode_ms',
		'input_tokens',
		'output_tokens',
		'cached_tokens'
	],
	sectionHeading: 'What the model did',
	chartHeading: 'Model tokens per second',
	throughputLink: {
		label: 'why the range is wide',
		href: 'https://github.com/miztiik/yen-idhazh/blob/main/docs/architecture/summarize/throughput.md'
	},
	readoutRows: ['read', 'write', 'items'],
	readoutSeries: ['read', 'write'],
	readoutHint: 'Point at a day to read it. Left and Right step through the days, Escape returns to the newest.',
	sectionOrder: ['chart', 'table']
};
