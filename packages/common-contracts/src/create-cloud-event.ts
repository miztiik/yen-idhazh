/** How is a new event occurrence created for an already allocated operation? */
import { randomUUID } from "node:crypto";
import { readCloudEvent } from "./read-cloud-event";
import { writeTraceContext } from "./propagate-trace-context";
import type { CloudEvent } from "./schemas/cloud-event.schema";
import type { OperationMetadata } from "./schemas/operation-metadata.schema";

export type CreateCloudEventInput<T> = {
  source: string;
  type: string;
  context: OperationMetadata;
  data: unknown;
  parseData: (value: unknown) => T;
};

export function createCloudEvent<T>(input: CreateCloudEventInput<T>): CloudEvent<T> {
  return readCloudEvent({
    specversion: "1.0",
    id: randomUUID(),
    source: input.source,
    type: input.type,
    time: new Date().toISOString(),
    datacontenttype: "application/json",
    ...writeTraceContext(input.context),
    data: input.data,
  }, input.parseData);
}
