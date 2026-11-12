/** Which console-only style values does the CSS producer consume? */

export const CONSOLE_FONT_FACES = ['inter', 'system-sans', 'system-mono'] as const;
export const CONSOLE_LINECAPS = ['butt', 'round', 'square'] as const;
export type ConsoleFontFace = (typeof CONSOLE_FONT_FACES)[number];

export interface ConsoleColors {
	canvas: string;
	inset: string;
	surface: string;
	raised: string;
	text: string;
	text_secondary: string;
	text_tertiary: string;
	rule: string;
	rule_strong: string;
	accent: string;
	accent_hover: string;
	on_accent: string;
	focus: string;
	selected: string;
	chart_axis: string;
	chart_grid: string;
	/** Custom category colours; the last slot remains neutral under every palette choice. */
	categorical: string[];
}

export interface ConsoleType {
	size_rem: number;
	leading_rem: number;
	weight: number;
	tracking_em: number;
}

export interface ConsoleShadow {
	y_px: number;
	blur_px: number;
	alpha: number;
}

export interface ConsoleStyleConfig {
	colors: { light: ConsoleColors; dark: ConsoleColors };
	typography: {
		ui_face: ConsoleFontFace;
		heading_face: ConsoleFontFace;
		data_face: ConsoleFontFace;
		small: ConsoleType;
		body: ConsoleType;
		control: ConsoleType;
		panel_title: ConsoleType;
		page_title: ConsoleType;
		value: ConsoleType;
	};
	layout: {
		rail_width_rem: number;
		header_min_height_rem: number;
		rail_padding_rem: number;
		rail_gap_rem: number;
		content_gap_rem: number;
		control_min_height_rem: number;
		control_padding_inline_rem: number;
		control_padding_block_rem: number;
		control_gap_rem: number;
		panel_padding_rem: number;
		panel_gap_rem: number;
		group_gap_rem: number;
		columns_wide: number;
	};
	radii: { control_rem: number; panel_rem: number };
	elevation: {
		light: { panel: ConsoleShadow; floating: ConsoleShadow };
		dark: { panel: ConsoleShadow; floating: ConsoleShadow };
	};
	chart: {
		axis_width_px: number;
		grid_width_px: number;
		line_width_px: number;
		grid_opacity: number;
		grid_dash_px: number[] | null;
		linecap: (typeof CONSOLE_LINECAPS)[number];
	};
}

export type ConsoleStyleInput = {
	[K in keyof ConsoleStyleConfig]?: K extends 'colors'
		? { [M in 'light' | 'dark']?: Partial<ConsoleColors> }
		: K extends 'typography'
			? {
					[P in keyof ConsoleStyleConfig['typography']]?:
						ConsoleStyleConfig['typography'][P] extends ConsoleType
							? Partial<ConsoleType>
							: ConsoleStyleConfig['typography'][P];
				}
			: K extends 'elevation'
				? { [M in 'light' | 'dark']?: { panel?: Partial<ConsoleShadow>; floating?: Partial<ConsoleShadow> } }
				: Partial<ConsoleStyleConfig[K]>;
};

