import { z } from "zod";

function isRelativePath(value: string): boolean {
  const parts = value.split("/");
  return value === parts.join("/")
    && !value.startsWith("/")
    && !value.includes("\\")
    && !value.includes(":")
    && !/[\u0000-\u001f\u007f]/.test(value)
    && ![...value].some(character => "*?[]!^".includes(character))
    && parts.every(part => part !== "" && part !== "." && part !== ".." && part.toLowerCase() !== ".git");
}

export const DeliveryPathSchema = z.string().min(1).refine(isRelativePath, "Expected a canonical relative path");
export const DeliverySha256Schema = z.string().regex(/^[a-f0-9]{64}$/, "Expected a lowercase SHA256 digest");

const PositiveSecondsSchema = z.number().finite().positive();
const PushRetrySchema = z.strictObject({
  deadline_seconds: z.record(z.string(), PositiveSecondsSchema)
    .refine(deadlines => Object.hasOwn(deadlines, "default"), "deadline_seconds.default is required"),
  base_step_seconds: PositiveSecondsSchema,
  ceiling_seconds: PositiveSecondsSchema,
  ceiling_after: z.number().int().positive(),
}).superRefine((retry, context) => {
  if (retry.base_step_seconds > retry.ceiling_seconds) {
    context.addIssue({ code: "custom", path: ["base_step_seconds"], message: "Must not exceed ceiling_seconds" });
  }
});

const FileSchema = z.strictObject({
  sourcePath: DeliveryPathSchema,
  targetPath: DeliveryPathSchema,
  sha256: DeliverySha256Schema,
});

const CommonInput = {
  sourceRoot: z.string().min(1),
  files: z.array(FileSchema),
  permittedPaths: z.array(DeliveryPathSchema),
};

export const SafePersistDataCommitterSchema = z.strictObject({
  name: z.string().trim().min(1).refine(value => !/[\r\n]/.test(value), "Committer name must be one line"),
  email: z.email(),
});

const GitInputSchema = z.strictObject({
  ...CommonInput,
  destination: z.strictObject({
    kind: z.literal("git"),
    repository: z.string().min(1),
  }),
  committer: SafePersistDataCommitterSchema,
  message: z.string().trim().min(1),
  retry: PushRetrySchema,
});

const ArtifactDirectoryInputSchema = z.strictObject({
  ...CommonInput,
  destination: z.strictObject({
    kind: z.literal("artifact-directory"),
    directory: z.string().min(1),
  }),
});

export const SafePersistDataInputSchema = z.union([
  GitInputSchema,
  ArtifactDirectoryInputSchema,
]).superRefine((input, context) => {
  const targets = input.files.map(file => file.targetPath);
  if (new Set(targets).size !== targets.length) {
    context.addIssue({ code: "custom", path: ["files"], message: "Target paths must be unique" });
  }
  if (new Set(input.permittedPaths).size !== input.permittedPaths.length) {
    context.addIssue({ code: "custom", path: ["permittedPaths"], message: "Permitted paths must be unique" });
  }
  if (input.permittedPaths.some(path => ["state", "state/raw", "state/compact"].includes(path))) {
    context.addIssue({ code: "custom", path: ["permittedPaths"], message: "Broad state permissions are refused" });
  }
  for (const [index, file] of input.files.entries()) {
    if (!input.permittedPaths.some(scope => file.targetPath === scope || file.targetPath.startsWith(`${scope}/`))) {
      context.addIssue({
        code: "custom",
        path: ["files", index, "targetPath"],
        message: "Target is outside independently declared permissions",
      });
    }
  }
});

const GitResultSchema = z.strictObject({
  destination: z.literal("git"),
  status: z.enum(["landed", "already-on-main", "no-changes"]),
  commit: z.string().regex(/^[a-f0-9]{40,64}$/).nullable(),
  files: z.number().int().nonnegative(),
  paths: z.array(DeliveryPathSchema),
}).superRefine((result, context) => {
  if ((result.status === "no-changes") !== (result.commit === null)) {
    context.addIssue({ code: "custom", message: "Commit identity must match the delivery status" });
  }
  if ((result.status === "no-changes") !== (result.files === 0)
    || new Set(result.paths).size !== result.files) {
    context.addIssue({ code: "custom", message: "Git delivery status, file count and paths must agree" });
  }
});

const ArtifactResultSchema = z.strictObject({
  destination: z.literal("artifact-directory"),
  status: z.enum(["written", "already-present", "no-changes"]),
  files: z.number().int().nonnegative(),
  paths: z.array(DeliveryPathSchema),
}).superRefine((result, context) => {
  if ((result.status === "no-changes") !== (result.files === 0)
    || new Set(result.paths).size !== result.files) {
    context.addIssue({ code: "custom", message: "Artifact delivery status, file count and paths must agree" });
  }
});

export const SafePersistDataResultSchema = z.discriminatedUnion("destination", [
  GitResultSchema,
  ArtifactResultSchema,
]);

export type SafePersistDataInput = z.infer<typeof SafePersistDataInputSchema>;
export type SafePersistDataResult = z.infer<typeof SafePersistDataResultSchema>;
export type SafePersistDataCommitter = z.infer<typeof SafePersistDataCommitterSchema>;
