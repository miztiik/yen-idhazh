/** Does one console panel clear the sufficiency gates a selector can decide?
 *
 * Six of the ten gates in `docs/concepts/design-system.md` are arithmetic
 * over a drawn panel, so they are specs rather than a reviewer's reading: 1
 * uses the screen, 2 separates figure from ground, 3 lands one thing first, 5
 * names its comparison, 6 carries its confounders, and 8 tells its four
 * nothings apart. Gate 4 is a reviewer reading the component, and gates 7, 9
 * and 10 are enforced by tests that already exist.
 *
 * The split is the point of the file: `readPanel` measures in the page and
 * returns plain numbers and words, and every `judge` function below is pure.
 * So the fixture panel and a real judged panel are held to the same code, and a
 * number printed beside a capture is the number a gate judged.
 */

import type { Locator } from '@playwright/test';

/** A colour as it lands on screen, every see-through layer already blended
 * onto what is behind it. Two computed strings can differ while the pixels do
 * not - `rgba(0, 0, 0, 0)` over white is white - so only this is compared. */
export type Rgb = [number, number, number];

export interface PlotReading {
	name: string;
	left: number;
	right: number;
	/** The colour the plot is drawn on. */
	ground: Rgb;
}

export interface LedeReading {
	/** How many elements in the panel carry `data-lede`. */
	count: number;
	/** Whether the lede holds words. One with none is a mark, judged by area. */
	words: boolean;
	/** The lede's type size in CSS px, or its area in square px for a mark. */
	lede: number;
	/** The largest other thing of the same kind in the panel. */
	rival: number;
	rivalWhat: string;
}

export interface TrendReading {
	name: string;
	/** `data-model-rule` on the chart or the element that declares for it. */
	rule: string;
	/** How many settings-change rules the chart draws. */
	lines: number;
	/** The words saying no setting changed inside the span, where it says so. */
	empty: string;
	/** Why a chart that does not draw the rule does not, in words. */
	reason: string;
}

export interface NothingReading {
	/** What a sighted reader can read in the panel body. */
	words: string;
	/** The colour of the box standing in for the chart, where there is one. */
	ground: Rgb | null;
}

export interface PanelReading {
	id: string;
	/** The panel's content box: its border box less border and padding. */
	content: { left: number; right: number };
	/** The colour just outside the panel, and the panel's own. */
	around: Rgb;
	panel: Rgb;
	plots: PlotReading[];
	ledes: LedeReading;
	comparisons: string[];
	/** Distinct bar fills in each date series the panel draws. */
	stackedFills: number[];
	trends: TrendReading[];
	nothing: NothingReading;
}

export type GateNumber = 1 | 2 | 3 | 5 | 6 | 8;

export interface Verdict {
	gate: GateNumber;
	pass: boolean;
	/** One sentence a person can act on, pass or fail. */
	says: string;
}