export const CONSOLE_STYLE_DEFAULTS: ConsoleStyleConfig = {
	colors: {
		light: {
			canvas: '#f2f1ed', inset: '#e9e7e1', surface: '#fffefa', raised: '#ffffff',
			text: '#25251f', text_secondary: '#625e55', text_tertiary: '#746f64',
			rule: '#dad6cb', rule_strong: '#b6afa0', accent: '#276419',
			accent_hover: '#1b4612', on_accent: '#ffffff', focus: '#8e0152',
			selected: '#e6f5d0', chart_axis: '#b6afa0', chart_grid: '#dad6cb',
			categorical: ['#356a9a', '#7d53a0', '#167f99', '#a3427c', '#5968af', '#29739e', '#995aab', '#777268']
		},
		dark: {
			canvas: '#191917', inset: '#151513', surface: '#22221f', raised: '#2b2b27',
			text: '#f0ede5', text_secondary: '#c1bcb1', text_tertiary: '#a39c8f',
			rule: '#393932', rule_strong: '#565348', accent: '#b8e186',
			accent_hover: '#e6f5d0', on_accent: '#122722', focus: '#de77ae',
			selected: '#1b4612', chart_axis: '#565348', chart_grid: '#393932',
			categorical: ['#8bbce5', '#bea2df', '#72c6d9', '#e6a1c9', '#a4b1e8', '#83bfdc', '#cea4e0', '#b0aa9e']
		}
	},
	typography: {
		ui_face: 'inter', heading_face: 'inter', data_face: 'inter',
		small: { size_rem: 0.75, leading_rem: 1, weight: 400, tracking_em: 0 },
		body: { size_rem: 0.875, leading_rem: 1.25, weight: 400, tracking_em: 0 },
		control: { size_rem: 0.875, leading_rem: 1.25, weight: 500, tracking_em: 0 },
		panel_title: { size_rem: 1, leading_rem: 1.5, weight: 600, tracking_em: -0.01 },
		page_title: { size_rem: 1.5, leading_rem: 2, weight: 600, tracking_em: -0.02 },
		value: { size_rem: 1.75, leading_rem: 2, weight: 600, tracking_em: -0.02 }
	},
	layout: {
		rail_width_rem: 12, header_min_height_rem: 3.5,
		rail_padding_rem: 1, rail_gap_rem: 0.5, content_gap_rem: 1.5,
		control_min_height_rem: 2.75, control_padding_inline_rem: 0.75,
		control_padding_block_rem: 0.25, control_gap_rem: 0.5,
		panel_padding_rem: 1, panel_gap_rem: 1, group_gap_rem: 1.5, columns_wide: 2
	},
	radii: { control_rem: 0.25, panel_rem: 0.5 },
	elevation: {
		light: { panel: { y_px: 1, blur_px: 2, alpha: 0.06 }, floating: { y_px: 6, blur_px: 16, alpha: 0.12 } },
		dark: { panel: { y_px: 0, blur_px: 0, alpha: 0 }, floating: { y_px: 0, blur_px: 0, alpha: 0 } }
	},
	chart: { axis_width_px: 1, grid_width_px: 1, line_width_px: 2, grid_opacity: 1, grid_dash_px: null, linecap: 'round' }
};

/** Native validation owns legality; this copy preserves missing-leaf defaults. */
export function resolveConsoleStyle(input: ConsoleStyleInput = {}): ConsoleStyleConfig {
	const defaults = CONSOLE_STYLE_DEFAULTS;
	const type = input.typography;
	const depth = input.elevation;
	return {
		colors: {
			light: { ...defaults.colors.light, ...input.colors?.light },
			dark: { ...defaults.colors.dark, ...input.colors?.dark }
		},
		typography: {
			...defaults.typography, ...type,
			small: { ...defaults.typography.small, ...type?.small },
			body: { ...defaults.typography.body, ...type?.body },
			control: { ...defaults.typography.control, ...type?.control },
			panel_title: { ...defaults.typography.panel_title, ...type?.panel_title },
			page_title: { ...defaults.typography.page_title, ...type?.page_title },
			value: { ...defaults.typography.value, ...type?.value }
		},
		layout: { ...defaults.layout, ...input.layout },
		radii: { ...defaults.radii, ...input.radii },
		elevation: {
			light: {
				panel: { ...defaults.elevation.light.panel, ...depth?.light?.panel },
				floating: { ...defaults.elevation.light.floating, ...depth?.light?.floating }
			},
			dark: {
				panel: { ...defaults.elevation.dark.panel, ...depth?.dark?.panel },
				floating: { ...defaults.elevation.dark.floating, ...depth?.dark?.floating }
			}
		},
		chart: { ...defaults.chart, ...input.chart }
	};
}
