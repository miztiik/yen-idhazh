/** How is a saved event validated without changing its identity, instant or application values? */
import { CloudEventSchema } from "./schemas/cloud-event.schema";
import type { CloudEvent } from "./schemas/cloud-event.schema";

export function readCloudEvent<T>(value: unknown, parseData: (value: unknown) => T): CloudEvent<T> {
  const event = CloudEventSchema.parse(value);
  return { ...event, data: parseData(event.data) };
}
