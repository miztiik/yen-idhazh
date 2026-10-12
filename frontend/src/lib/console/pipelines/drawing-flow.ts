/** Where the private drawing record's items went, conserving each named loss. */
import type { ChartToken } from '../../charts/theme';

export interface FlowDay {
	reached: number;
	asked: number;
	drafted: number;
	published: number;
}

const STAGES = [
	{ key: 'reached', label: 'Reached', token: '--chart-1' },
	{ key: 'asked', label: 'Asked the model', token: '--chart-2' },
	{ key: 'drafted', label: 'Drafted', token: '--chart-3' },
	{ key: 'published', label: 'Published', token: '--chart-4' }
] as const satisfies readonly { key: keyof FlowDay; label: string; token: ChartToken }[];

const LOSSES = ['Answered without a visual', 'The model drew nothing', 'Did not survive the checks'];

export interface FlowStep {
	label: string;
	value: number;
	/** Whole percent of everything that reached chart drawing. */
	share: number;
	token: ChartToken;
	/** No branch for a zero loss or for the final stage. */
	lost: { label: string; value: number; share: number } | null;
}

export interface ChartFlow {
	empty: boolean;
	reason: string | null;
	steps: FlowStep[];
}

export function chartFlow(days: readonly FlowDay[]): ChartFlow {
	const total = STAGES.map((stage) => ({
		...stage,
		value: days.reduce((sum, day) => sum + day[stage.key], 0)
	}));
	const reached = total[0].value;
	if (reached === 0) {
		return {
			empty: true,
			steps: [],
			reason:
				'Nothing committed says what the visual planner did over this window, so there is ' +
				'no flow to draw.'
		};
	}

	// A visual can have been drafted before the window opened. A negative loss
	// cannot describe that flow; the daily table still carries its real counts.
	const gained = total.findIndex((stage, i) => i > 0 && stage.value > total[i - 1].value);
	if (gained > 0) {
		return {
			empty: true,
			steps: [],
			reason:
				`This window counts more items at ${total[gained].label.toLowerCase()} than at ` +
				`${total[gained - 1].label.toLowerCase()}, so the counts are not one flow. A visual ` +
				'published inside the window can have been drafted before it opened. The table ' +
				'below holds the numbers.'
		};
	}

	const share = (value: number) => Math.round((value / reached) * 100);
	return {
		empty: false,
		reason: null,
		steps: total.map((stage, i) => {
			const dropped = i === total.length - 1 ? 0 : stage.value - total[i + 1].value;
			return {
				label: stage.label,
				value: stage.value,
				share: share(stage.value),
				token: stage.token,
				lost: dropped > 0 ? { label: LOSSES[i], value: dropped, share: share(dropped) } : null
			};
		})
	};
}
