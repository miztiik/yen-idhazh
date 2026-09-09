import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * The console never claims a fact it cannot have read.
 *
 * Every console panel reads a window. `feedResults` opens the newest
 * `shardMonths(90)` month shards, the source census reads at most
 * `collect.source_yield_min_complete_days` complete days, and the availability
 * states come from `HEALTH_WINDOW_DAYS` of the feed ledger. So a sentence that
 * says a feed "has never failed" is not a stronger version of "did not fail in
 * these runs" - it is a different claim, and it is one no read on the page can
 * support. A sentence that could only be true by reading everything is a
 * growing read wearing different clothes (`CLAUDE.md` Rule #12).
 *
 * It also costs the operator the answer he came for. A feed that broke once in
 * August and has answered every run since is permanently disqualified by
 * "never failed", and the question on the desk is whether anything is broken
 * now.
 *
 * **This bans a grammar, not a word list.** The present perfect - "has never
 * failed", "has ever reached" - places a claim in an unbounded past, and that
 * is the shape the console may not use about its own record. A `never` in the
 * present simple states a rule about how the page works and reads over no span
 * at all: "runs are never pooled", "a counterfactual, never a bill", "today is
 * never counted". Those are correct sentences and they stay. Two unbounded
 * totals go with the tense, because "in all" and "all time" say the same thing
 * with no verb at all.
 *
 * **What it does not catch, said out loud.** A bare past tense - "the feeds
 * that never failed" - makes the same claim and is not matched, because the
 * only pattern that would catch it is a list of verbs, and that list would fire
 * on "the part the machine never read" on this same page. So the three bare-past
 * strings this row removed are held by review and by the assertions in
 * `console.spec.ts`, not by this file. A rule stated as a property survives a
 * sentence nobody has written yet; a rule stated as a list is wrong the day
 * after it is written (`CLAUDE.md` Rule #12 design rationale).
 *
 * Runs in Node rather than in a page, like `payload-weight.spec.ts` beside it,
 * and it reads the same build the preview server is about to serve. A source
 * grep could not answer this: `console.spec.ts` carries all four of these words
 * legitimately, in test titles and comments, and the built document carries
 * neither.
 */

const BUILD = resolve(process.cwd(), 'build');

/** The three documents the console shell renders into. The band and the window
 * strip are shared, so a claim added to `console-shell.ts` reaches all three. */
const ROUTES = ['console', 'console/model', 'console/machine'] as const;

interface Claim {
	/** What the pattern is about, in the message a failure prints. */
	name: string;
	pattern: RegExp;
}

/**
 * The perfect tense allows at most two words before its adverb - "has ever",
 * "have never been", "has only ever" - so the gap is bounded rather than
 * open. An open gap bridges two clauses and fires on a page that happens to
 * say "has" early and "never" late in one sentence.
 *
 * `\b` on `ever` is what keeps it off `every`, `whenever` and `however`: those
 * have no word boundary after `ever`, so the pattern cannot end inside them.
 * `never` is matched on its own boundaries for the same reason.
 */
const CLAIMS: Claim[] = [
	{
		name: 'a claim in the present perfect ("has never failed", "have never been read")',
		pattern: /\b(?:has|have|had)(?:\s+\w+){0,2}\s+never\b/i
	},
	{
		name: 'a claim in the present perfect ("has ever reached", "has ever carried")',
		pattern: /\b(?:has|have|had)(?:\s+\w+){0,2}\s+ever\b/i
	},
	{ name: 'an unbounded total ("in all")', pattern: /\bin all\b/i },
	{ name: 'an unbounded span ("all time")', pattern: /\ball[- ]time\b/i }
];

/** The words a browser shows, plus the labels it reads out.
 *
 * Scripts go first, because the SvelteKit data payload carries every string the
 * server sent and matching it would report a sentence twice. Comments go with
 * them: a comment is not a claim, and the compiler drops them from a production
 * build anyway. Every other attribute value goes too - a `data-` attribute is
 * how the specs read a number, not something an operator is told.
 *
 * `aria-label` stays, because it is the only text a person gets from the window
 * strip, and it carried "in all" over a windowed sum.
 */
export function shownText(html: string): string {
	const labels: string[] = [];
	const body = html
		.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
		.replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<[^>]*>/g, (tag) => {
			for (const found of tag.matchAll(/\baria-label="([^"]*)"/gi)) labels.push(found[1]);
			return ' ';
		});
	return [body, ...labels]
		.join(' ')
		.replace(/&quot;/g, '"')
		.replace(/&#3[49];/g, "'")
		.replace(/&amp;/g, '&')
		.replace(/&[a-z]+;/gi, ' ')
		.replace(/\s+/g, ' ');
}

/** The sentence a match sits in, so a failure names the string to go and fix. */
function around(text: string, at: number): string {
	return text.slice(Math.max(0, at - 90), at + 90).trim();
}

for (const route of ROUTES) {
	test(`THE ORACLE: /${route}/ claims nothing over a span it did not read`, () => {
		const html = readFileSync(resolve(BUILD, route, 'index.html'), 'utf8');
		const text = shownText(html);
		// A document that lost its text would pass every pattern below without
		// reading a word of the console.
		expect(text.length, `/${route}/ rendered no text at all`).toBeGreaterThan(2000);

		for (const claim of CLAIMS) {
			const found = text.match(claim.pattern);
			expect(
				found === null,
				`/${route}/ makes ${claim.name}: "${around(text, found?.index ?? 0)}"`
			).toBe(true);
		}
	});
}

test('the oracle reads what a person reads, and only that', () => {
	const page = [
		'<!-- a comment that has never been read by anyone -->',
		'<script>const note = "the ledger has ever carried this";</script>',
		'<style>.a::after { content: "in all"; }</style>',
		'<p data-note="feeds have never failed">Every run, whenever it lands, however slow.</p>',
		'<svg aria-label="9 in all"></svg>'
	].join('');
	const text = shownText(page);

	// The three places a claim can hide from an operator are all gone.
	expect(text).not.toContain('has never been read');
	expect(text).not.toContain('has ever carried');
	expect(text).not.toContain('feeds have never failed');
	// The label survives, which is the one attribute an operator is read out.
	expect(text).toContain('9 in all');

	// `every`, `whenever` and `however` all hold `ever`, and none of them is a
	// claim. This is the assertion that would have caught a pattern written
	// without its word boundary.
	const words = 'Every run, whenever it lands, however slow.';
	expect(words).toContain('ever');
	for (const claim of CLAIMS.slice(0, 2)) expect(claim.pattern.test(words)).toBe(false);

	// A rule in the present simple reads over no span, so it is not a claim.
	for (const rule of [
		'Runs are never pooled: two runs of one day draw two marks.',
		'A counterfactual, never a bill, over the last 30 days.',
		'Today is never counted, because the run is still working.'
	]) {
		for (const claim of CLAIMS) {
			expect(claim.pattern.test(rule), `"${rule}" is a rule and not a claim`).toBe(false);
		}
	}

	// And the four shapes it does refuse.
	for (const claim of [
		'12 of 40 feeds have never failed a read.',
		'Nothing from it has ever reached the digest.',
		'9,000 published each day, 270,000 in all.',
		'The all-time total sits under the strip.'
	]) {
		expect(CLAIMS.some((entry) => entry.pattern.test(claim)), `"${claim}" passed`).toBe(true);
	}
});
