/** Was it quiet, and which day did it fire: one tile a day, in three states, never two.
 *
 * A rare reading has no useful value axis. Auto-scaled, a trivial worst day
 * draws exactly like a severe one; fixed to the threshold, almost every day is
 * a flat line on the floor. So a tile carries a state rather than a height:
 *
 * - `absent` - not recorded: the run predates the column, or the machine did
 *   not answer. Drawn as an empty cell, visibly unlike a quiet one.
 * - `quiet` - recorded, and under the first threshold. An outlined tile.
 * - `fired` - recorded, and at or past the first threshold. A filled tile.
 *
 * **Two states would be the default failure**, because the archive for a new
 * column is mostly absent, and an absence drawn as a quiet day claims a clean
 * machine on every run that predates its own instrument.
 *
 * **Two thresholds, and both are the caller's, from config.** The first decides
 * whether a tile fills and is checked against every state it is handed; the
 * second decides whether a day is worth naming in the panel's headline. One
 * threshold cannot do both: a bar low enough to catch a day worth looking at is
 * far too low to be worth a sentence.
 */

export type TileState = 'quiet' | 'fired' | 'absent';

export interface TileInput {
	/** A UTC day, `YYYY-MM-DD`. */
	date: string;
	state: TileState;
	reading?: number;
}

export interface TileOptions {
	/** The fill threshold, then the naming threshold. The first may not sit
	 * above the second. */
	thresholds?: readonly [number, number];
}

export interface Tile {
	date: string;
	state: TileState;
	reading: number | null;
	/** At or past the naming threshold. */
	named: boolean;
}

export interface TileGeometry {
	/** One tile a day, oldest first. */
	tiles: Tile[];
	counts: Record<TileState, number>;
	/** The day to name in the headline: the highest reading at or past the
	 * naming threshold, the newest of any tie. Null where no day reached it. */
	worst: Tile | null;
}

export interface TileWindow {
	tiles: Tile[];
	offset: number;
	earlier: Record<TileState, number>;
	overflow: string | null;
}

/** Only the newest days that fit; the count below still accounts for every day. */
export function tileWindow(geometry: TileGeometry, width: number, minPx?: number, gapPx = 2): TileWindow {
	if (minPx !== undefined && (!Number.isFinite(minPx) || minPx <= 0)) throw new Error('tile_min_px must be positive.');
	const count = minPx === undefined ? geometry.tiles.length : Math.max(1, Math.floor((width + gapPx) / (minPx + gapPx)));
	const offset = Math.max(0, geometry.tiles.length - count);
	const earlier: Record<TileState, number> = { fired: 0, quiet: 0, absent: 0 };
	for (const tile of geometry.tiles.slice(0, offset)) earlier[tile.state] += 1;
	return {
		tiles: geometry.tiles.slice(offset),
		offset,
		earlier,
		overflow: offset === 0 ? null : `${offset} earlier days: ${earlier.fired} fired, ${earlier.quiet} quiet, ${earlier.absent} not recorded.`
	};
}

/** The strip, or null where there are no days or nothing was recorded on any. */
export function tileStrip(tiles: readonly TileInput[], opts: TileOptions = {}): TileGeometry | null {
	if (opts.thresholds === undefined && tiles.some((tile) => tile.reading !== undefined)) {
		throw new Error('A tile with a reading needs fill and naming thresholds.');
	}
	const [marked, named] = opts.thresholds ?? [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY];
	if (!(marked <= named)) {
		throw new RangeError(`The fill threshold ${marked} sits above the naming threshold ${named}.`);
	}
	const days = new Set<string>();
	const placed = tiles.map((input): Tile => {
		if (days.has(input.date)) throw new Error(`Two tiles are both for ${input.date}.`);
		days.add(input.date);
		const reading = input.reading ?? null;
		if (input.state === 'absent' && reading !== null) {
			throw new Error(`${input.date} is not recorded, yet carries a reading of ${reading}.`);
		}
		if (input.state === 'fired' && reading !== null && reading < marked) {
			throw new RangeError(`${input.date} is marked fired at ${reading}, under the fill threshold ${marked}.`);
		}
		if (input.state === 'quiet' && reading !== null && reading >= marked) {
			throw new RangeError(`${input.date} is marked quiet at ${reading}, at or past the fill threshold ${marked}.`);
		}
		return {
			date: input.date,
			state: input.state,
			reading,
			named: input.state === 'fired' && reading !== null && reading >= named
		};
	});
	placed.sort((left, right) => (left.date < right.date ? -1 : left.date > right.date ? 1 : 0));

	const counts: Record<TileState, number> = { quiet: 0, fired: 0, absent: 0 };
	for (const tile of placed) counts[tile.state] += 1;
	if (placed.length === 0 || counts.absent === placed.length) return null;

	let worst: Tile | null = null;
	for (const tile of placed) {
		if (!tile.named) continue;
		if (worst === null || (tile.reading ?? 0) >= (worst.reading ?? 0)) worst = tile;
	}
	return { tiles: placed, counts, worst };
}
