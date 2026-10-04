import type { LedgerName } from '../../data/slice-shapes';

export type KeptQuestion = {
	id: string;
	name: string;
	statement: string;
	ledgers: readonly LedgerName[];
	days: number;
	updatedAt: string;
};

export type RecentRun = {
	id: string;
	statement: string;
	ledgers: readonly LedgerName[];
	days: number;
	rows: number;
	ms: number;
	askedAt: string;
};

export type SavedQuestionResult = {
	items: readonly KeptQuestion[];
	notice: string | null;
	dropped: KeptQuestion | null;
};

export function suggestedSaveName(statement: string, maxChars: number): string {
	const firstLine = statement.replaceAll('\r\n', '\n').split('\n')[0].trim();
	if (firstLine.length <= maxChars) return firstLine;
	return firstLine.slice(0, Math.max(0, maxChars)).trimEnd();
}

export function keepSavedQuestion(saved: readonly KeptQuestion[], next: KeptQuestion, max: number): SavedQuestionResult {
	const withoutDuplicate = saved.filter((item) => item.id !== next.id);
	const items = [next, ...withoutDuplicate];
	const kept = items.slice(0, Math.max(0, max));
	const dropped = items.length > kept.length ? items[kept.length] : null;
	return {
		items: kept,
		dropped,
		notice: dropped ? `Saved "${next.name}". "${dropped.name}" was the oldest of ${max} and is no longer kept.` : null
	};
}

export function forgetSavedQuestion(saved: readonly KeptQuestion[], id: string): readonly KeptQuestion[] {
	return saved.filter((item) => item.id !== id);
}

export function keepRecentRun(history: readonly RecentRun[], next: RecentRun, max: number): readonly RecentRun[] {
	const withoutDuplicate = history.filter((item) => item.id !== next.id);
	return [next, ...withoutDuplicate].slice(0, Math.max(0, max));
}
