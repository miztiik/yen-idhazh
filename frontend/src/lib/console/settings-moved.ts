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
 * `RunManifest` and fails on a field with no words or
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

/** The two inputs that are many settings rather than one.
 *
 * Each is a mapping of one setting to its value, so the comparison below runs
 * per key. Joined into one string they moved as a block: renaming a key or
 * dropping a setting read as every decode parameter changing at once, on a day
 * when nothing about the decode had moved at all.
 */
const KEYED_SETTINGS: readonly string[] = ['sampling', 'runtime_flags'];

/** What this project called each runtime switch before the model file carried
 * llama-server's own flags, and what the same switch is called now.
 *
 * **This table is closed and cannot grow.** It names spellings that existed in
 * records written before 2026-09-22 and nowhere else; the writer stopped
 * emitting every one of them on that day. `RENAMED_FLAGS` in
 * `backend/idhazh/contracts/fingerprint.py` is the same table for the same
 * reason, and two copies of a set that will never gain a member cannot drift.
 */
const RENAMED_FLAGS: Readonly<Record<string, string>> = {
	cache_type_k: '-ctk',
	cache_type_v: '-ctv',
	flash_attention: '-fa',
	n_parallel: '-np',
	n_threads_batch: '-tb',
	checkpoint_min_step: '-cms',
	ctx_checkpoints: '-ctxcp',
	cache_ram: '-cram',
	slot_prompt_similarity: '-sps'
};

/** The three that were one boolean and became a pair of flags. True took the
 * positive flag and false the `--no-` one, and a flag carries no value of its
 * own, so both sides record `set` or `runtime-default`. */
const SPLIT_FLAGS: Readonly<Record<string, readonly [string, string]>> = {
	cache_prompt: ['--cache-prompt', '--no-cache-prompt'],
	jinja: ['--jinja', '--no-jinja'],
	reasoning_preserve: ['--reasoning-preserve', '--no-reasoning-preserve']
};

/** The words for one setting inside a keyed block, per block, in the order a
 * readout names them.
 *
 * `-ctk` is what llama-server calls it and "the key cache precision" is what it
 * is; a term from a subsystem is not a term for a user (`CLAUDE.md` section
 * 0b). A key with no words here falls back to its block's own words, so a
 * switch added next month reads as "the model server switches" rather than as
 * nothing - unnamed is worse than coarse.
 *
 * The order is this table's, never the record's. A readout whose order changes
 * with the data is a readout a reader cannot scan twice.
 */
export const SETTING_KEY_WORDS: Readonly<Record<string, Readonly<Record<string, string>>>> = {
	sampling: {
		temperature: 'the sampling temperature',
		top_p: 'the sampling cut-off',
		seed: 'the sampling seed'
	},
	runtime_flags: {
		'-ctk': 'the key cache precision',
		'-ctv': 'the value cache precision',
		'-fa': 'the attention kernel',
		'-np': 'the slot count',
		'-tb': 'the prompt thread count',
		'-cms': 'the checkpoint step',
		'-ctxcp': 'the checkpoint count',
		'-cram': 'the cache memory',
		'-sps': 'the slot reuse threshold',
		'--cache-prompt': 'prompt caching',
		'--no-cache-prompt': 'prompt caching',
		'--jinja': 'template rendering',
		'--no-jinja': 'template rendering',
		'--reasoning-preserve': 'reasoning preservation',
		'--no-reasoning-preserve': 'reasoning preservation'
	}
};

/** Every word a readout can use, in the order it uses them.
 *
 * A block that holds many settings contributes its own keys in place of itself,
 * so the whole list is one declared order rather than two rules a reader has to
 * hold at once.
 */
export const WORDS_IN_ORDER: readonly string[] = Object.keys(SETTING_WORDS).flatMap((name) =>
	KEYED_SETTINGS.includes(name)
		? [...new Set(Object.values(SETTING_KEY_WORDS[name])), SETTING_WORDS[name]]
		: [SETTING_WORDS[name]]
);

/** One recorded settings block as the pairs it holds, whichever way it was written.
 *
 * Both blocks were one `a=1;b=2` string until 2026-09-22 and a published day is
 * never rewritten, so every day before that is read here and nowhere else. The
 * split is the whole of it for `sampling`; `runtime_flags` needs the rename
 * table on top, because the switches took llama-server's own names the day
 * before the shape changed.
 */
function pairsOf(name: string, recorded: unknown): Record<string, string> {
	const pairs: Record<string, string> = {};
	if (recorded !== null && typeof recorded === 'object') {
		for (const [key, value] of Object.entries(recorded as Record<string, unknown>)) {
			pairs[key] = JSON.stringify(value);
		}
		return pairs;
	}
	if (typeof recorded !== 'string') return pairs;
	for (const term of recorded.split(';')) {
		const at = term.indexOf('=');
		if (at <= 0) continue;
		const key = term.slice(0, at);
		const value = term.slice(at + 1);
		if (name !== 'runtime_flags') {
			pairs[key] = JSON.stringify(value);
			continue;
		}
		const split = SPLIT_FLAGS[key];
		if (split === undefined) {
			pairs[RENAMED_FLAGS[key] ?? key] = JSON.stringify(value);
			continue;
		}
		const asked = value.trim().toLowerCase() === 'true';
		pairs[split[0]] = JSON.stringify(asked ? 'set' : 'runtime-default');
		pairs[split[1]] = JSON.stringify(asked ? 'runtime-default' : 'set');
	}
	return pairs;
}

