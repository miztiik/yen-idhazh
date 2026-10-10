/** Which sources failed in feed reads or article fetches on the same recorded days? */
import type { Row } from '../../data/slice-shapes';
import type { FeedResult } from '../../server/payload';
import type { LedgerTable } from '../../server/ledger-rows';
import type { RecordRead } from '../recording';
import type { Range } from '../queries/window';
import { windowRange } from '../queries/window';
import { answered, failing, preserves, settled, reliability, resultLabel } from '../../feed-health';
import { tileStrip, type TileInput } from '../../charts/d3/tileStrip';
import { datesOf, numberOf, wordOf, readingRecords, dayReadout } from './record';

export interface FeedInput { results: FeedResult[]; read: RecordRead }
// The existing feedResults projection, on its canonical reader's single answer.
// Keeping that answer's metadata avoids reading the same rows twice or losing empty/read-failed distinctions.
export function feedInput(table: LedgerTable): FeedInput {
	return {
		read: table.read,
		results: settled(table.rows.map((row) => ({
			runId: row.run_id ?? '', date: row.date ?? '', feedId: row.feed_id ?? '',
			checkedAt: row.checked_at ?? '', outcome: row.outcome ?? '',
			status: row.status ? Number(row.status) : null, items: Number(row.items ?? 0) || 0, detail: row.detail ?? ''
		})))
	};
}
const FAILS: Record<string, string> = {
	http_client_error: 'client error', http_rate_limited: 'rate limited',
	http_server_error: 'server error', network_error: 'network error'
};
export function fallbackFeeds(input: FeedInput, days: number, cap: number, marked: number, named: number) {
	if (input.read.state !== 'read') return null;
	const newest = input.results.map((row) => row.date).sort().at(-1);
	if (newest === undefined) return null;
	return feedsFailed(input, null, windowRange(days, newest, input.read.first), cap, marked, named);
}
function commonCode(rows: readonly Row[]): string {
	const codes = new Map<string, number>();
	for (const row of rows) codes.set(wordOf(row.code), (codes.get(wordOf(row.code)) ?? 0) + 1);
	const common = [...codes].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
	return common ? FAILS[common[0]] ?? common[0] : 'no failure recorded';
}
export function feedsFailed(input: FeedInput, articles: readonly Row[] | null, range: Range, cap: number, marked: number, named: number) {
	const feeds = input.results.filter((row) => row.date >= range.from && row.date <= range.to);
	const feedThrough = feeds.map((row) => row.date).sort().at(-1) ?? null;
	const articleThrough = articles?.map((row) => wordOf(row.date, '')).filter(Boolean).sort().at(-1) ?? null;
	const through = articles === null ? feedThrough : feedThrough && articleThrough ? [feedThrough, articleThrough].sort()[0] : null;
	const dates = through === null ? [] : datesOf({ ...range, to: through });
	const sourceIds = [...new Set([...feeds.map((row) => row.feedId), ...(articles ?? []).map((row) => wordOf(row.source_id, ''))])].filter(Boolean);
	const sources = sourceIds.map((sourceId) => {
		const feedRows = feeds.filter((row) => row.feedId === sourceId && through !== null && row.date <= through);
		const articleRows = (articles ?? []).filter((row) => row.source_id === sourceId && through !== null && wordOf(row.date, '') >= range.from && wordOf(row.date, '') <= through);
		const feedFailures = feedRows.filter(failing);
		const feedCodes = new Map<string, number>();
		for (const row of feedFailures) feedCodes.set(resultLabel(row), (feedCodes.get(resultLabel(row)) ?? 0) + 1);
		const commonFeed = [...feedCodes].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0];
		const newestFeedFailure = feedFailures.map((row) => row.date).sort().at(-1);
		const failures = articleRows.filter((row) => Object.hasOwn(FAILS, wordOf(row.code, '')));
		const days = dates.map((date) => {
			const feedDay = feedRows.filter((row) => row.date === date && !preserves(row));
			const articleDay = articleRows.filter((row) => row.date === date);
			const failedFeed = feedDay.filter(failing).length;
			const failedArticle = articleDay.filter((row) => Object.hasOwn(FAILS, wordOf(row.code, ''))).length;
			const knownArticle = articleDay.length > 0 && articleDay.every((row) => typeof row.outcome === 'string' && row.outcome !== '');
			const feed: TileInput = feedDay.length === 0 ? { date, state: 'absent' } : { date, state: failedFeed > 0 ? 'fired' : 'quiet', reading: failedFeed };
			const article: TileInput = !knownArticle && failedArticle === 0 ? { date, state: 'absent' } : { date, state: failedArticle >= marked ? 'fired' : 'quiet', reading: failedArticle };
			return { date, feed, article, feedDay, articleDay };
		});
		const firedDates = days.filter((day) => day.feed.state === 'fired' || day.article.state === 'fired');
		const newestFailure = failures.map((row) => wordOf(row.date, '')).sort().at(-1);
		const record = (kind: 'feed' | 'article') => readingRecords(days.map((day) => ({
			title: `${sourceId}, ${kind}, ${day.date}`, facts: kind === 'feed' ? [
				{ label: 'Feed reads', value: day.feed.state === 'absent' ? 'not recorded as asked' : `${day.feed.reading} failed of ${day.feedDay.length} asked` },
				{ label: 'Answers', value: day.feedDay.map((row) => `${resultLabel(row)}${row.status === null ? '' : `, HTTP ${row.status}`}${row.detail ? `, ${row.detail}` : ''}`).join('; ') || 'not recorded' }
			] : [
				{ label: 'Article fetches', value: day.article.state === 'absent' ? 'not recorded as asked' : `${day.article.reading} failed of ${day.articleDay.length} recorded fetches` },
				{ label: 'Answers', value: day.articleDay.map((row) => `${FAILS[wordOf(row.code)] ?? wordOf(row.code)}, ${wordOf(row.outcome)}${numberOf(row.http_status) === null ? '' : `, HTTP ${row.http_status}`}; ${wordOf(row.source_form)}, tier ${numberOf(row.tier) ?? 'not recorded'}`).join('; ') || 'not recorded' }
			]
		})));
		return {
			sourceId, fired: firedDates.length,
			feed: tileStrip(days.map((day) => day.feed), { thresholds: [1, 1] }),
			article: articles === null ? null : tileStrip(days.map((day) => day.article), { thresholds: [marked, named] }),
			feedRecords: dayReadout(record('feed')), articleRecords: dayReadout(record('article')),
			ending: newestFailure ? `mostly ${commonCode(failures)}, last ${newestFailure}` : 'no article failure recorded',
			feedEnding: newestFeedFailure ? `mostly ${commonFeed}, last ${newestFeedFailure}` : 'no feed failure recorded',
			observed: days.some((day) => day.feed.state !== 'absent' || day.article.state !== 'absent'),
			answeredEveryDay: days.length > 0 && days.every((day) => day.feedDay.length > 0 && day.feedDay.every(answered) &&
				articles !== null && day.articleDay.length > 0 && day.articleDay.every((row) => row.outcome === 'ok'))
		};
	}).sort((a, b) => b.fired - a.fired || a.sourceId.localeCompare(b.sourceId));
	const failed = sources.filter((source) => source.fired > 0);
	const clean = sources.filter((source) => source.observed && source.fired === 0);
	const answeredAll = clean.filter((source) => source.answeredEveryDay).length;
	return {
		sources: failed.slice(0, cap), hidden: Math.max(0, failed.length - cap), clean: clean.length,
		feedRecord: reliability(feeds),
		through, feedThrough, articleThrough,
		lede: through === null ? 'There is no common observed row end, so no common failure count can be stated.'
			: `${failed.length} sources failed on at least one day${failed[0] ? `; ${failed[0].sourceId} failed on ${failed[0].fired} of ${dates.length}` : ''}.${articles === null ? ' This is the feed record alone.' : ''}`,
		tail: `${Math.max(0, failed.length - cap)} more sources failed on fewer days; ${answeredAll} answered on every day. ${clean.length - answeredAll} other observed sources had no recorded failure, but an unobserved or refused ask is not an answer.`,
		waiting: feedThrough && articleThrough && feedThrough < articleThrough ? `Waiting for the feed record after ${feedThrough}; article days through ${articleThrough} do not extend the common axis.` : null,
		feedWaiting: feedThrough && articleThrough && feedThrough > articleThrough ? `Feed results after ${articleThrough} wait for their article fetches; feeds through ${feedThrough} do not extend the common axis.` : null,
		noCommon: through === null,
		completeClean: dates.length > 0 && clean.length > 0 && failed.length === 0 && sources.every((source) => source.answeredEveryDay)
	};
}
export function feedReadNotes(input: FeedInput, range: Range | null): string[] {
	if (input.read.state === 'not-packed') return ['Not published yet. No feed record was included in this build, so a common feed-and-article count cannot be stated.'];
	if (input.read.state === 'unreadable') return ['Did not arrive. The build could not read the feed record, so a common feed-and-article count cannot be stated.'];
	if (range === null) return [];
	const notes: string[] = [];
	if (input.read.first > range.from) notes.push(`Feed records begin on ${input.read.first}; earlier days in this span are not clean feed days.`);
	if (input.read.through < range.to) notes.push(`Feed records stop on ${input.read.through}; later days are not clean feed days.`);
	const lost = input.read.lostDays.filter((date) => date >= range.from && date <= range.to);
	if (lost.length) notes.push(`Feed records were lost for ${lost.join(', ')}; those days are not successful asks.`);
	const setAside = Object.values(input.read.setAside).reduce((sum, count) => sum + count, 0);
	if (setAside) notes.push(`${setAside} feed record files were set aside unread; feed counts may be short.`);
	return notes;
}
