import { z } from "zod";
import {
  DeliveryPathSchema,
  DeliverySha256Schema,
  SafePersistDataCommitterSchema,
} from "./safe-persist-data-contract";

const RevisionSchema = z.string().regex(/^[a-f0-9]{40,64}$/, "Expected a Git revision");
const PermissionSchema = z.array(DeliveryPathSchema).min(1)
  .refine(paths => new Set(paths).size === paths.length, "Permissions must be unique")
  .refine(paths => !paths.some(path => ["state", "state/raw", "state/compact"].includes(path)),
    "Broad state permissions are refused");

const NamedFileSchema = z.strictObject({
  path: DeliveryPathSchema,
});
const WriteFileSchema = z.strictObject({
  sourcePath: DeliveryPathSchema,
  targetPath: DeliveryPathSchema,
  sha256: DeliverySha256Schema,
});

export const ReadGitDataInputSchema = z.strictObject({
  repository: z.string().min(1),
  max_bytes: z.number().int().positive(),
  paths: z.array(NamedFileSchema).min(1).max(128),
});

export const ReadGitDataResultSchema = z.strictObject({
  revision: RevisionSchema,
  files: z.array(z.strictObject({
    path: DeliveryPathSchema,
    sha256: DeliverySha256Schema.nullable(),
    content: z.string().base64().nullable(),
    ever_published: z.boolean(),
  })).max(128),
});

export const CompareAndSwapDataInputSchema = z.strictObject({
  sourceRoot: z.string().min(1),
  destination: z.strictObject({
    kind: z.literal("git"),
    repository: z.string().min(1),
  }),
  expected_revision: RevisionSchema,
  max_bytes: z.number().int().positive(),
  files: z.array(WriteFileSchema).min(1).max(128),
  permittedPaths: PermissionSchema,
  committer: SafePersistDataCommitterSchema,
  message: z.string().trim().min(1),
}).superRefine((input, context) => {
  const targets = input.files.map(file => file.targetPath);
  if (new Set(targets).size !== targets.length) {
    context.addIssue({ code: "custom", path: ["files"], message: "Target paths must be unique" });
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

export const CompareAndSwapDataResultSchema = z.discriminatedUnion("status", [
  z.strictObject({
    destination: z.literal("git"),
    status: z.literal("published"),
    expected_revision: RevisionSchema,
    revision: RevisionSchema,
    commit: RevisionSchema,
    paths: z.array(DeliveryPathSchema).min(1).max(128),
  }),
  z.strictObject({
    destination: z.literal("git"),
    status: z.literal("conflict"),
    expected_revision: RevisionSchema,
    revision: RevisionSchema,
    paths: z.array(DeliveryPathSchema).min(1).max(128),
  }),
]);

export type ReadGitDataInput = z.infer<typeof ReadGitDataInputSchema>;
export type ReadGitDataResult = z.infer<typeof ReadGitDataResultSchema>;
export type CompareAndSwapDataInput = z.infer<typeof CompareAndSwapDataInputSchema>;
export type CompareAndSwapDataResult = z.infer<typeof CompareAndSwapDataResultSchema>;