/** Every field of one record, flattened to the names the comparison asks about.
 *
 * A keyed block becomes one entry per setting, named `sampling.temperature`.
 * Everything else keeps its own name and its serialised value, so an absent key
 * and a recorded null are one value and a number and its own spelling as a
 * string are not.
 */
export function comparableInputs(inputs: unknown): Map<string, string> {
	const flat = new Map<string, string>();
	if (inputs === null || typeof inputs !== 'object') return flat;
	const record = inputs as Record<string, unknown>;
	for (const name of Object.keys(SETTING_WORDS)) {
		if (!KEYED_SETTINGS.includes(name)) {
			flat.set(name, JSON.stringify(record[name] ?? null));
			continue;
		}
		const pairs = pairsOf(name, record[name]);
		// The words table's order first, then whatever the record holds that it
		// does not name, so a key nobody has words for is still compared.
		const known = Object.keys(SETTING_KEY_WORDS[name]);
		const rest = Object.keys(pairs)
			.filter((key) => !known.includes(key))
			.sort();
		for (const key of [...known, ...rest]) {
			if (key in pairs) flat.set(`${name}.${key}`, pairs[key]);
		}
	}
	return flat;
}

/** The words for one comparison name, keyed or not. */
function wordsFor(name: string): string {
	const at = name.indexOf('.');
	if (at < 0) return SETTING_WORDS[name];
	const field = name.slice(0, at);
	return SETTING_KEY_WORDS[field][name.slice(at + 1)] ?? SETTING_WORDS[field];
}

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
 * The same rule the whole-manifest boundary uses, asked once per setting: a day
 * is a change when it ran something the previous RECORDED day did not run, and
 * a day that only stopped using one of yesterday's values changed nothing. The
 * comparison is between consecutive recorded days, so a day with no record is
 * skipped rather than read as a day nothing moved on (`CLAUDE.md` Guardrail
 * #10, and the same refusal Row #10 made of a zero theft figure).
 *
 * **Once per setting rather than once per field**, because two of the fields
 * hold many settings each. Compared whole they moved as a block, so the day the
 * model file took llama-server's own flag names read as every switch changing
 * at once - a permanent rule on a published day where the decode had not moved.
 * Per key, a renamed switch compares against itself and a setting that stopped
 * being sent is a key that is absent, which this rule already treats as no
 * change.
 *
 * A run that recorded no inputs is skipped by the check below rather than by a
 * date. Before the record existed every run carries a null, so the two rules
 * remove the same days - and the check says why the day is skipped where a date
 * could only say when.
 */
export function settingsMoved(runs: readonly RecordedRunDay[]): SettingsMoved[] {
	const byDate = new Map<string, Map<string, Set<string>>>();
	for (const day of runs) {
		for (const record of day.records) {
			const inputs = record.inputs;
			if (inputs === null || inputs === undefined || typeof inputs !== 'object') continue;
			const held = byDate.get(day.date) ?? new Map<string, Set<string>>();
			for (const [name, value] of comparableInputs(inputs)) {
				const values = held.get(name) ?? new Set<string>();
				values.add(value);
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
		const changed = [...now.keys()].filter((name) =>
			[...(now.get(name) ?? new Set<string>())].some(
				(value) => !(before.get(name) ?? new Set<string>()).has(value)
			)
		);
		// One entry a setting, deduplicated: a boolean that became a pair of flags
		// moves both halves together and is one thing a reader changed.
		const settings = [...new Set(changed.map(wordsFor))];
		if (settings.length > 0) {
			moved.push({ date: dates[index], settings });
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

/** How many settings a readout names before it starts counting instead.
 *
 * Three, because a strip row is one line and a fourth name is what pushes it
 * onto a second. Seventeen inputs can move on one day, and a day that moved
 * seven of them is the day a reader most needs the row to stay readable.
 */
export const NAMES_SHOWN = 3;

/** The same list, cut to what fits on one line.
 *
 * "a, b and c" up to the cap, then "a, b, c and 4 more". The count is kept
 * rather than dropped: a reader who sees three names and no number cannot tell
 * a day that moved three settings from one that moved seven, and those are
 * different days.
 */
export function namesMovedShort(settings: readonly string[]): string {
	if (settings.length <= NAMES_SHOWN) return namesMoved(settings);
	const shown = settings.slice(0, NAMES_SHOWN).join(', ');
	return `${shown} and ${settings.length - NAMES_SHOWN} more`;
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
