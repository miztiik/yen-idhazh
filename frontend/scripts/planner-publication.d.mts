/** The native publication handoff preserves the existing named ledger-copy shape. */
export type LedgerPublicationCopy = {
	files: string[];
	indexes: Record<string, string>;
	refused: string[];
	missing: string[];
	logs: string[];
};
export function projectPlannerPublication(copy: LedgerPublicationCopy, stateRoot: string): LedgerPublicationCopy;
