/** What every console route carries above its own panels, as the producer wrote it.
 *
 * The console is three routes, and a route is where a metric goes to die unless
 * something outside it says a metric is there. So two things stand identically
 * on all three: a band that answers "did it work, what is worst, how much room
 * is left", and a navigation strip whose every label carries its own worst
 * state.
 *
 * **This module reads. It does not derive.** Until 2026-09-09 the same facts
 * were computed here at build time from the committed ledger under `state/`,
 * which meant the console could only exist as a document a build had already
 * finished. The pipeline writes `console/band.json` now, so the derivation has
 * one home - `backend/idhazh/publish_console_band.py` - and this side maps the
 * published shape onto the names the components already use. Two derivations of
 * one verdict is two verdicts.
 *
 * It is browser-safe on purpose. The band arrives by fetch, so nothing here may
 * touch a file, and `$lib/server/` would refuse to bundle for a browser at all.
 */

/** Green: it worked. Amber: look at it. Red: it did not work. */
export type Health = 'green' | 'amber' | 'red';

export type RouteId = 'pipelines' | 'model' | 'machine';

/** How loud a route's worst state is.
 *
 * Ranked rather than coloured. The strip never takes the health ramp - green,
 * amber and red on a label would say a route is failing, and a route is a noun -
 * so this ordering exists to pick the one worst thing across three routes, and
 * never to paint anything. The producer writes the same four numbers.
 */
export const BROKEN = 3;
export const WORTH_A_LOOK = 2;
export const WORTH_KNOWING = 1;
export const CLEAR = 0;

export interface ConsoleRoute {
	id: RouteId;
	/** The strip's word for the route. `Pipelines` is the owner's own, taken
	 * verbatim on 2026-08-30; `Summaries` and `Hardware` replaced `Model` and
	 * `Machine` on 2026-08-31. The id and the href did not move with them. */
	label: string;
	/** Route-relative and trailing-slashed. A component prefixes `base`. */
	href: string;
	/** One line under the strip, and the same text as the link's title. */
	description: string;
	/** The route's own worst state, appended to its label. Null when clear. */
	worst: string | null;
	severity: number;
}

/** One run of the newest day, as the band draws it. */
export interface BandRun {
	health: Health;
	/** What the square means, for a reader who cannot see the colour. */
	label: string;
}

export interface ConsoleBandFacts {
	/** The newest day the manifests hold, as a sentence. */
	verdict: {
		date: string | null;
		sentence: string;
		health: Health;
		/** One square a run, in the order they ran. It says what the sentence
		 * cannot: whether one run ate every failure or all five limped. */
		runs: BandRun[];
		/** Runs past the twelve drawn. A day of thirty squares is a chart. */
		moreRuns: number;
	};
	/** The one worst thing on the whole console, and which route it is on. */
	worst: { id: RouteId; label: string; href: string; sentence: string } | null;
	size: {
		/** The committed payload tree at the newest run, or null if unmeasured. */
		bytes: number | null;
		/** That tree against the 1 GB Pages cap. */
		capFraction: number | null;
		/** Megabytes left under the cap. */
		leftMb: number | null;
		/** Articles to the cap, at the cost the whole record measured. */
		articlesToCap: number | null;
		/** Published days the per-article cost was measured over. */
		measuredDays: number;
		sentence: string;
	};
}

export interface ConsoleShell {
	band: ConsoleBandFacts;
	routes: ConsoleRoute[];
	/** One sentence per route pointing at the panel another route owns. */
	carries: Record<RouteId, string>;
	/** Every month the archive holds a shard for, newest last.
	 *
	 * It rides on the band because a page cannot ask for a month until it knows
	 * which months exist, and a list fetched on its own would be a fifth serial
	 * hop before the first row of data (Carmack, 2026-09-08).
	 */
	months: string[];
	/** False when no band payload could be read. The page prints a named absence
	 * rather than a verdict it does not have. */
	read: boolean;
}

const ROUTE_IDS: RouteId[] = ['pipelines', 'model', 'machine'];
const HEALTHS: Health[] = ['green', 'amber', 'red'];

/** What the console draws when no band payload could be read.
 *
 * A named absence, not a blank: an operator who sees no band has to be told
 * whether the day was clean or whether nothing answered. The strip keeps its
 * three routes with no worst state, so the console is still navigable when the
 * one file it needs first is the one that failed (`CLAUDE.md` section 1a,
 * degrade rather than fail).
 */
