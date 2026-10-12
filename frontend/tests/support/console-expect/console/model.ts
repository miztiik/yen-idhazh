/** Summaries keeps its throughput readout and independently declared table columns. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	bansRouter: true,
	cellFormats: {
		summaries: /^(not measured|\d+)$/,
		'not-sure': /^(not measured|\d+)$/,
		unsupported: /^(not measured|\d+)$/,
		hedge: /^(not measured|\d+)$/,
		part: /^(not measured|\d+)$/,
		'part-pct': /^(not measured|\d+%)$/,
		copied: /^(not measured|\d+%)$/,
		'per-item': /^(not measured|(<1|\d+) s( (<1|\d+) s when cut short)?)$/,
		minutes: /^(not measured|(<1|\d+) min)$/,
		'too-long': /^(not measured|\d+)$/,
		failed: /^(not measured|\d+)$/,
		determinism: /^(not measured|\d+)$/
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
	sectionOrder: ['table', 'chart']
};
