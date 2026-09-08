import type { DayExtraction } from '../server/payload';

/** What the extractor found over a window of days, and what the page drew from it.
 *
 * A pure reduction over day records the caller already read, so it runs in Node
 * without a browser and a spec can re-derive every figure from the same records
 * and compare.
 *
 * **Three classes, not five.** `comparative` and `processual` are claims about
 * how an article is written rather than about its numbers, so they have no query
 * yet and land with the diagram plan. The panel says so on the page: an operator
 * who read three as the whole taxonomy would read `Not yet classified` as a
 * defect rather than as work nobody has done.
 */

/** Every figure the panel prints, for one window. */
export interface Extraction {
	days: number;
	/** Day records inside the window that carried an extraction block. The
	 * figures below are silent about every other day in the window. */
	measuredDays: number;
	/** Articles the candidate pass ran on. The integrity denominator, and never
	 * the published set. */
	items: number;
	/** Of those, the ones where every element span cut its own characters. */
	spanIntegrityPass: number;
	/** Elements the pass kept, over the window. It falls when the patterns stop
	 * matching, whatever the planner does. */
	elementsFound: number;
	chartable: number;
	narrative: number;
	unclassified: number;
	/** Chartable articles the window published. The unused denominator. */
	chartablePublished: number;
	/** Of those, the ones carrying a chart a reader can see. */
	chartableCharted: number;
	/** Chartable and published with no chart. The count behind `unusedPct`. */
	unused: number;
	/** `unused` over `chartablePublished`, whole percent. Null where the window
	 * published nothing chartable - a rate over nothing is not zero. */
	unusedPct: number | null;
	/** `spanIntegrityPass` over `items`, whole percent. Null on the same terms. */
	integrityPct: number | null;
	/** What the numbers say, in one sentence, or null where nothing was measured. */
	verdict: string | null;
}

const EMPTY: Extraction = {
	days: 0,
	measuredDays: 0,
	items: 0,
	spanIntegrityPass: 0,
	elementsFound: 0,
	chartable: 0,
	narrative: 0,
	unclassified: 0,
	chartablePublished: 0,
	chartableCharted: 0,
	unused: 0,
	unusedPct: null,
	integrityPct: null,
	verdict: null
};

function share(part: number, whole: number): number | null {
	return whole <= 0 ? null : Math.round((part / whole) * 100);
}

/** The one sentence the panel leads with.
 *
 * It names what moved and what it means, never a bare percentage: an operator
 * reading `12%` cannot tell a planner that stopped choosing charts from an
 * extractor that stopped finding numbers, and telling those two apart is the
 * whole reason the panel exists (`CLAUDE.md` section 0b).
 */
function verdictFor(found: Extraction): string | null {
	if (found.measuredDays === 0) return null;
	if (found.integrityPct !== null && found.integrityPct < 100) {
		const broken = found.items - found.spanIntegrityPass;
		return `${broken} of ${found.items} articles carried a fact the pipeline could no longer find in the text it was cut from. Those articles are degraded and the rest published normally.`;
	}
	if (found.chartablePublished === 0) {
		return `No article the window published stated enough figures of one kind to draw a chart from, so the planner had nothing to pass over.`;
	}
	if (found.unused === 0) {
		return `Every one of the ${found.chartablePublished} articles that could carry a chart carries one.`;
	}
	return `${found.unused} of ${found.chartablePublished} articles that could carry a chart went out without one. If this share climbs while the chartable count holds, the planner is passing over material it was given.`;
}

/** Add up a window's day records. Days with no block are counted and skipped. */
export function extraction(
	records: readonly (DayExtraction | null)[],
	days: number
): Extraction {
	const measured = records.filter((record): record is DayExtraction => record !== null);
	if (measured.length === 0) return { ...EMPTY, days };

	const total = (pick: (record: DayExtraction) => number) =>
		measured.reduce((sum, record) => sum + pick(record), 0);
	const items = total((record) => record.items);
	const chartablePublished = total((record) => record.chartablePublished);
	const chartableCharted = total((record) => record.chartableCharted);
	const spanIntegrityPass = total((record) => record.spanIntegrityPass);

	const found: Extraction = {
		days,
		measuredDays: measured.length,
		items,
		spanIntegrityPass,
		elementsFound: total((record) => record.elementsFound),
		chartable: total((record) => record.chartable),
		narrative: total((record) => record.narrative),
		unclassified: total((record) => record.unclassified),
		chartablePublished,
		chartableCharted,
		unused: chartablePublished - chartableCharted,
		unusedPct: share(chartablePublished - chartableCharted, chartablePublished),
		integrityPct: share(spanIntegrityPass, items),
		verdict: null
	};
	return { ...found, verdict: verdictFor(found) };
}
