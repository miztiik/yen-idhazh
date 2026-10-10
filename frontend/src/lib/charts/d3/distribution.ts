/** How bad it gets: one quantity over many items, as counts in bins with the running share on a second axis.
 *
 * The bars say where the readings fall; the curve says what share of them sit
 * at or below each bin, nought to a hundred, so "nine in ten were under two
 * seconds" is read off the page rather than added up from bar heights. The
 * rules the caller names - a limit, a target - are drawn across the plot at
 * their own value and are always inside its domain.
 *
 * **Below its floor it draws nothing and says why.** A histogram of eight
 * readings is a claim about a shape eight readings cannot have, so under
 * `minValues` the geometry is null and `distributionShortfall` names the floor
 * it missed. The floor is the caller's, from config.
 */
import { bin } from 'd3-array';
import { line } from 'd3-shape';
import { scaleLog } from 'd3-scale';

import type { Frame } from '../frame';
import { tooFewSentence } from '../../console/waiting';
import { valueAxis, type ValueAxis } from './axis';

export interface DistributionRule {
	at: number;
	label: string;
}

export interface DistributionOptions {
	frame: Frame;
	/** The fewest readings the shape is drawn from - `console.fleet_min_rows`. */
	minValues: number;
	/** How many ticks each axis aims for. The bins are cut at the value axis's
	 * own ticks, so every bin edge is a labelled number. */
	valueTicks: number;
	rules?: readonly DistributionRule[];
	scale: 'linear' | 'log';
	domain?: [number, number];
}

export type LegacyDistributionOptions = Omit<DistributionOptions, 'scale' | 'domain'> & { scale?: never; domain?: never };

export interface Bin {
	x0: number;
	x1: number;
	count: number;
	/** The bar, in the chart's own pixels. */
	left: number;
	width: number;
	top: number;
	height: number;
	/** Percent of every reading at or below this bin's upper edge. */
	share: number;
}

export interface PlacedRule extends DistributionRule {
	x: number;
}

export interface BinGeometry {
	frame: Frame;
	/** The quantity, along the bottom. */
	x: ValueAxis;
	/** How many readings, up the left. */
	y: ValueAxis;
	/** The running share, up the right, nought to a hundred. */
	share: ValueAxis;
	bins: Bin[];
	/** The running-share curve, as an SVG path. */
	cumulative: string;
	rules: PlacedRule[];
	/** Readings drawn. */
	count: number;
}

function finiteOf(values: readonly number[]): number[] {
	return values.filter((value) => Number.isFinite(value));
}

/** Why there is no distribution, in words, or null where there is one. */
export function distributionShortfall(
	values: readonly number[],
	opts: Pick<DistributionOptions, 'minValues'>
): string | null {
	const have = finiteOf(values).length;
	return have > 0 && have < opts.minValues ? tooFewSentence(have, opts.minValues, 'readings') : null;
}

/** The distribution, or null where there are fewer readings than its floor. */
export function distribution(values: readonly number[], opts: DistributionOptions): BinGeometry | null;
export function distribution(values: readonly number[], opts: LegacyDistributionOptions): BinGeometry | null;
export function distribution(values: readonly number[], opts: DistributionOptions | LegacyDistributionOptions): BinGeometry | null {
	const box = opts.frame;
	const readings = finiteOf(values);
	if (readings.length === 0 || readings.length < opts.minValues) return null;
	const rules = opts.rules ?? [];

	const all = [...readings, ...rules.map((rule) => rule.at)];
	for (const rule of rules) {
		if (!Number.isFinite(rule.at) || !rule.label.trim()) throw new Error('A distribution rule needs at and a label.');
	}
	let x = valueAxis(all, box, {
		along: 'x',
		ticks: opts.valueTicks
	});
	if (opts.scale === 'log' && all.some((value) => value <= 0)) throw new Error('A log distribution needs positive readings and rules.');
	const domain: [number, number] = opts.domain ?? (opts.scale === 'log'
		? [10 ** Math.floor(Math.log10(Math.min(...all))), 10 ** (Math.floor(Math.log10(Math.max(...all))) + 1)]
		: x.domain);
	if (!Number.isFinite(domain[0]) || !Number.isFinite(domain[1]) || domain[0] >= domain[1] || all.some((value) => value < domain[0] || value > domain[1])) throw new Error('The distribution domain must contain all readings and rules.');
	if (opts.scale === 'log') {
		if (domain[0] <= 0) throw new Error('A log distribution domain must be positive.');
		const scale = scaleLog().domain(domain).range([box.left, box.right]);
		const ticks = [];
		for (let power = Math.ceil(Math.log10(domain[0])); 10 ** power <= domain[1]; power += 1) {
			const value = 10 ** power;
			ticks.push({ value, at: scale(value), text: String(value) });
		}
		x = { domain, along: 'x', scale: (value) => scale(value), ticks };
	} else if (opts.domain !== undefined) {
		const scale = (value: number) => box.left + (value - domain[0]) / (domain[1] - domain[0]) * box.innerWidth;
		const axis = valueAxis(domain, box, { along: 'x', ticks: opts.valueTicks, zero: false });
		x = { ...axis, domain, scale, ticks: axis.ticks.filter((tick) => tick.value >= domain[0] && tick.value <= domain[1]).map((tick) => ({ ...tick, at: scale(tick.value) })) };
	}
	const edges = x.ticks.map((tick) => tick.value);
	const binned = bin()
		.domain(x.domain)
		.thresholds(edges.filter((edge) => edge > x.domain[0] && edge < x.domain[1]))(readings);
	const y = valueAxis(
		binned.map((group) => group.length),
		box,
		{ along: 'y', ticks: opts.valueTicks }
	);
	const share = valueAxis([0, 100], box, { along: 'y', ticks: opts.valueTicks });

	let below = 0;
	const bins = binned.map((group) => {
		const x0 = group.x0 ?? x.domain[0];
		const x1 = group.x1 ?? x.domain[1];
		below += group.length;
		const top = y.scale(group.length);
		return {
			x0,
			x1,
			count: group.length,
			left: x.scale(x0),
			width: x.scale(x1) - x.scale(x0),
			top,
			height: y.scale(0) - top,
			share: (below / readings.length) * 100
		};
	});
	const curve = line<{ at: number; share: number }>()
		.x((point) => x.scale(point.at))
		.y((point) => share.scale(point.share));
	const cumulative =
		curve([{ at: bins[0]?.x0 ?? x.domain[0], share: 0 }, ...bins.map((b) => ({ at: b.x1, share: b.share }))]) ?? '';

	return {
		frame: box,
		x,
		y,
		share,
		bins,
		cumulative,
		rules: rules.map((rule) => ({ ...rule, x: x.scale(rule.at) })),
		count: readings.length
	};
}
