/** Which configured producer URI references may native TypeScript events use? */
import { readFile } from "node:fs/promises";
import { z } from "zod";
import { EventSourceSchema } from "./schemas/cloud-event.schema";

const EventSourcesSchema = z.strictObject({
  planner: EventSourceSchema,
  summarizer: EventSourceSchema,
  workflow: EventSourceSchema,
});
export type EventSources = z.infer<typeof EventSourcesSchema>;

export async function loadEventSources(path: string | URL): Promise<EventSources> {
  const raw: unknown = JSON.parse(await readFile(path, "utf8"));
  return EventSourcesSchema.parse(raw);
}
