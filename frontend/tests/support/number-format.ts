import { numberFormatConfig } from '../../src/lib/server/config';
import { coverageSentence as drawCoverageSentence, type Coverage, type CoverageItems } from '../../src/lib/charts/frame';
import { horizonRate as writeHorizonRate } from '../../src/lib/charts/glance';
import { grouped as formatGrouped } from '../../src/lib/charts/series';
import { valueAxis as drawValueAxis, type ValueAxisOptions } from '../../src/lib/charts/d3/axis';
import {
	dateSeries as drawDateSeries,
	type DateSeriesOptions,
	type LegacyDateSeriesOptions,
	type SeriesInput
} from '../../src/lib/charts/d3/dateSeries';
import {
	distribution as drawDistribution,
	distributionShortfall as drawDistributionShortfall,
	type DistributionOptions,
	type LegacyDistributionOptions
} from '../../src/lib/charts/d3/distribution';
import { flow as drawFlow, type FlowOptions, type FlowStageInput } from '../../src/lib/charts/d3/flow';
import {
	pairedScatter as drawPairedScatter,
	pairedScatterShortfall as drawPairedScatterShortfall,
	type ScatterOptions,
	type ScatterInput
} from '../../src/lib/charts/d3/pairedScatter';
import { tooFewSentence as writeTooFewSentence } from '../../src/lib/console/waiting';
import {
	mergeNote as writeMergeNote,
	mergeRate as writeMergeRate,
	rateWithDenominator as writeRateWithDenominator,
	describeUnclear as writeDescribeUnclear,
	type MergeTotals
} from '../../src/lib/console/merge-line';
import {
	reasonHeadline as writeReasonHeadline,
	unexplainedNote as writeUnexplainedNote,
	type ReasonDay
} from '../../src/lib/console/doubt-reasons';
import { money as writeMoney } from '../../src/lib/charts/machine';
import { faithfulness as reduceFaithfulness } from '../../src/lib/console/model/faithfulness';
import { matchHeadline as writeMatchHeadline, type EvalDay } from '../../src/lib/console/eval-instruments';
import { numberFormatter } from '../../src/lib/number-format';
import type { NumberFormatConfig } from '../../src/lib/number-format';

export const numberFormat = numberFormatConfig();
export const formatNumber = numberFormatter(numberFormat);

export function grouped(value: number): string {
	return formatGrouped(value, numberFormat);
}

export function valueAxis(
	values: readonly number[],
	frame: Parameters<typeof drawValueAxis>[1],
	options: Omit<ValueAxisOptions, 'number_format'>
): ReturnType<typeof drawValueAxis> {
	return drawValueAxis(values, frame, { ...options, number_format: numberFormat });
}

type DateSeriesTestOptions =
	| Omit<DateSeriesOptions, 'number_format'>
	| Omit<LegacyDateSeriesOptions, 'number_format'>;

export function dateSeries(series: readonly SeriesInput[], options: DateSeriesTestOptions) {
	const configured = { ...options, number_format: numberFormat };
	return 'rule' in options
		? drawDateSeries(series, configured as DateSeriesOptions)
		: drawDateSeries(series, configured as LegacyDateSeriesOptions);
}

type DistributionTestOptions =
	| Omit<DistributionOptions, 'number_format'>
	| Omit<LegacyDistributionOptions, 'number_format'>;

export function distribution(values: readonly number[], options: DistributionTestOptions) {
	const configured = { ...options, number_format: numberFormat };
	return 'scale' in options
		? drawDistribution(values, configured as DistributionOptions)
		: drawDistribution(values, configured as LegacyDistributionOptions);
}

export function distributionShortfall(values: readonly number[], options: { minValues: number }) {
	return drawDistributionShortfall(values, { ...options, number_format: numberFormat });
}

export function flow(stages: readonly FlowStageInput[], options: Omit<FlowOptions, 'number_format'>) {
	return drawFlow(stages, { ...options, number_format: numberFormat });
}

export function pairedScatter(
	points: readonly ScatterInput[],
	options: Omit<ScatterOptions, 'number_format'>
) {
	return drawPairedScatter(points, { ...options, number_format: numberFormat });
}

export function pairedScatterShortfall(
	points: readonly ScatterInput[],
	options: { minRows: number; minSubjects: number }
) {
	return drawPairedScatterShortfall(points, { ...options, number_format: numberFormat });
}

export function tooFewSentence(have: number, floor: number, noun: string, place?: string): string {
	return writeTooFewSentence(have, floor, noun, numberFormat, place);
}

export function coverageSentence(
	found: Coverage,
	lead: string,
	items?: CoverageItems | null
): string | null {
	return drawCoverageSentence(found, lead, numberFormat, items);
}

export function horizonRate(rate: number, days: number): string {
	return writeHorizonRate(rate, days, numberFormat);
}

export function mergeNote(totals: MergeTotals, days: number): string {
	return writeMergeNote(totals, days, numberFormat);
}

export function mergeRate(totals: MergeTotals, days: number): string | null {
	return writeMergeRate(totals, days, numberFormat);
}

export function rateWithDenominator(
	numerator: number | null,
	denominator: number | null,
	floor: number,
	mark?: number
): string | null {
	return writeRateWithDenominator(numerator, denominator, floor, numberFormat, mark);
}

export function describeUnclear(
	unclear: number | null,
	agreed: number | null,
	floor: number,
	mark?: number
): string {
	return writeDescribeUnclear(unclear, agreed, floor, numberFormat, mark);
}

export function reasonHeadline(days: readonly ReasonDay[], span: number): string | null {
	return writeReasonHeadline(days, span, numberFormat);
}

export function unexplainedNote(days: readonly ReasonDay[], span: number): string | null {
	return writeUnexplainedNote(days, span, numberFormat);
}

export function money(amount: number, currency: string): string {
	return writeMoney(amount, currency, numberFormat);
}

export function faithfulness(
	rows: Parameters<typeof reduceFaithfulness>[0],
	thresholds: { high: number; low: number },
	options: Parameters<typeof reduceFaithfulness>[2]
) {
	return reduceFaithfulness(rows, thresholds, options, numberFormat);
}

export function matchHeadline(days: readonly EvalDay[], span: number): string | null {
	return writeMatchHeadline(days, span, numberFormat);
}

export type { NumberFormatConfig };
