/** Only configuration crosses the static page boundary. The browser asks for records. */
import { chartConfig, inferenceConfig, observabilityConfig, runConfig, themeConfig } from '$lib/server/config';

export const prerender = true;

export function load() {
	const observability = observabilityConfig();
	return {
		machineConfig: {
			chart: chartConfig(),
			contextWindow: inferenceConfig().n_ctx,
			jobTimeoutSeconds: runConfig().shard_timeout_minutes * 60,
			recording: observability.host_fingerprint,
			gradients: themeConfig().gradient_enabled,
			rate: {
				currency: observability.cost_currency,
				inputPerMillion: observability.cost_input_per_million,
				outputPerMillion: observability.cost_output_per_million
			}
		}
	};
}
