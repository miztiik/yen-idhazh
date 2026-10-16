/** One private day record drives the drawing rule, flow and daily evidence. */
export { chartRule, minutesText, coverageText } from '../../charts/glance';
export { chartFlow } from './drawing-flow';
import type { FlowDay } from './drawing-flow';

export function visualsPublished(days: readonly FlowDay[]): number {
	return days.reduce((total, day) => total + day.published, 0);
}
