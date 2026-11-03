/** How does explicit operation context cross a W3C carrier without a tracing provider? */
import {
  ROOT_CONTEXT, TraceFlags, createTraceState, defaultTextMapGetter, defaultTextMapSetter,
  isSpanContextValid, trace,
} from "@opentelemetry/api";
import { W3CTraceContextPropagator } from "@opentelemetry/core";
import { OperationMetadataSchema } from "./schemas/operation-metadata.schema";
import type { OperationMetadata } from "./schemas/operation-metadata.schema";

export type TraceContextCarrier = Readonly<Record<string, string | string[] | undefined>>;

const propagator = new W3CTraceContextPropagator();

export function readTraceContext(carrier: TraceContextCarrier): OperationMetadata | undefined {
  const extracted = propagator.extract(ROOT_CONTEXT, carrier, defaultTextMapGetter);
  const incoming = trace.getSpanContext(extracted);
  if (!incoming || !isSpanContextValid(incoming)) return undefined;
  const traceState = incoming.traceState?.serialize();
  return OperationMetadataSchema.parse({
    traceId: incoming.traceId,
    spanId: incoming.spanId,
    links: [],
    ...(traceState ? { traceState } : {}),
  });
}

export function writeTraceContext(context: OperationMetadata): Record<string, string> {
  const metadata = OperationMetadataSchema.parse(context);
  const outgoing = trace.setSpanContext(ROOT_CONTEXT, {
    traceId: metadata.traceId,
    spanId: metadata.spanId,
    traceFlags: TraceFlags.NONE,
    ...(metadata.traceState === undefined ? {} : { traceState: createTraceState(metadata.traceState) }),
  });
  const carrier: Record<string, string> = {};
  propagator.inject(outgoing, carrier, defaultTextMapSetter);
  return carrier;
}
