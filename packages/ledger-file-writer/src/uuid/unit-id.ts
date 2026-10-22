/** Creates the repeatable work-unit identity used by ledger files. */
import { createUuidV5 } from "./name-id";

const URL_NAMESPACE = "6ba7b811-9dad-11d1-80b4-00c04fd430c8";
const REPOSITORY_NAMESPACE_NAME = "github.com/miztiik/yen-idhazh";

const REPOSITORY_NAMESPACE = createUuidV5(URL_NAMESPACE, REPOSITORY_NAMESPACE_NAME);

export type UnitIdentity = {
  ledger: string;
  covers: string;
  runId: string;
  job: string | null;
  pipelineName: string | null;
  taskName: string | null;
  shard: number;
  producer: string;
};

export function createUnitId(identity: UnitIdentity): string {
  const generic = identity.pipelineName !== null || identity.taskName !== null;
  if (generic && (identity.pipelineName === null || identity.taskName === null)) {
    throw new Error("unit identity requires both pipeline_name and task_name");
  }
  if (!generic && identity.job === null) {
    throw new Error("unit identity requires legacy job or pipeline and task");
  }
  if (generic && identity.job !== null && identity.job !== identity.taskName) {
    throw new Error("generic job must be absent or match its task");
  }
  const label = generic ? `${identity.pipelineName}|${identity.taskName}` : identity.job!;
  const seed = `${identity.ledger}|${identity.covers}|${identity.runId}|${label}|${identity.shard}|${identity.producer}`;
  return createUuidV5(REPOSITORY_NAMESPACE, seed);
}
