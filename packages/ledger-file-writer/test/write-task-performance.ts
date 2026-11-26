/** Writes named Task Performance Parquet for the Python readback gate. */
import { TASK_PERFORMANCE_VERSION, TaskPerformanceRowSchema } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings } from "@idhazh/ledger-file-writer";

const outputRoot = process.argv[2];
if (outputRoot === undefined) throw new Error("a test output root is required");
const { rows, registryEntry, ledgerSettings, attempt } = await Bun.stdin.json() as {
  rows: unknown[];
  registryEntry: LedgerRegistration;
  ledgerSettings: LedgerSettings;
  attempt: number;
};
const paths = [];
for (const input of rows) {
  const row = TaskPerformanceRowSchema.parse(input);
  const result = await persistLedger({
    ledger: "task-performance",
    rowContract: { schema: TaskPerformanceRowSchema, schemaVersion: TASK_PERFORMANCE_VERSION },
    rows: [row], outputRoot, registryEntry, ledgerSettings, period: { tier: "raw", covers: row.date },
    writerContext: {
      run_id: row.run_id, pipeline_name: row.pipeline_name, task_name: row.task_name, shard: row.shard,
      attempt, job: null, producer: "tests.task-performance", git_sha: "a".repeat(40),
    },
  });
  if (result.status !== "written" || result.files.length !== 1) {
    throw new Error(`expected one Parquet for ${row.task_name}`);
  }
  paths.push(result.files[0]!.path);
}
process.stdout.write(`${JSON.stringify(paths)}\n`);