export const BAND_UNREAD: ConsoleShell = {
	band: {
		verdict: {
			date: null,
			sentence: 'The band could not be read, so nothing here reports on the last run.',
			health: 'amber',
			runs: [],
			moreRuns: 0
		},
		worst: null,
		size: {
			bytes: null,
			capFraction: null,
			leftMb: null,
			articlesToCap: null,
			measuredDays: 0,
			sentence: 'No size was read, so there is nothing to hold against the 1 GB limit.'
		}
	},
	routes: ROUTE_IDS.map((id) => ({
		id,
		label: { pipelines: 'Pipelines', model: 'Summaries', machine: 'Hardware' }[id],
		href: { pipelines: '/console/', model: '/console/model/', machine: '/console/machine/' }[id],
		description: {
			pipelines: 'Did the runs work, which feeds broke, and what each stage cost.',
			model: 'What the model wrote, how long it took, and what it got wrong.',
			machine: 'The hardware the model ran on, and how much it varied between runs.'
		}[id],
		worst: null,
		severity: CLEAR
	})),
	carries: {
		pipelines: 'The band could not be read, so this route carries no figure from another.',
		model: 'The band could not be read, so this route carries no figure from another.',
		machine: 'The band could not be read, so this route carries no figure from another.'
	},
	months: [],
	read: false
};

function text(value: unknown, fallback = ''): string {
	return typeof value === 'string' ? value : fallback;
}

function count(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function healthOf(value: unknown): Health {
	return HEALTHS.includes(value as Health) ? (value as Health) : 'amber';
}

/** The published band as the components read it, or the named absence.
 *
 * Every field is checked rather than cast. The payload is our own and validated
 * where it was written, but it arrives over the network on a page that has to
 * keep working when a deploy is half done - so a shape that does not answer
 * degrades to `BAND_UNREAD` and says so, instead of throwing inside a load and
 * taking the whole route with it.
 */
export function readBand(payload: unknown): ConsoleShell {
	if (!payload || typeof payload !== 'object') return BAND_UNREAD;
	const raw = payload as Record<string, unknown>;
	const verdict = (raw.verdict ?? {}) as Record<string, unknown>;
	const size = (raw.size ?? {}) as Record<string, unknown>;
	if (typeof verdict.sentence !== 'string' || typeof size.sentence !== 'string') return BAND_UNREAD;

	const published = Array.isArray(raw.routes) ? (raw.routes as Record<string, unknown>[]) : [];
	const byId = new Map(published.map((route) => [text(route.id), route]));
	// Ordered by this list and not by the payload's, so the strip cannot be
	// reordered by a producer change. A route the payload omits keeps its place
	// with no worst state rather than vanishing from the strip.
	const routes: ConsoleRoute[] = ROUTE_IDS.map((id) => {
		const found = byId.get(id);
		const blank = BAND_UNREAD.routes.find((route) => route.id === id) as ConsoleRoute;
		if (found === undefined) return blank;
		return {
			id,
			label: text(found.label, blank.label),
			href: text(found.href, blank.href),
			description: text(found.description, blank.description),
			worst: typeof found.worst === 'string' ? found.worst : null,
			severity: count(found.severity) ?? CLEAR
		};
	});

	const worst = (raw.worst ?? null) as Record<string, unknown> | null;
	const worstId = worst === null ? '' : text(worst.id);
	const runs = Array.isArray(verdict.runs) ? (verdict.runs as Record<string, unknown>[]) : [];

	return {
		band: {
			verdict: {
				date: typeof verdict.date === 'string' ? verdict.date : null,
				sentence: verdict.sentence,
				health: healthOf(verdict.health),
				runs: runs.map((run) => ({ health: healthOf(run.health), label: text(run.label) })),
				moreRuns: count(verdict.more_runs) ?? 0
			},
			worst:
				worst === null || !ROUTE_IDS.includes(worstId as RouteId)
					? null
					: {
							id: worstId as RouteId,
							label: text(worst.label),
							href: text(worst.href),
							sentence: text(worst.sentence)
						},
			size: {
				bytes: count(size.bytes),
				capFraction: count(size.cap_fraction),
				leftMb: count(size.left_mb),
				articlesToCap: count(size.articles_to_cap),
				measuredDays: count(size.measured_days) ?? 0,
				sentence: size.sentence
			}
		},
		routes,
		carries: {
			pipelines: text(byId.get('pipelines')?.carries, BAND_UNREAD.carries.pipelines),
			model: text(byId.get('model')?.carries, BAND_UNREAD.carries.model),
			machine: text(byId.get('machine')?.carries, BAND_UNREAD.carries.machine)
		},
		months: Array.isArray(raw.months) ? raw.months.filter((m): m is string => typeof m === 'string') : [],
		read: true
	};
}
