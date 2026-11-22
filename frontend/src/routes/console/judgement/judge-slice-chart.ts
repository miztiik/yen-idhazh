/** Compare one digest's drawn ranges without treating them as a continuous score axis. */
import { valueAxis } from '../../../lib/charts/d3/axis';
import { bandScale } from '../../../lib/charts/d3/scale';
import { AXIS_LABEL_GAP_PX, labelWidth, type Frame } from '../../../lib/charts/frame';
import { readoutOf } from '../../../lib/charts/readout';
import { judgeDecimal, judgeShare, type SliceOutcome } from '../../../lib/console/judge-observations';
import { numberFormatter, type NumberFormatConfig } from '../../../lib/number-format';

const OUTCOMES = [
	{ label: 'Agreed YES', token: '--chart-1' },
	{ label: 'Agreed NO', token: '--chart-2' },
	{ label: 'Other returned', token: '--chart-3' },
	{ label: 'Did not return', token: '--chart-8' }
] as const;

export const NOT_DRAWN = 'Not drawn';
export const GAP_LABEL = ['Not', 'drawn'] as const;

interface SliceRange {
	edges: [string, string];
	label: string;
	drawn: number | null;
	total: string | null;
	counts: [number, number, number, number] | null;
}

export function judgeSliceEvidence(slices: readonly SliceOutcome[], format: NumberFormatConfig) {
	const number = numberFormatter(format);
	const exact = (value: number) => number(value, { exact: true });
	const ranges: SliceRange[] = [];
	function add(low: number, high: number, slice?: SliceOutcome) {
		const first = judgeDecimal(low, format);
		const last = judgeDecimal(high, format);
		const edges: SliceRange['edges'] = [`${first}-`, last];
		const label = `${first} to ${last}`;
		if (slice === undefined) {
			ranges.push({ edges, label, drawn: null, total: null, counts: null });
			return;
		}
		const other = slice.unclear + slice.split + slice.refused;
		const outstanding = slice.drawn - slice.yes - slice.no - other;
		ranges.push({ edges, label, drawn: slice.drawn, total: exact(slice.drawn), counts: [slice.yes, slice.no, other, outstanding] });
	}
	for (const [index, slice] of slices.entries()) {
		const previous = slices[index - 1];
		if (previous && previous.high < slice.low) add(previous.high, slice.low);
		add(slice.low, slice.high, slice);
	}

	function yesOfAgreed(counts: SliceRange['counts']) {
		if (counts === null) return null;
		const [yes, no] = counts;
		const agreed = yes + no;
		return agreed === 0 ? 'No agreed YES or NO' :
			`${exact(yes)} of ${exact(agreed)} (${judgeShare(yes, agreed, format)})`;
	}

	const readout = readoutOf({
		type: 'stackedCountColumns',
		columns: ranges.map(({ label }) => label),
		series: [
			{ label: 'Drawn', swatch: null, values: ranges.map(({ total }) => total), format: exact },
			...OUTCOMES.map(({ label, token }, index) => ({
				label,
				swatch: ranges.some(({ counts }) => (counts?.[index] ?? 0) > 0) ? `var(${token})` : null,
				values: ranges.map(({ counts }) => counts?.[index] ?? null),
				format: exact
			})),
			{
				label: 'YES of agreed', swatch: null, format: exact,
				values: ranges.map(({ counts }) => yesOfAgreed(counts))
			}
		],
		notMeasured: NOT_DRAWN,
		resting: 'first'
	});
	return { ranges, readout };
}

export function judgeSliceColumns(
	ranges: readonly SliceRange[], box: Frame, density: number, format: NumberFormatConfig
) {
	if (ranges.length === 0) return null;
	const { labels } = box;
	// Leave one more line above the grid for totals and below it for the second score bound.
	const top = box.top + labels.leading;
	const bottom = box.bottom - labels.leading;
	const plot = { ...box, top, bottom, innerHeight: bottom - top };
	const band = bandScale(ranges.map((_, index) => String(index)), plot, 'x', 0);
	const needed = ranges.reduce((max, range) => Math.max(max, ...[
		...range.edges, ...(range.total === null ? GAP_LABEL : [range.total])
	].map((text) => labelWidth(text, labels))), 0) + AXIS_LABEL_GAP_PX;
	if (band.bandwidth() < needed || plot.innerHeight <= 0) return null;

	const totals = ranges.flatMap(({ drawn }) => drawn === null ? [] : [drawn]);
	const axis = valueAxis(totals, plot, {
		along: 'y', ticks: Math.min(density, Math.max(1, ...totals)), number_format: format
	});
	const width = Math.min(band.bandwidth() - AXIS_LABEL_GAP_PX, plot.innerHeight);
	const columns = ranges.map((range, index) => {
		const center = band(String(index))! + band.bandwidth() / 2;
		let start = 0;
		const segments = (range.counts ?? []).flatMap((count, part) => {
			if (count === 0) return [];
			const floor = axis.scale(start);
			start += count;
			const y = axis.scale(start);
			return [{ y, height: floor - y, token: OUTCOMES[part]!.token }];
		});
		return { ...range, center, top: axis.scale(start), segments };
	});
	// Return the exact rows rather than erase a positive outcome too small to paint.
	if (columns.some(({ segments }) => segments.some(({ height }) => height < 1))) return null;
	return { plot, columns, width, axis };
}
