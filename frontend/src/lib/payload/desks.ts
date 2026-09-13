/** The desks a model proposed rather than a person, mirrored from `config/taxonomy.json`.
 *
 * Empty today, and that is the honest state: `config/taxonomy.json` declares
 * five verticals and a person put all five there. A desk arrives here only once
 * plan 23 row #16's proposal channel promotes one, and `VerticalDef` already
 * carries the `is_auto_discovered` marker this set mirrors.
 *
 * **Held here rather than on the payload.** Whether a desk was proposed is a
 * fact about the vocabulary, not about a day. Freezing it per day would keep a
 * desk folding on every archived day for ever after a person promoted it - the
 * page would be answering a question with last month's answer.
 *
 * `frontend/tests/topics.spec.ts` reads `config/taxonomy.json` and fails on any
 * drift, in either direction. That is what makes this file a handoff rather
 * than a note: plan 23 row #16 cannot land an auto-discovered vertical without
 * the check telling it this rule exists. It reads one fixed-size config file
 * and no collection a run appends to (`CLAUDE.md` section 13).
 */
export const AUTO_DISCOVERED_DESKS: ReadonlySet<string> = new Set<string>();
