const DISPLAY_UNIT_SYMBOLS: Readonly<Record<string, string>> = {
	w: 'W',
	watt: 'W',
	kw: 'kW',
	kilowatt: 'kW',
	mw: 'MW',
	megawatt: 'MW',
	gw: 'GW',
	gigawatt: 'GW',
	tw: 'TW',
	terawatt: 'TW',
	wh: 'Wh',
	kwh: 'kWh',
	mwh: 'MWh',
	gwh: 'GWh',
	twh: 'TWh',
	g: 'g',
	gram: 'g',
	kg: 'kg',
	kilogram: 'kg',
	t: 't',
	tonne: 't',
	kt: 'kt',
	kilotonne: 'kt',
	mm: 'mm',
	cm: 'cm',
	km: 'km',
	kilometre: 'km',
	kilometer: 'km',
	s: 's',
	second: 's',
	min: 'min',
	minute: 'min',
	hr: 'h',
	hour: 'h',
	day: 'd'
};

/** Return the readable symbol for a unit spelling, or preserve an unknown unit. */
export function displayUnitSymbol(unit: string): string {
	return DISPLAY_UNIT_SYMBOLS[unit] ?? unit;
}
