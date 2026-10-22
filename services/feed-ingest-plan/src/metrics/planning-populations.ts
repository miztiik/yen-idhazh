/** Which complete recorded planning attempt supplies one day's measured populations? */
import { isDeepStrictEqual } from "node:util";
import {
  ArticleAssessmentRecordSchema, CONTRACT_VERSION, CandidateRejectionRecordSchema,
  EditorialSelectionRowSchema,
} from "@idhazh/common-contracts";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import type { SourceRunRecord } from "@idhazh/common-contracts";
import { selectCompleteAttempt } from "../read-ledger-history/complete-attempt";
import type { AttemptFinding, AttemptHistory, ProvenAttempt } from "../read-ledger-history/complete-attempt";
import { readLedgerDay } from "../read-ledger-history/read-period";
import type { NamedDayInput } from "../read-ledger-history/read-period";
import { uniqueRecorded } from "./fingerprint-dedup";
import {
  ArticleAssessmentContract, DiversityMetricContract, DispatchContract, SourceRunContract,
} from "./audit-contracts";

export type PopulationItem = Readonly<{ candidate_id: string; source_id: string; source_kind: string; url_key: string | null }>;
export type PlanningStage = "input" | "freshness" | "deduplication" | "normalization" | "selection";
export type PlanningPopulation = Readonly<{
  run_id: string; sources: readonly SourceRunRecord[];
  eligible: readonly PopulationItem[]; selected: readonly PopulationItem[];
  stages: Readonly<Record<PlanningStage, readonly PopulationItem[]>>;
}>;
export type PlanningDay = Readonly<{
  day: string; status: "rows" | "empty" | "missing" | "lost";
  runs: readonly PlanningPopulation[]; findings: readonly AttemptFinding[];
}>;
type CompletionLedger = keyof AttemptHistory["ledgers"];
type NamedPaths = Omit<NamedDayInput<object>, "ledger" | "contract">;
export type NamedPlanningHistory = Readonly<{
  sources: NamedPaths; ledgers: Readonly<Record<CompletionLedger, NamedPaths>>;
}>;

export async function readPlanningHistory(input: NamedPlanningHistory): Promise<AttemptHistory> {
  const sources = await readLedgerDay({
    ...input.sources, ledger: "source-runs",
    contract: SourceRunContract,
  });
  const schemas: Record<CompletionLedger, LedgerRowContract<object>> = {
    "article-assessments": ArticleAssessmentContract,
    diversity: DiversityMetricContract,
    "editorial-selections": { schema: EditorialSelectionRowSchema, schemaVersion: CONTRACT_VERSION },
    dispatches: DispatchContract,
    rejections: { schema: CandidateRejectionRecordSchema, schemaVersion: CONTRACT_VERSION },
  };
  const read = async (ledger: CompletionLedger) => {
    const named = input.ledgers[ledger];
    if (named.day !== sources.day) throw new Error("Named planning ledgers belong to different UTC days");
    return readLedgerDay({ ...named, ledger, contract: schemas[ledger] });
  };
  const [assessments, diversity, selections, dispatches, rejections] = await Promise.all([
    read("article-assessments"), read("diversity"), read("editorial-selections"), read("dispatches"), read("rejections"),
  ]);
  return { sources, ledgers: { "article-assessments": assessments, diversity, "editorial-selections": selections, dispatches, rejections } };
}