/** Everything the gates need from one `[data-console-panel-id]` element. */
export async function readPanel(panel: Locator): Promise<PanelReading> {
	return panel.evaluate((root: Element) => {
		const unseenTags = new Set(['title', 'desc', 'style', 'script', 'noscript', 'template']);

		const parse = (value: string): [number, number, number, number] => {
			if (value === 'transparent') return [0, 0, 0, 0];
			const legacy = /^rgba?\(([^)]+)\)$/.exec(value);
			if (legacy) {
				const [r, g, b, a] = legacy[1].split(/[\s,/]+/).filter(Boolean).map(Number);
				return [r, g, b, a ?? 1];
			}
			const modern = /^color\(srgb ([^)]+)\)$/.exec(value);
			if (modern) {
				const [r, g, b, a] = modern[1].split(/[\s/]+/).filter(Boolean).map(Number);
				return [r * 255, g * 255, b * 255, a ?? 1];
			}
			throw new Error(`a colour the sufficiency gates cannot read: ${value}`);
		};

		const ground = (element: Element): [number, number, number] => {
			const chain: Element[] = [];
			for (let node: Element | null = element; node; node = node.parentElement) chain.unshift(node);
			let seen: [number, number, number] = [255, 255, 255];
			for (const node of chain) {
				const [r, g, b, a] = parse(getComputedStyle(node).backgroundColor);
				seen = [r * a + seen[0] * (1 - a), g * a + seen[1] * (1 - a), b * a + seen[2] * (1 - a)];
			}
			return [Math.round(seen[0]), Math.round(seen[1]), Math.round(seen[2])];
		};

		// Hidden from a sighted reader: not drawn, or drawn into a one-pixel clip
		// the way screen-reader-only text is. `innerText` would count the second.
		const shown = (element: Element): boolean => {
			for (let node: Element | null = element; node; node = node.parentElement) {
				if (unseenTags.has(node.tagName.toLowerCase())) return false;
				const style = getComputedStyle(node);
				if (style.display === 'none' || style.visibility === 'hidden') return false;
				if (style.clip.startsWith('rect(0') || style.clipPath.startsWith('inset(50%')) return false;
				if (style.position === 'absolute' || style.position === 'fixed') {
					const box = node.getBoundingClientRect();
					if (box.width <= 1 && box.height <= 1) return false;
				}
				if (node === root) break;
			}
			return true;
		};

		const texts = (node: Element): { text: string; element: Element }[] => {
			const found: { text: string; element: Element }[] = [];
			const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
			for (let text = walker.nextNode(); text; text = walker.nextNode()) {
				const said = (text.textContent ?? '').replace(/\s+/g, ' ').trim();
				const parent = text.parentElement;
				if (said !== '' && parent !== null && shown(parent)) found.push({ text: said, element: parent });
			}
			return found;
		};

		const words = (node: Element): string =>
			texts(node)
				.map((one) => one.text)
				.join(' ');

		const filled = (element: Element): boolean => {
			const fill = getComputedStyle(element).fill;
			if (fill === 'none' || fill === '') return false;
			if (fill.startsWith('url(')) return true;
			return parse(fill)[3] > 0;
		};

		const style = getComputedStyle(root);
		const box = root.getBoundingClientRect();
		const content = {
			left: box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
			right: box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight)
		};

		const plots = [...root.querySelectorAll('[data-chart-type], [data-chart]')]
			.filter((plot) => shown(plot) && plot.getBoundingClientRect().width > 0)
			.map((plot) => {
				const at = plot.getBoundingClientRect();
				return {
					name:
						plot.getAttribute('data-chart-name') ??
						plot.getAttribute('aria-label') ??
						plot.getAttribute('data-chart-type') ??
						'a chart',
					left: at.left,
					right: at.right,
					ground: ground(plot)
				};
			});

		const ledeElements = [root, ...root.querySelectorAll('[data-lede]')].filter((node) =>
			node.hasAttribute('data-lede')
		);
		const ledes = { count: ledeElements.length, words: false, lede: 0, rival: 0, rivalWhat: 'nothing' };
		if (ledeElements.length === 1) {
			const lede = ledeElements[0];
			const sized = texts(root).map((one) => ({
				size: parseFloat(getComputedStyle(one.element).fontSize),
				what: `"${one.text.slice(0, 48)}"`,
				inside: lede.contains(one.element)
			}));
			const inside = sized.filter((one) => one.inside);
			if (inside.length > 0) {
				ledes.words = true;
				ledes.lede = Math.max(...inside.map((one) => one.size));
				for (const one of sized) {
					if (!one.inside && one.size > ledes.rival) {
						ledes.rival = one.size;
						ledes.rivalWhat = one.what;
					}
				}
			} else {
				const at = lede.getBoundingClientRect();
				ledes.lede = at.width * at.height;
				for (const mark of root.querySelectorAll('rect, circle, ellipse, polygon, path')) {
					if (lede.contains(mark) || mark.contains(lede) || !filled(mark) || !shown(mark)) continue;
					const area = mark.getBoundingClientRect();
					if (area.width * area.height > ledes.rival) {
						ledes.rival = area.width * area.height;
						ledes.rivalWhat = `a ${mark.tagName.toLowerCase()} mark`;
					}
				}
			}
		}

		const comparisons = [root, ...root.querySelectorAll('[data-comparison]')]
			.filter((node) => node.hasAttribute('data-comparison'))
			.map((node) => node.getAttribute('data-comparison') ?? '');

		const series = [...root.querySelectorAll('[data-chart-type="dateSeries"]')];
		const stackedFills = series.map(
			(chart) => new Set([...chart.querySelectorAll('rect')].map((bar) => getComputedStyle(bar).fill)).size
		);
		const trends = series.map((chart) => {
			const declared = chart.closest('[data-model-rule]');
			const ours = declared !== null && root.contains(declared) ? declared : null;
			const name = ours?.getAttribute('data-model-rule-name') ?? '';
			const empty =
				name === ''
					? ''
					: [...root.querySelectorAll('[data-model-rule-empty]')]
							.filter((note) => note.getAttribute('data-model-rule-empty') === name)
							.map(words)
							.join(' ');
			return {
				name: chart.getAttribute('data-chart-name') ?? 'a date series',
				rule: ours?.getAttribute('data-model-rule') ?? '',
				lines: ours?.querySelectorAll('[data-model-rule-line]').length ?? 0,
				empty,
				reason: ours?.getAttribute('data-model-rule-none') ?? ''
			};
		});

		const standIn = root.querySelector('[data-empty], [data-reserved]');
		const body = root.querySelector('.panel-body') ?? root;

		return {
			id: root.getAttribute('data-console-panel-id') ?? '',
			content,
			around: ground(root.parentElement ?? root),
			panel: ground(root),
			plots,
			ledes,
			comparisons,
			stackedFills,
			trends,
			nothing: { words: words(body), ground: standIn === null ? null : ground(standIn) }
		};
	});
}

