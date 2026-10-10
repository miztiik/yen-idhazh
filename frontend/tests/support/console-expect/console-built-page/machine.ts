/** Only the shipped Platform Mix first frame is a door panel before row 9. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	scope: 'platform-mix-only',
	doorPanels: { 'platform-mix': '' },
	reservedPanels: ['platform-mix'],
	pendingPanel: {
		selector: '[data-windowed="machine-fleet"]',
		stateAttribute: 'data-fleet-state',
		emptyAttributes: ['data-fleet-from', 'data-fleet-through']
	},
	// Explicit legacy keys are still permitted until row 9 replaces this route's contract.
	pageData: [
		'windows', 'series', 'modelChanges', 'settingsMoved', 'board', 'memory',
		'processorLostByShard', 'processorLostThresholds', 'memoryHeld', 'newestRunId',
		'split', 'machines', 'clocks', 'clocksSvg', 'latency', 'workSvg', 'workGrid',
		'workUnit', 'costSvg', 'costGrid', 'costShape', 'ramp', 'lostDays', 'recording',
		'rate', 'limits', 'shardTimeoutMinutes', 'contextWindow', 'clocksTolerancePct',
		'panelGroups', 'recordNotes', 'console', 'chart'
	]
};
