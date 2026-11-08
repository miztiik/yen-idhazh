/** Compare generated native vectors with the actual common metadata and W3C helpers. */
import { z } from "../../../packages/common-contracts/node_modules/zod";
import { createChildContext, createRootContext } from "../../../packages/common-contracts/src/create-operation-context";
import { readTraceContext, writeTraceContext } from "../../../packages/common-contracts/src/propagate-trace-context";
import { OperationMetadataSchema } from "../../../packages/common-contracts/src/schemas/operation-metadata.schema";

const InputSchema = z.strictObject({
  metadata: z.array(z.strictObject({ name: z.string(), value: z.unknown() })),
  carriers: z.array(z.strictObject({
    name: z.string(),
    value: z.record(z.string(), z.union([z.string(), z.array(z.string())])),
  })),
  factoryParent: OperationMetadataSchema,
});

const input = InputSchema.parse(JSON.parse(await Bun.stdin.text()));
const root = createRootContext();
const linkedRoot = createRootContext({
  links: input.factoryParent.links,
  ...(input.factoryParent.traceState === undefined ? {} : {
    traceState: input.factoryParent.traceState,
  }),
});

const result = {
  schema: z.toJSONSchema(OperationMetadataSchema),
  metadata: input.metadata.map(({ name, value }) => {
    const parsed = OperationMetadataSchema.safeParse(value);
    return parsed.success
      ? { name, accepted: true, value: parsed.data, carrier: writeTraceContext(parsed.data) }
      : { name, accepted: false };
  }),
  carriers: input.carriers.map(({ name, value }) => {
    const operation = readTraceContext(value);
    return {
      name,
      value: operation ?? null,
      carrier: operation === undefined ? null : writeTraceContext(operation),
    };
  }),
  factories: [
    { root, child: createChildContext(root) },
    { root: linkedRoot, child: createChildContext(linkedRoot, { links: linkedRoot.links }) },
  ],
};
console.log(JSON.stringify(result));
