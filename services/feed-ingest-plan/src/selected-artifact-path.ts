/** Keep artifact configuration and produced paths inside the native relative-path contract. */
import { RelPathSchema } from "@idhazh/common-contracts";

// The filename and 128-bit UUID run-number limit are fixed output/identity protocols.
const artifactFilename = "selected-articles.json";
const maximumGeneratedRun = `9999-12-31-${((1n << 128n) - 1n).toString()}`;
export const ArtifactRootSchema = RelPathSchema.refine(root =>
  RelPathSchema.safeParse(`${root}/${maximumGeneratedRun}/${Number.MAX_SAFE_INTEGER}/${artifactFilename}`).success,
  "Artifact root must leave room for the generated execution, attempt and filename");

export function selectedArtifactPath(root: string, context: { run_id: string; writer: { attempt: number } }) {
  return RelPathSchema.parse(`${root}/${context.run_id}/${context.writer.attempt}/${artifactFilename}`);
}
