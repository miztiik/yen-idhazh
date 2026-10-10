/** Pipelines reports its window on ten surfaces and its two stacked charts. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: [
		'band-distance',
		'chart-drawing',
		'extraction',
		'failure-mix',
		'failure-rate',
		'item-cost',
		'run-health',
		'site-cost-per-item',
		'telemetry-viewport',
		'time-split'
	],
	dailyTable: true,
	panelCases: [
		{ state: 'two items failed and one was timed', mix: { 1: 1, 7: 7 }, split: { 1: 1, 7: 7 } },
		{
			state: 'three items were timed and none failed',
			mix: {
				1: 'Nothing failed in this one day, out of 3 items planned.',
				7: 'Nothing failed in these 7 days, out of 21 items planned.'
			},
			split: { 1: 1, 7: 7 }
		},
		{
			state: 'one item failed and two had no end-to-end clock',
			mix: { 1: 1, 7: 7 },
			split: {
				1: 'No item was timed from start to finish in this one day, so there is no time to split.',
				7: 'No item was timed from start to finish in these 7 days, so there is no time to split.'
			}
		},
		{
			state: 'no item was planned',
			mix: {
				1: 'No item was planned in this one day, so nothing could fail.',
				7: 'No item was planned in these 7 days, so nothing could fail.'
			},
			split: {
				1: 'No item was planned in this one day, so there is no time to split.',
				7: 'No item was planned in these 7 days, so there is no time to split.'
			}
		}
	],
	panelWords: {
		'failure-mix': {
			section: {
				1: 'What is failing, by stage, over 1 day',
				7: 'What is failing, by stage, over 7 days'
			},
			chart: {
				1: "Failures by stage in this one day. The column's height is the day's failures, and the bands are the stages they stopped at. Drawn as lines instead, each stage is its own count and the total is not shown.",
				7: "Failures per day by stage, over 7 days. One column is one day, its height is that day's failures, and the bands are the stages they stopped at. A day with no column is a day on which nothing was planned or nothing failed, and the numbers below the chart say which. Drawn as lines instead, each stage is its own count a day and the total is not shown."
			},
			empty: '[data-mix-empty]'
		},
		'time-split': {
			section: {
				1: "Where an item's time went, over 1 day",
				7: "Where an item's time went, over 7 days"
			},
			chart: {
				1: "Mean milliseconds an item spent in each step, in this one day. The column's height is the mean item's whole clock. The bands from the bottom are fetch, extract, the label call, the summary, the visual plan, the model time neither call claimed, the faithfulness scorers, and at the top the time no named step claimed. Drawn as lines instead, each step is its own milliseconds and the whole clock is not shown.",
				7: "Mean milliseconds an item spent in each step, per day, over 7 days. One column is one day and its height is the mean item's whole clock. A day with no column is a day on which no item was timed from start to finish. The bands from the bottom are fetch, extract, the label call, the summary, the visual plan, the model time neither call claimed, the faithfulness scorers, and at the top the time no named step claimed. Drawn as lines instead, each step is its own milliseconds a day and the whole clock is not shown."
			},
			empty: '[data-time-split-empty]'
		}
	}
};
