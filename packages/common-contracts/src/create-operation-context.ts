/** How is a fresh operation placed in an explicit execution and parent context? */
import { randomBytes } from "node:crypto";
import { OperationMetadataSchema } from "./schemas/operation-metadata.schema";
import type { OperationLink, OperationMetadata } from "./schemas/operation-metadata.schema";

type ContextOptions = {
  links?: readonly OperationLink[];
  traceState?: string;
};

function createIdentifier(byteLength: number, excluded?: string): string {
  let identifier: string;
  do {
    identifier = randomBytes(byteLength).toString("hex");
  } while (identifier === "0".repeat(byteLength * 2) || identifier === excluded);
  return identifier;
}

export function createRootContext(options: ContextOptions = {}): OperationMetadata {
  return OperationMetadataSchema.parse({
    // W3C trace and span identifiers contain 16 and 8 bytes, respectively.
    traceId: createIdentifier(16),
    spanId: createIdentifier(8),
    links: options.links === undefined ? [] : options.links,
    ...(options.traceState === undefined ? {} : { traceState: options.traceState }),
  });
}

export function createChildContext(
  parent: OperationMetadata,
  options: Pick<ContextOptions, "links"> = {},
): OperationMetadata {
  const enclosing = OperationMetadataSchema.parse(parent);
  return OperationMetadataSchema.parse({
    traceId: enclosing.traceId,
    spanId: createIdentifier(8, enclosing.spanId),
    parentSpanId: enclosing.spanId,
    links: options.links === undefined ? [] : options.links,
    ...(enclosing.traceState === undefined ? {} : { traceState: enclosing.traceState }),
  });
}