/** How much of the panel's content width sits under at least one plot.
 *
 * Covered width rather than the widest plot, so two small multiples side by
 * side fill the panel together; and covered rather than spanned, so two thin
 * charts at opposite edges do not pass as one wide one. Null where the panel
 * draws no plot at all, which the gate reads as no share printed.
 */
export function fillShare(reading: PanelReading): number | null {
	const { left, right } = reading.content;
	if (right <= left) return null;
	const spans = reading.plots
		.map((plot): [number, number] => [Math.max(left, plot.left), Math.min(right, plot.right)])
		.filter(([from, to]) => to > from)
		.sort((a, b) => a[0] - b[0]);
	if (spans.length === 0) return null;
	let covered = 0;
	let [from, to] = spans[0];
	for (const [start, end] of spans.slice(1)) {
		if (start > to) {
			covered += to - from;
			[from, to] = [start, end];
		} else {
			to = Math.max(to, end);
		}
	}
	return (covered + to - from) / (right - left);
}

const percent = (share: number): string => `${(share * 100).toFixed(1)} percent`;

const hex = (colour: Rgb): string =>
	`#${colour.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;

/** One step of rounding either way, because a blended channel lands between two integers. */
const sameColour = (a: Rgb, b: Rgb): boolean => a.every((channel, at) => Math.abs(channel - b[at]) <= 1);

/** Gate 1: the drawn plot covers at least `floor` of the panel's content width. */
export function judgeFill(reading: PanelReading, floor: number): Verdict {
	const share = fillShare(reading);
	if (share === null) {
		return { gate: 1, pass: false, says: `${reading.id} draws no plot, so it has no share of its width to print` };
	}
	return {
		gate: 1,
		pass: share + 1e-9 >= floor,
		says: `${reading.id}: the plot covers ${percent(share)} of the panel's width, against a floor of ${percent(floor)}`
	};
}

/** Gate 2: the panel stands off the page, and every plot sits on the panel's own ground. */
export function judgeGround(reading: PanelReading): Verdict {
	if (sameColour(reading.panel, reading.around)) {
		return {
			gate: 2,
			pass: false,
			says: `${reading.id}: the panel is ${hex(reading.panel)}, the same colour as the page around it, so nothing lifts it off the ground`
		};
	}
	const stray = reading.plots.find((plot) => !sameColour(plot.ground, reading.panel));
	if (stray) {
		return {
			gate: 2,
			pass: false,
			says: `${reading.id}: ${stray.name} is drawn on ${hex(stray.ground)} rather than on the panel's ${hex(reading.panel)}, a tint under the plot that weakens every fill and axis on it`
		};
	}
	return {
		gate: 2,
		pass: true,
		says: `${reading.id}: the panel is ${hex(reading.panel)} on a page of ${hex(reading.around)}, and every plot sits on the panel`
	};
}

/** Gate 3: exactly one thing is marked to land first, and it is the largest thing in the panel. */
export function judgeLede(reading: PanelReading): Verdict {
	const { count, words, lede, rival, rivalWhat } = reading.ledes;
	if (count !== 1) {
		return {
			gate: 3,
			pass: false,
			says:
				count === 0
					? `${reading.id}: nothing carries data-lede, so nothing is marked to land first`
					: `${reading.id}: ${count} elements carry data-lede, so ${count} things compete to land first`
		};
	}
	const unit = words ? 'px type' : 'square px';
	const size = (value: number): string => `${Math.round(value * 10) / 10} ${unit}`;
	return {
		gate: 3,
		pass: lede > rival + 0.01,
		says: `${reading.id}: the lede is ${size(lede)} and the largest thing beside it is ${rivalWhat} at ${size(rival)}`
	};
}

