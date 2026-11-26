/** Read dated writes for bounded, consented compact periods through the query keeper. */
import { preflight } from './ask-reader';
import { COMPACT_PERIODS, compactPeriods, type CompactEntry, type CompactIndex, type Period } from './compact-index';
import { compactWriteFooter, type CompactWrite } from './compact-write-footer';
import type { PageKeeper, WantedFile } from './page-keeper';
import { coveredDays, firstNamed, namesFile, newestNamed } from './slice';
import { dataPath, dataVersion, explainRefusal, explainShortfall, readIndexFrom } from './slice-reader';
import { isDay, SliceRequestError, type LedgerName } from './slice-shapes';
import { siteKeepsFrom } from './site-window';

interface Limits { maxFiles: number; maxBytes: number }
export interface CompactWriteRequest extends Limits { days: number; presets: readonly number[] }
interface Member { ledger: LedgerName; period: Period; entry: CompactEntry }
interface Span { ledger: LedgerName; from: string; to: string }
type Indexes = Record<Period, CompactIndex | null>;

export interface CompactWriteTrack {
	period: Period;
	candidates: number;
	writes: CompactWrite[];
	issues: string[];
	spans: Span[];
	days: number;
	omitted: boolean;
}

export type CompactPeriodReading =
	| { state: 'coverage' | 'packed'; entry: CompactEntry; write: CompactWrite | null }
	| { state: 'coarser'; period: Period; covers: string }
	| { state: 'expired'; through: string }
	| { state: 'unavailable' | 'unrecorded' };

function price(members: readonly Member[], limits: Limits) {
	return preflight({
		files: members.length, bytes: members.reduce((sum, member) => sum + member.entry.bytes, 0),
		readFrom: null, readTo: null, cut: [], through: {}
	}, limits.maxFiles, limits.maxBytes);
}

function allowed(keeper: PageKeeper, ledger: LedgerName) {
	return keeper.catalog.get(ledger)?.publish_to_data_explorer === true;
}

async function ledgerIndexes(keeper: PageKeeper, ledger: LedgerName) {
	const issues: Partial<Record<Period, string>> = {};
	async function index(period: Period) {
		const reading = await readIndexFrom(keeper, ledger, period);
		if (reading !== null && 'index' in reading) return reading.index;
		const issue = reading === null ? `${period} index is not published` : explainRefusal(period, reading.refused);
		issues[period] = `${ledger}: ${issue}.`;
		keeper.warn(`[ledger] ${issues[period]}`);
		return null;
	}
	const [daily, monthly, yearly] = await Promise.all(COMPACT_PERIODS.map(index));
	const indexes: Indexes = { daily, monthly, yearly };
	const entries = COMPACT_PERIODS.map((period) => indexes[period] === null ? [] : compactPeriods(indexes[period]!));
	const through = newestNamed(entries[0], entries[1], entries[2]);
	const first = through === null ? null : firstNamed(entries[0], entries[1], entries[2]);
	return { ledger, indexes, issues, first, through };
}

type LedgerIndexes = Awaited<ReturnType<typeof ledgerIndexes>>;

function candidates(inventory: readonly LedgerIndexes[], period: Period, days: number) {
	const items: Member[] = [];
	const spans: Span[] = [];
	const issues: string[] = [];
	for (const held of inventory) {
		const { ledger, first, through } = held;
		const index = held.indexes[period];
		if (index === null) {
			const issue = held.issues[period];
			if (issue) issues.push(issue);
			continue;
		}
		if (first === null || through === null) continue;
		const start = siteKeepsFrom(through, days);
		const from = start > first ? start : first;
		spans.push({ ledger, from, to: through });
		for (const entry of index.entries) {
			const covered = coveredDays(period, entry.covers);
			if (entry.rows > 0 && covered.last >= from && covered.first <= through) items.push({ ledger, period, entry });
		}
	}
	return { items, spans, issues, days, period };
}

function planWrites(inventory: readonly LedgerIndexes[], request: CompactWriteRequest) {
	const widest = Math.max(...request.presets);
	const monthly = candidates(inventory, 'monthly', widest);
	const yearly = candidates(inventory, 'yearly', widest);
	const reserved: Member[] = [];
	const fit = (plan: ReturnType<typeof candidates>) => {
		const omitted = price([...reserved, ...plan.items], request) !== null;
		if (!omitted) reserved.push(...plan.items);
		return { ...plan, omitted };
	};
	const lead = fit(monthly);
	const years = fit(yearly);
	const daily = [...request.presets].sort((a, b) => b - a)
		.filter((days) => days <= request.days).map((days) => candidates(inventory, 'daily', days));
	const days = daily.find((plan) => price([...reserved, ...plan.items], request) === null) ?? daily.at(-1)!;
	return { monthly: lead, yearly: years, daily: fit(days) };
}

