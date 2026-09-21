/** Which settings moved on which day, in words a reader knows.
 *
 * A dashed rule down a chart already says "everything left of this was written
 * by a different setup". What it could not say is WHAT changed, because the
 * thing behind it used to be one digest and a digest affords equality and
 * nothing else. Since 2026-09-12 a run records its inputs field by field, so
 * the same comparison can name them - and "the prompt and the context size
 * moved" is a finding where "something moved" is only a warning.
 *
 * **No new column.** The run record already carries every field below and the
 * manifest reader already passes it through as `RunRecord.inputs`. A second
 * copy on the item row would be a fact that can disagree with itself.
 *
 * **One entry a date, never one a setting.** A day is one column on every chart
 * that draws a rule, so a day that moved five settings is one entry naming five
 * of them rather than five entries a reader has to count.
 *
 * Relative imports only, and nothing from `$lib/server`: a panel draws this, so
 * the module has to be loadable in a browser bundle and in plain Node. That is
 * why the cutover date and the run-day shape live here rather than beside the
 * boundary derivation that also reads them.
 */

/** The slice of a published day's runs both derivations need.
 *
 * Structural rather than imported, so `RunSummary` from the payload loader
 * satisfies it and this module goes on importing nothing at all.
 */
export interface RecordedRunDay {
	date: string;
	records: readonly { inputs: unknown }[];
}

/** Every input the run record enumerates, and the words a reader gets for it.
 *
 * Declaration order is `PipelineInputs`' own, so a readout naming several reads
 * in the order the contract writes them rather than in an order that changes
 * with the data. The keys must cover that contract exactly -
 * `frontend/tests/console-settings-moved.spec.ts` reads
 * `schemas/run-manifest.schema.json` and fails on a field with no words or
 * words with no field, so a field added next month cannot go unnamed.
 *
 * The words are not the field names. `n_ctx` is what the runtime calls it and
 * "the context size" is what it is, and a term from a subsystem is not a term
 * for a user (`CLAUDE.md` section 0b).
 */
export const SETTING_WORDS: Readonly<Record<string, string>> = {
	model_sha256: 'the weights',
	quantisation: 'the weight precision',
	runtime_build: 'the model runtime build',
	chat_template_sha256: 'the chat template',
	prompt_sha256: 'the prompt',
	turn_markers_sha256: 'the turn markers',
	output_schema_sha256: 'the reply shape',
	truncation_cap_tokens: 'the truncation cap',
	sampling: 'the sampling settings',
	runtime_flags: 'the model server switches',
	n_ctx: 'the context size',
	n_batch: 'the batch size',
	n_ubatch: 'the micro-batch size',
	n_threads: 'the thread count',
	runner_class: 'the kind of machine it asked for',
	extractor_version: 'the article extractor',
	sanitizer_version: 'the sanitizer'
};

/** What one day's record says moved since the last day that kept one. */
export interface SettingsMoved {
	date: string;
	/** In words, in contract order. Empty is possible and is not a bug: a day
	 * can run a combination no earlier day ran while every single value it used
	 * was one yesterday used too, and then the boundary is real with nothing to
	 * name. The readout falls back to the sentence that names no field. */
	settings: string[];
}

/** Every day the recorded inputs named a value the last recorded day did not.
 *
 * The same rule the whole-manifest boundary uses, asked once per field: a day
 * is a change when it ran something the previous RECORDED day did not run, and
 * a day that only stopped using one of yesterday's values changed nothing. The
 * comparison is between consecutive recorded days, so a day with no record is
 * skipped rather than read as a day nothing moved on (`CLAUDE.md` Guardrail
 * #10, and the same refusal Row #10 made of a zero theft figure).
 *
 * A run that recorded no inputs is skipped by the check below rather than by a
 * date. Before the record existed every run carries a null, so the two rules
 * remove the same days - and the check says why the day is skipped where a date
 * could only say when.
 */
export function settingsMoved(runs: readonly RecordedRunDay[]): SettingsMoved[] {
	const names = Object.keys(SETTING_WORDS);
	const byDate = new Map<string, Map<string, Set<string>>>();
	for (const day of runs) {
		for (const record of day.records) {
			const inputs = record.inputs;
			if (inputs === null || inputs === undefined || typeof inputs !== 'object') continue;
			const held = byDate.get(day.date) ?? new Map<string, Set<string>>();
			for (const name of names) {
				const values = held.get(name) ?? new Set<string>();
				// Serialised, so an absent key and a recorded null are one value and a
				// number and its own spelling as a string are not.
				values.add(JSON.stringify((inputs as Record<string, unknown>)[name] ?? null));
				held.set(name, values);
			}
			byDate.set(day.date, held);
		}
	}
	const dates = [...byDate.keys()].sort();
	const moved: SettingsMoved[] = [];
	for (let index = 1; index < dates.length; index += 1) {
		const before = byDate.get(dates[index - 1]) as Map<string, Set<string>>;
		const now = byDate.get(dates[index]) as Map<string, Set<string>>;
		const changed = names.filter((name) =>
			[...(now.get(name) ?? new Set<string>())].some(
				(value) => !(before.get(name) ?? new Set<string>()).has(value)
			)
		);
		if (changed.length > 0) {
			moved.push({ date: dates[index], settings: changed.map((name) => SETTING_WORDS[name]) });
		}
	}
	return moved;
}

/** The words for each date, for a chart asking once a column. */
export function settingsByDate(moved: readonly SettingsMoved[]): Map<string, string[]> {
	return new Map(moved.map((one) => [one.date, one.settings]));
}

/** A list as a person writes one: "a", "a and b", "a, b and c".
 *
 * An Oxford comma is not used, because the surrounding sentences here do not
 * use one either and one list punctuated differently from the paragraph around
 * it reads as a mistake rather than as a rule.
 */
export function namesMoved(settings: readonly string[]): string {
	if (settings.length === 0) return '';
	if (settings.length === 1) return settings[0];
	return `${settings.slice(0, -1).join(', ')} and ${settings[settings.length - 1]}`;
}

/** What a chart says about a day it covers, that a setting moved on, and that
 * it has no reading for.
 *
 * The most useful state this whole marker has, and the one a missing line
 * cannot express: a setting moved on a day nobody was measuring, so the
 * readings either side of it are a before-and-after across a change that is
 * invisible on the plot. A chart that only drew rules where it had columns
 * would be silent about exactly the days an owner most needs before trusting a
 * comparison.
 *
 * `days` are the dates the chart covers but drew nothing for, newest last.
 */
export function unreadRuleNote(unread: readonly SettingsMoved[]): string {
	if (unread.length === 0) return '';
	const each = unread.map((one) => {
		const what = namesMoved(one.settings);
		return what === '' ? one.date : `${one.date} (${what})`;
	});
	const one = unread.length === 1;
	return `${one ? 'A setting moved' : 'Settings moved'} on ${namesMoved(each)}, and nothing here measured ${
		one ? 'that day' : 'those days'
	}. A reading either side of ${one ? 'it' : 'them'} is a before-and-after across a change this chart cannot draw.`;
}
