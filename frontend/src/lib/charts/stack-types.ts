/** A caller-authored reference rule: where it crosses the plot, its words and its colour. */
import type { ChartToken } from './theme';

export interface StackRule {
	at: number;
	label: string;
	side: 'above' | 'below';
	token: ChartToken;
}
