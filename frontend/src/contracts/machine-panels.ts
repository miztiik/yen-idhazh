// Generated from `backend/idhazh/contracts/machine_panels.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Which ledger a machine card was built from.
 *
 * The two answer different questions. The machine record says what a processor
 * can do; the model server's counters say only what it is called. A card that
 * did not say which it came from would let "we never read the instruction set"
 * read as "this machine has none of the watched flags".
 */
export const CARD_SOURCE = ['fingerprint', 'counters'] as const;

export type CardSource = (typeof CARD_SOURCE)[number];

/**
 * One kind of machine, counted over the window.
 *
 * The panel also draws this count day by day. That grain is DERIVED from the
 * `date` every fingerprint row already carries, and is declared nowhere: a
 * field for it would be a second place for the day grain to disagree with
 * itself, written by nothing.
 */
export interface FleetKind {
	identity: MachineIdentity;

	/** Job placements recorded on this kind. A count of what happened, never a rate and never a probability: the share of a future draw is exactly what a lottery refuses to quote. */
	placements: number;
}

/** One machine a run drew, and what it can do. */
export interface MachineCard {
	identity: MachineIdentity;

	/** Which ledger built this card. The machine record carries the instruction set, the cache and the bandwidth; the model server's own counters carry only a processor name, and a card built from them says so rather than drawing twelve absent chips. */
	source?: CardSource;

	/** Family, model and stepping as one string - `25/1/1`. Two machines reporting one model name can differ here, and that difference is the only thing that explains a speed gap between them. */
	part?: string | null;

	/** Every watched flag, present or absent, or nothing at all where the fingerprint never reached this run. Never a subset. */
	flags?: MachineFlag[];

	/** Whether the instruction set was read at all. False is a different fact from a machine that reported none of the watched flags, and drawing twelve absent chips for it would publish the second as the first. */
	flags_recorded?: boolean;

	l3_cache_bytes?: number | null;

	/** Large-block copy bandwidth. Absent where the probe was switched off, which is a different fact from a rate of zero. */
	memcpy_gib_s?: number | null;

	/** The buffer the probe used. It rides beside the rate so the two are read in one sentence: a buffer at or below L3 measured cache. */
	memcpy_probe_mib?: number | null;

	/** Jobs of this run that drew this machine. A job and not a shard: the machine record files one row a job, and a work shard is a job of its own on the platform that hands them out. */
	shards_drawn: number;

	/** Jobs of this run that recorded a machine at all. The denominator. */
	shards_total: number;

	placement?: MachinePlacement | null;
}

/** One chip on a card: a flag, and whether this machine reported it. */
export interface MachineFlag {
	name: WatchedFlag;

	/** Whether the host reported this flag. False draws an outlined chip rather than dropping the flag, because what a machine cannot do is the half a list of what it can do refuses to say. */
	present: boolean;
}

/**
 * What names a machine on this route, and what colour it takes.
 *
 * `key` is the fingerprint where the fingerprint ledger reached this run, and
 * the processor's own model-name string where it did not. Colour is assigned
 * ascending by that key so a machine keeps its stop at every window preset -
 * assigning by speed or by draw count would encode an ordering the ramp does
 * not mean, and assigning by order of first appearance would change a
 * machine's colour when the operator changes the span.
 */
export interface MachineIdentity {
	key: string;

	/** The machine in words, on the row, always. Colour here encodes a fact, so it is semantic and may never be the only carrier of it. */
	name: string;

	/** Which stop of the chart ramp this machine takes, 1-based. 8 is reserved for shards that recorded no machine at all. */
	colour_stop: number;

	/** The machines folded into this row once the ramp ran out, named in words. Empty on every row that is one machine. Never two machines in one colour without the page saying so. */
	folded?: string[];
}

/**
 * Where the platform put this machine, and which microcode it was running.
 *
 * The five cells a processor detail table would have carried, kept behind the
 * card's own disclosure instead. Every one is absent on a machine whose host
 * metadata service did not answer, which is every developer machine.
 */
export interface MachinePlacement {
	vm_size?: string | null;

	vm_location?: string | null;

	vm_zone?: string | null;

	vm_fault_domain?: string | null;

	/** The one cell that moves without anything else moving, so it is the only explanation left for a speed change with no other change. */
	microcode?: string | null;

	/** The host's own `model name` line, unnormalised. The card's heading is a display name, and a display name that dropped a word has to be checkable against what was recorded. */
	cpu_model_raw?: string | null;
}

/**
 * How one machine's shards split their seconds and their tokens.
 *
 * Sum over sum within the machine, never a mean of per-shard rates: averaging
 * ratios weighs a shard that read twenty items like one that read forty. The
 * existing rule, now applied per machine instead of across all of them.
 */
export interface MachineSplit {
	identity: MachineIdentity;

	/** Shards of this machine that reported all four cells. */
	shards: number;

	read_seconds: number;

	write_seconds: number;

	read_tokens: number;

	write_tokens: number;

	read_tokens_per_second?: number | null;

	write_tokens_per_second?: number | null;

	/** How many read tokens one written token costs, on this machine's shards alone. Null unless both rates are known - a ratio against an absent rate is not a ratio. */
	write_cost_ratio?: number | null;
}

/**
 * One instruction-set flag the console draws a chip for.
 *
 * The closed set `WATCHED_FLAGS` already holds, restated as an enum so the
 * generated schema carries the names and the frontend reads them from there
 * rather than typing a second copy. The check below is what makes it a
 * restatement instead of a copy.
 */
export const WATCHED_FLAG = ['amx_bf16', 'amx_int8', 'amx_tile', 'avx2', 'avx512_bf16', 'avx512_fp16', 'avx512_vnni', 'avx512f', 'avx_vnni', 'f16c', 'fma', 'sse4_2'] as const;

export type WatchedFlag = (typeof WATCHED_FLAG)[number];

/** The three machine panels of `/console/machine/`, for one run and one window. */
export interface MachinePanels {
	version?: string;

	/** The run the cards and the split are about. */
	run_id?: string | null;

	date?: string | null;

	machines?: MachineCard[];

	splits?: MachineSplit[];

	fleet?: FleetKind[];

	/** Recorded placements the fleet count was made from. It is printed as the denominator and it is what the drawing threshold is read against. */
	fleet_rows?: number;

	/** Days the fleet count covers. The window, in days. */
	fleet_days?: number;

	/** Whether the machine record is switched on. False is why a panel has nothing, and the panel says so in words that never name the setting. */
	fingerprint_recording?: boolean;
}
