/** Which effective harvest configuration belongs to one validated plan request? */
import { loadHarvestInputs } from "./harvest-feeds/load-harvest-inputs";
import type { PlanInputs } from "./load-plan-inputs";
import type { resolvePlanRequest } from "./api/plan-request";

export function resolvePlanningInputs(
  inputs: PlanInputs, request: ReturnType<typeof resolvePlanRequest>,
) {
  return loadHarvestInputs({
    config: { ...inputs.harvest.config, curate_articles: { ...inputs.harvest.config.curate_articles, article_limit: request.article_limit } },
    taxonomy: inputs.harvest.registry,
    sources: {
      feeds: inputs.harvest.sources, retired: inputs.harvest.retired_sources,
      publishers: inputs.harvest.publishers,
    },
    extraction: { ...inputs.harvest.extraction_settings, extract: inputs.harvest.extraction },
  });
}