export function derivePlanningPopulation(attempt: ProvenAttempt): PlanningPopulation {
  const sources = new Map(attempt.sources.map(row => [row.source_id, row]));
  const assessments = uniqueRecorded(attempt.rows["article-assessments"].map(held => ArticleAssessmentRecordSchema.parse(held.row)),
    row => `${row.stage}/${row.candidate_id}`, isDeepStrictEqual);
  for (const row of assessments) {
    if (row.date !== attempt.date || row.correlation_id !== attempt.correlation_id
      || !isDeepStrictEqual(sources.get(row.source_id)?.source, row.source)) throw new Error("Historical assessment differs from its proven source attempt");
  }
  const rejected = uniqueRecorded(attempt.rows.rejections.map(held => CandidateRejectionRecordSchema.parse(held.row)),
    row => JSON.stringify([row.stage, row.subject, row.candidate_id ?? row.source_id, row.drop_reason]), isDeepStrictEqual);
  for (const row of rejected) {
    if (row.date !== attempt.date || row.correlation_id !== attempt.correlation_id
      || !sources.has(row.source_id)) throw new Error("Historical terminal loss differs from its proven source attempt");
  }
  for (const row of assessments) {
    const terminal = rejected.filter(loss => loss.candidate_id === row.candidate_id && loss.stage === row.stage);
    if (row.decision === "rejected" ? terminal.length !== 1 || terminal[0]!.drop_reason !== row.reason : terminal.length !== 0) {
      throw new Error("Historical assessment has no matching single terminal decision");
    }
    const first = assessments.find(item => item.stage === "harvest-feeds" && item.candidate_id === row.candidate_id);
    if (first === undefined || first.source_id !== row.source_id || first.url_key !== row.url_key) {
      throw new Error("Historical assessment changed its candidate attribution");
    }
  }
  if (rejected.some(loss => loss.candidate_id !== null && !assessments.some(row =>
    row.stage === loss.stage && row.candidate_id === loss.candidate_id && row.decision === "rejected"))) {
    throw new Error("Historical terminal article loss has no assessment");
  }
  const harvest = assessments.filter(row => row.stage === "harvest-feeds" && row.decision === "admitted");
  const screen = assessments.filter(row => row.stage === "screen-article-candidates");
  const curated = assessments.filter(row => row.stage === "curate-article-portfolio");
  const ids = (rows: typeof assessments) => new Set(rows.map(row => row.candidate_id));
  if (harvest.length !== screen.length || harvest.some(row => !ids(screen).has(row.candidate_id))) throw new Error("Historical screening membership is incomplete");
  const eligible = screen.filter(row => row.decision === "admitted");
  if (eligible.length !== curated.length || eligible.some(row => !ids(curated).has(row.candidate_id))) throw new Error("Historical curation membership is incomplete");
  const selections = uniqueRecorded(attempt.rows["editorial-selections"].map(held => EditorialSelectionRowSchema.parse(held.row)),
    row => row.candidate_id, isDeepStrictEqual);
  const selectedIds = new Set(curated.filter(row => row.decision === "selected").map(row => row.candidate_id));
  if (selections.length !== selectedIds.size || selections.some(row => !selectedIds.has(row.candidate_id))) throw new Error("Historical selections differ from recorded decisions");
  for (const row of selections) {
    const measured = curated.find(item => item.candidate_id === row.candidate_id)!;
    if (row.date !== attempt.date || row.correlation_id !== attempt.correlation_id
      || row.source_id !== measured.source_id || row.url_key !== measured.url_key
      || !isDeepStrictEqual(row.source, measured.source)) throw new Error("Historical selection attribution differs from its assessment");
  }
  const item = (row: typeof assessments[number]): PopulationItem => ({
    candidate_id: row.candidate_id, source_id: row.source_id, source_kind: row.source.kind, url_key: row.url_key,
  });
  const stale = new Set(screen.filter(row => row.reason === "STALE_MAX_AGE_EXCEEDED").map(row => row.candidate_id));
  const duplicate = new Set(curated.filter(row => row.reason === "DUPLICATE_CANONICAL_URL" || row.reason === "REPLACED_BY_CARRIER").map(row => row.candidate_id));
  const normalizedOut = new Set(curated.filter(row => row.reason === "SOURCE_QUOTA_EXCEEDED").map(row => row.candidate_id));
  const selected = curated.filter(row => row.decision === "selected").map(item);
  if (new Set(selected.map(row => row.url_key)).size !== selected.length) throw new Error("Historical selected primary articles are not unique");
  const stages = {
    input: harvest.map(item), freshness: harvest.filter(row => !stale.has(row.candidate_id)).map(item),
    deduplication: eligible.filter(row => !duplicate.has(row.candidate_id)).map(item),
    normalization: eligible.filter(row => !duplicate.has(row.candidate_id) && !normalizedOut.has(row.candidate_id)).map(item),
    selection: selected,
  };
  for (const source of attempt.sources) {
    for (const [field, members] of [
      ["harvested_count", stages.input], ["fresh_count", stages.freshness], ["eligible_count", eligible.map(item)],
      ["normalized_count", stages.normalization], ["selected_count", selected],
    ] as const) {
      if ((source[field] === null && field !== "harvested_count")
        || (source[field] !== null && source[field] !== members.filter(row => row.source_id === source.source_id).length)) {
        throw new Error(`Historical ${field} differs from settled membership`);
      }
    }
    if (source.duplicate_count !== curated.filter(row => row.source_id === source.source_id && duplicate.has(row.candidate_id)).length) {
      throw new Error("Historical duplicate count differs from terminal carrier losses");
    }
    if (source.parsed_count !== null && source.parsed_count !== assessments.filter(row => row.stage === "harvest-feeds" && row.source_id === source.source_id).length) {
      throw new Error("Historical parsed count differs from harvest observations");
    }
    if (source.status !== "active" && eligible.some(row => row.source_id === source.source_id)) throw new Error("Inactive historical source has eligible articles");
  }
  return { run_id: attempt.run_id, sources: attempt.sources, eligible: eligible.map(item), selected, stages };
}

export function settlePlanningDay(history: AttemptHistory): PlanningDay {
  const { day, status } = history.sources;
  if (status === "missing" || status === "lost") return { day, status, runs: [], findings: [] };
  if (history.sources.notices.some(notice => notice.startsWith("files-set-aside:"))) return { day, status: "missing", runs: [], findings: [] };
  if (status === "empty") return {
    day, status: Object.values(history.ledgers).some(ledger => ledger.status !== "empty") ? "missing" : "empty",
    runs: [], findings: [],
  };
  if (history.sources.rows.length === 0) throw new Error("Nonempty planning day has no source observations");
  const runs: PlanningPopulation[] = [];
  const findings: AttemptFinding[] = [];
  let missing = false;
  for (const run of new Set(history.sources.rows.filter(held => held.row.observation_phase === "plan_complete")
    .map(held => held.row.run_id))) {
    const resolution = selectCompleteAttempt(history, run);
    findings.push(...resolution.findings);
    if (resolution.selected === null) missing = true;
    else runs.push(derivePlanningPopulation(resolution.selected));
  }
  return { day, status: missing ? "missing" : "rows", runs, findings };
}
