/** Only configuration crosses the static page boundary. The browser asks for records. */
import { chartConfig, observabilityConfig } from '$lib/server/config';

export const prerender = true;

export function load() {
	const observability = observabilityConfig();
	return {
		machineConfig: {
			chart: chartConfig(),
			recording: observability.host_fingerprint
		}
	};
}
