/** Which shared item failures can affect native planner work or appear in its output? */
import { z } from "zod";
import { ItemHealthFailureCodeSchema } from "./item-health-failure.schema";

export const PlannerItemFailureCodeSchema = ItemHealthFailureCodeSchema.exclude([
  "robots_denied", "robots_unreachable",
]);
export type PlannerItemFailureCode = z.infer<typeof PlannerItemFailureCodeSchema>;
