/** Keep the independent Operations reads under one route status and retry. */
import { onMount } from 'svelte';
import { COMPACT_PERIODS, type Period } from '../../data/compact-index';
import type { CompactWriteRequest, CompactWriteTrack } from '../../data/compact-file-writes';
import { compactWrites } from '../../data/ledger';
import { readSession } from '../../data/read-session';
import type { QueryStanding } from '../query-state';
import { councilRunsQuery, gardenerWakeQuery } from '../queries/operations';
import { rangeFor, retryAsks, routeReach, sliceOnce, type Range } from '../queries/window';
import type { Answer } from '../voices/record';

export interface OperationReading { answer: Answer; range: Range | null }
const pending: OperationReading = { answer: 'pending', range: null };
export type PackTracks = Partial<Record<Period, CompactWriteTrack>>;
interface PackReading {
	state: 'ok' | 'unreachable';
	track: CompactWriteTrack;
}
type ReportQuery = typeof councilRunsQuery | typeof gardenerWakeQuery;
const reportReaders = {
	[councilRunsQuery.name]: (range: Range) => sliceOnce(councilRunsQuery, range),
	[gardenerWakeQuery.name]: (range: Range) => sliceOnce(gardenerWakeQuery, range)
};

export function useOperationReads(request: CompactWriteRequest) {
	let council = $state.raw(pending);
	let gardener = $state.raw(pending);
	let packs = $state.raw<Partial<Record<Period, PackReading>>>({});
	let mounted = false;
	const tracks: PackTracks = $derived(Object.fromEntries(COMPACT_PERIODS.flatMap((period) => {
		const reading = packs[period];
		return reading ? [[period, reading.track] as const] : [];
	})));
	const writeAnswers = $derived(COMPACT_PERIODS.map((period): QueryStanding => packs[period] ?? 'pending'));
	const answers = $derived([council.answer, gardener.answer, ...writeAnswers]);
	const busy = $derived(answers.includes('pending'));

	function readReport(query: ReportQuery, publish: (next: OperationReading) => void) {
		const session = readSession();
		publish(pending);
		async function read(): Promise<OperationReading | null> {
			const reach = await routeReach([query.ledger]);
			if (!mounted || session !== readSession()) return null;
			const requestRange = rangeFor(query, request.days, reach, request.presets);
			if ('from' in requestRange) return { range: requestRange, answer: await reportReaders[query.name](requestRange) };
			return { range: null, answer: requestRange };
		}
		void read().then((reading) => {
			if (reading !== null && mounted && session === readSession()) publish(reading);
		}, (error: unknown) => {
			if (!mounted || session !== readSession()) return;
			console.warn(`[operations] The ${query.ledger} record could not be read.`, error);
			publish({ range: null, answer: { state: 'unreachable' } });
		});
	}

	function readPacks(periods: readonly Period[]) {
		if (periods.length === 0) return;
		const session = readSession();
		const next = { ...packs };
		for (const period of periods) delete next[period];
		packs = next;
		const work = Promise.resolve().then(() => compactWrites(request));
		for (const period of COMPACT_PERIODS) {
			void work.then((all) => all[period]).then((track) => {
				if (mounted && session === readSession() && periods.includes(period)) {
					packs = { ...packs, [period]: { state: 'ok', track } };
				}
			}, (error: unknown) => {
				if (!mounted || session !== readSession() || !periods.includes(period)) return;
				console.warn(`[operations] ${period} pack evidence could not be read.`, error);
				packs = { ...packs, [period]: {
					state: 'unreachable',
					track: {
						period, candidates: 0, writes: [], issues: [`The ${period} packs could not be read.`],
						spans: [], days: request.days, omitted: false
					}
				} };
			});
		}
	}

	const readCouncil = () => readReport(councilRunsQuery, (next) => { council = next; });
	const readGardener = () => readReport(gardenerWakeQuery, (next) => { gardener = next; });
	onMount(() => {
		mounted = true;
		readCouncil();
		readGardener();
		readPacks(COMPACT_PERIODS);
		return () => { mounted = false; };
	});

	return {
		get council() { return council; },
		get gardener() { return gardener; },
		get tracks() { return tracks; },
		get answers() { return answers; },
		get busy() { return busy; },
		retryPacks() {
			if (!busy) readPacks(COMPACT_PERIODS.filter((period) => (tracks[period]?.issues.length ?? 0) > 0));
		},
		retry() {
			if (busy) return;
			if (council.answer !== 'pending' && council.answer.state === 'unreachable') {
				retryAsks([councilRunsQuery]);
				readCouncil();
			}
			if (gardener.answer !== 'pending' && gardener.answer.state === 'unreachable') {
				retryAsks([gardenerWakeQuery]);
				readGardener();
			}
			readPacks(COMPACT_PERIODS.filter((period) => packs[period]?.state === 'unreachable'));
		}
	};
}
