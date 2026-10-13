/** A composition's measured columns and caller-authored reference rules. */
import type { ChartToken } from './theme';

export interface StackSeries {
	label: string;
	token: ChartToken;
	/** Null is unmeasured; zero is a measured nothing. */
	values: (number | null)[];
}

export interface StackRule {
	at: number;
	label: string;
	side: 'above' | 'below';
	token: ChartToken;
}
