import type { WhowhatGridData } from '../payload/types';

export type WhowhatVisualState = 'idle' | 'loading' | 'ready' | 'failed';

export function whowhatVisualState(
	wanted: string | null,
	settled: string | null,
	loaded: { file: string; data: WhowhatGridData | null } | null
): WhowhatVisualState {
	if (!wanted) return 'idle';
	if (settled !== wanted || !loaded || loaded.file !== wanted) return 'loading';
	return loaded.data === null ? 'failed' : 'ready';
}
