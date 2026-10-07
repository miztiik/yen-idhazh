/** Runs `check` with this process's clock in `zone`, then puts the starting zone back. Node
 *  reads `TZ` the moment it is set, and deleting it does not bring the old zone back. */
export function inZone(zone: string, check: () => void): void {
	const variable = process.env.TZ;
	const starting = Intl.DateTimeFormat().resolvedOptions().timeZone;
	process.env.TZ = zone;
	try {
		check();
	} finally {
		process.env.TZ = variable ?? starting;
		if (variable === undefined) delete process.env.TZ;
	}
}
