/** How the Chart tab's role row lays out its pills: how many share one line, and how many lines
 * the row takes, in each of the four width bands.
 *
 * The row holds one slot for each role of the chart with the most roles, empty slots included,
 * so a change of chart never changes its height. A line holds the smaller of that count and the
 * band's cap, `console.explorer_role_slots_per_line`, and the row takes as many lines as its slots
 * need. The bands are the ones `console.explorer_readout_lines` uses, cut at
 * `frame.breakpoints_px`. Jony, 2026-10-07.
 */

/** The pills one line holds in each band. */
export function roleSlotsPerLine(mostRoles: number, cap: readonly number[]): number[] {
	return cap.map((slots) => Math.max(1, Math.min(mostRoles, slots)));
}

/** The lines the role row takes in each band. */
export function roleRowLines(mostRoles: number, cap: readonly number[]): number[] {
	return roleSlotsPerLine(mostRoles, cap).map((slots) => Math.ceil(mostRoles / slots));
}
