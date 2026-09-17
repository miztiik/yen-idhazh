/** What a processor is called, in words a person reads off a card.
 *
 * The host reports its own `model name` line and nothing normalises it, so the
 * ledger holds `INTEL(R) XEON(R) PLATINUM 8573C` beside `Intel(R) Xeon(R)
 * 6973P-C`: the same vendor, shouted on one row and not on the next. A card
 * heading that shouted at a reader on one machine and not on another would say
 * something about the machines, and it says nothing about them at all.
 *
 * **Display only.** The raw string is what the ledger holds and what the card's
 * own disclosure prints, so a heading that dropped a word can always be checked
 * against what was recorded.
 *
 * Two things are dropped and both are dropped because they are already on the
 * card as their own figures: the trailing core count and the trailing clock. A
 * duplicate is a thing that can disagree, and the columns are the ones a reader
 * can act on.
 *
 * Pure, and it imports nothing: the browser suite drives it in plain Node.
 */

/** Words that are a vendor's own spelling and are wrong in any other case.
 *
 * Not a `config/` knob. Changing it changes no behaviour a run can take - it
 * decides which brand names survive a case fold, and a brand name is not a
 * preference anybody tunes (Guardrail #6). A new vendor on the fleet adds a
 * word here, in the same commit as the card that first drew it.
 */
const KEPT_UPPER = new Set(['AMD', 'EPYC', 'IBM', 'ARM']);

/** `64-Core Processor`, `96-Core Processor` - the core count, spelled long. */
const TRAILING_CORES = /\s+\d+-core\s+processor\s*$/i;

/** `CPU @ 2.80GHz` - the clock, which is its own column and moves under load. */
const TRAILING_CLOCK = /\s+cpu\s*@\s*[\d.]+\s*[gm]hz\s*$/i;

/** `(R)`, `(TM)`, `(C)` - a trademark mark, in any case. */
const TRADEMARKS = /\((?:r|tm|c)\)/gi;

/** One word of a model name, in the case a reader should see it in.
 *
 * A word holding a digit is a part number - `8573C`, `9V74`, `6973P-C` - and is
 * left exactly as the host spelled it, because a part number is an identifier
 * and case is part of it. Everything else that arrives shouting is title-cased,
 * unless it is one of the words above.
 */
function word(raw: string): string {
	if (/\d/.test(raw)) return raw;
	if (KEPT_UPPER.has(raw.toUpperCase())) return raw.toUpperCase();
	if (raw !== raw.toUpperCase()) return raw;
	return raw.charAt(0) + raw.slice(1).toLowerCase();
}

/** The heading for a machine card. Empty in, empty out - never a placeholder.
 *
 * A caller with no string at all has a different fact to print ("no shard of
 * this run recorded what machine it was on"), and inventing a name here would
 * take that sentence away from it.
 */
export function machineName(raw: string | null): string {
	if (raw === null) return '';
	const trimmed = raw
		.replace(TRADEMARKS, '')
		.replace(TRAILING_CORES, '')
		.replace(TRAILING_CLOCK, '')
		.trim();
	if (trimmed === '') return '';
	return trimmed.split(/\s+/).map(word).join(' ');
}