function checkLimits(limits: Limits) {
	if (![limits.maxFiles, limits.maxBytes].every((value) => Number.isSafeInteger(value) && value > 0)) {
		throw new SliceRequestError('compact write reads require positive file and byte limits');
	}
}

export function compactWriteReader(keeper: PageKeeper, rangeOnly: boolean) {
	const held = new Map<string, Promise<CompactWrite | string>>();

	async function read(member: Member, file: WantedFile): Promise<CompactWrite | string> {
		const report = (why: string) => {
			const note = `${member.ledger} ${member.entry.covers}: ${why}.`;
			keeper.warn(`[ledger] ${note}`);
			return note;
		};
		try {
			const result = await keeper.hold([file], rangeOnly);
			if ('failed' in result) return report(result.shortfall.reason === 'absent'
				? 'the indexed compact file is missing' : explainShortfall(file, result.shortfall));
			try {
				const write = await compactWriteFooter(result.engine, result.names[0], {
					ledger: member.ledger, period: member.period, covers: member.entry.covers
				});
				return write ?? report('the footer does not establish a dated Gardener write');
			} finally {
				await result.done();
			}
		} catch (error) {
			return report(`the compact footer could not be read (${error instanceof Error ? error.message : String(error)})`);
		}
	}

	function inspect(member: Member) {
		const { ledger, period, entry } = member;
		const path = dataPath(keeper.catalog, ledger, period, entry.covers);
		const version = dataVersion(entry);
		const key = `${path}?${version}`;
		const previous = held.get(key);
		if (previous !== undefined) return previous;
		const answer = read(member, { path, version, bytes: entry.bytes, byRange: rangeOnly });
		held.set(key, answer);
		void answer.then((value) => {
			if (typeof value === 'string') held.delete(key);
		});
		return answer;
	}

	function activity(request: CompactWriteRequest): Record<Period, Promise<CompactWriteTrack>> {
		checkLimits(request);
		if (!request.presets.includes(request.days) || request.presets.some((days) => !Number.isSafeInteger(days) || days < 1)) {
			throw new SliceRequestError('compact write reads require an available UTC window');
		}
		const ledgers = keeper.catalog.entries.filter((entry) => allowed(keeper, entry.name));
		const planned = Promise.all(ledgers.map(({ name }) => ledgerIndexes(keeper, name)))
			.then((inventory) => planWrites(inventory, request));
		async function track(period: Period): Promise<CompactWriteTrack> {
			const plan = (await planned)[period];
			const answers = plan.omitted ? [] : await Promise.all(plan.items.map(inspect));
			return {
				period, candidates: plan.items.length, days: plan.days, spans: plan.omitted ? [] : plan.spans, omitted: plan.omitted,
				writes: answers.filter((answer): answer is CompactWrite => typeof answer !== 'string'),
				issues: [...plan.issues, ...answers.filter((answer): answer is string => typeof answer === 'string')]
			};
		}
		return { daily: track('daily'), monthly: track('monthly'), yearly: track('yearly') };
	}

	async function period(ledger: LedgerName, grain: Period, covers: string, limits: Limits): Promise<CompactPeriodReading> {
		checkLimits(limits);
		const day = grain === 'daily' ? covers : grain === 'monthly' ? `${covers}-01` : `${covers}-01-01`;
		if (!allowed(keeper, ledger) || !isDay(day)) throw new SliceRequestError('compact detail needs a consented ledger and valid UTC period');
		const { indexes } = await ledgerIndexes(keeper, ledger);
		const index = indexes[grain];
		if (index === null) return { state: 'unavailable' };
		const entry = compactPeriods(index).find((candidate) => candidate.covers === covers);
		if (entry !== undefined) {
			if (!namesFile(entry) || entry.rows === 0) return { state: 'coverage', entry, write: null };
			const member = { ledger, period: grain, entry };
			if (price([member], limits) !== null) return { state: 'unavailable' };
			const write = await inspect(member);
			return { state: 'packed', entry, write: typeof write === 'string' ? null : write };
		}
		const year = day.slice(0, 4);
		const expired = indexes.yearly?.expired_through;
		if (expired && year <= expired) return { state: 'expired', through: expired };
		const month = day.slice(0, 7);
		if (grain !== 'yearly' && indexes.yearly?.entries.some((entry) => entry.covers === year)) {
			return { state: 'coarser', period: 'yearly', covers: year };
		}
		if (grain === 'daily' && indexes.monthly?.entries.some((entry) => entry.covers === month)) {
			return { state: 'coarser', period: 'monthly', covers: month };
		}
		return { state: 'unrecorded' };
	}

	return { activity, period };
}