/** Gate 5: the panel names one comparison with the word "against" in it, or declares a mix over time. */
export function judgeComparison(reading: PanelReading): Verdict {
	const named = reading.comparisons;
	if (named.length !== 1) {
		return {
			gate: 5,
			pass: false,
			says:
				named.length === 0
					? `${reading.id}: the panel declares no comparison, so a reader is left to guess what to compare`
					: `${reading.id}: ${named.length} elements declare a comparison, and a panel makes one`
		};
	}
	const [sentence] = named;
	if (sentence.includes(' against ')) {
		return { gate: 5, pass: true, says: `${reading.id} compares "${sentence}"` };
	}
	if (sentence === 'composition') {
		const mixed = reading.stackedFills.some((fills) => fills >= 2);
		return {
			gate: 5,
			pass: mixed,
			says: mixed
				? `${reading.id} shows a mix over time, stacked in more than one fill`
				: `${reading.id} declares a mix over time, and no stacked trend in it shows two parts`
		};
	}
	return {
		gate: 5,
		pass: false,
		says: `${reading.id}: "${sentence}" names a subject, not a comparison - it has no "against" in it`
	};
}

/** Gate 6: every trend over days says whether a settings change sits inside it. */
export function judgeTrends(reading: PanelReading): Verdict {
	if (reading.trends.length === 0) {
		return { gate: 6, pass: true, says: `${reading.id} draws no trend over days, so no settings change can hide in one` };
	}
	for (const trend of reading.trends) {
		const at = `${reading.id}: ${trend.name}`;
		if (trend.rule === 'yes' && trend.lines === 0 && trend.empty === '') {
			return { gate: 6, pass: false, says: `${at} says it draws the settings-change rule, and draws no rule and no sentence saying none fell inside it` };
		}
		if (trend.rule === 'no' && trend.reason.trim().split(/\s+/).filter(Boolean).length < 5) {
			return { gate: 6, pass: false, says: `${at} declines the settings-change rule without saying why in five words or more` };
		}
		if (trend.rule !== 'yes' && trend.rule !== 'no') {
			return {
				gate: 6,
				pass: false,
				says: `${at} is a trend with no settings-change declaration, so a line that moved because a setting changed looks like one that moved because the work got worse`
			};
		}
	}
	return { gate: 6, pass: true, says: `${reading.id}: every trend declares its settings-change rule` };
}

/** The four things a console panel can be when it has nothing to draw. */
export const NOTHINGS = ['loading', 'quiet', 'missing', 'unreachable'] as const;
export const REFUSED_NOTHINGS = ['loading', 'quiet', 'missing', 'unreachable', 'refused'] as const;
export type BasicNothing = (typeof NOTHINGS)[number];
export type Nothing = (typeof REFUSED_NOTHINGS)[number];

/** Gate 8: the four nothings are four different pictures to a reader. */
export function judgeNothings(id: string, readings: Record<Nothing, PanelReading>, states: readonly Nothing[] = NOTHINGS): Verdict {
	const seen = (state: Nothing): string => {
		const { words, ground } = readings[state].nothing;
		return `${words}|${ground === null ? 'no box' : hex(ground)}`;
	};
	const alike: string[] = [];
	for (let first = 0; first < states.length; first += 1) {
		for (let second = first + 1; second < states.length; second += 1) {
			if (seen(states[first]) === seen(states[second])) alike.push(`${states[first]} and ${states[second]}`);
		}
	}
	return alike.length === 0
		? { gate: 8, pass: true, says: `${id} draws ${states.join(', ')} as different pictures` }
		: { gate: 8, pass: false, says: `${id} draws ${alike.join(', ')} as the same picture, so a reader cannot tell them apart` };
}

/** The five gates a settled panel is judged on at one width and one theme. */
export function judgeSettled(reading: PanelReading, floor: number): Verdict[] {
	return [judgeFill(reading, floor), judgeGround(reading), judgeLede(reading), judgeComparison(reading), judgeTrends(reading)];
}
