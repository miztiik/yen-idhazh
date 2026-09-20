// Generated from `backend/idhazh/contracts/day_validation.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One row of `state/day-validations.csv`: one frozen day, one validator. */
export interface DayValidationReceipt {
	version?: string;

	/** The published day this row is about. */
	date: string;

	/** The length of the day payload that passed. Compared against `os.stat` on a later run, which is what lets an unchanged day be skipped without opening it. A length of zero is not a day. */
	payload_bytes: number;

	/** sha256 over the payload bytes that passed. Taken from the bytes, never derived from anything else. It is what makes two rows about one day detectable as disagreeing after a union merge. */
	payload_digest: string;

	/** The identity of what the day was checked against: both generated schemas plus the source of the functions that do the checking. It moves when any of them moves, so it cannot be left behind by hand. */
	validator_version: string;
}
