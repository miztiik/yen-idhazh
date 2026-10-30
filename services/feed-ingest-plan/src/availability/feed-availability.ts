/** Reserve and finish one logical feed check against the mutable published state. */
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  FeedAvailabilityCompletionSchema,
  FeedAvailabilityEnrollmentSchema,
  FeedAvailabilityStateSchema,
} from "@idhazh/common-contracts";
import type {
  FeedAvailabilityCompletion,
  FeedAvailabilityEnrollment,
  FeedAvailabilityRecord,
  FeedAvailabilityState,
} from "@idhazh/common-contracts";
import {
  compare_and_swap_data,
  read_git_data,
} from "@idhazh/data-delivery";
import type { PlanInputs } from "../load-plan-inputs";
import type { ConfiguredSource } from "../harvest-feeds/load-harvest-inputs";
import type { FetchResult } from "../harvest-feeds/robots-policy";
import { PlanError } from "../api/plan-request";
import type { FeedAvailabilityConfig } from "./availability-config";

const STATE_PATH_PREFIX = "state/raw/planner/feed-availability/";
const STATE_PERMISSION = "state/raw/planner/feed-availability";
const CHANGE = "Add durable per-feed reservations, rest deadlines and recovery retirement.";
const requestsInFlight = new WeakMap<PlanInputs, Set<string>>();
const transactionTails = new Map<string, Promise<void>>();

export type FeedAvailabilityStatus = "eligible" | "resting" | "retired" | "unknown";
export type FeedAvailabilityView = Readonly<{
  feed_id: string;
  endpoint_key: string;
  status: FeedAvailabilityStatus;
  consecutive_failed_checks: number;
  rest_until: string | null;
  retired_at: string | null;
  failed_recovery_checks: number;
  first_confirmed_failure_at: string | null;
}>;
export type FeedAvailabilitySnapshot = Readonly<{
  revision: string;
  feeds: readonly FeedAvailabilityView[];
  eligible_feed_ids: readonly string[];
}>;

type ActiveSource = Pick<ConfiguredSource, "id" | "url" | "status">;
type ReservationContext = Readonly<{
  request_id: string;
  run_id: string;
  attempt: number;
}>;
type CompletionInput = ReservationContext & Readonly<{
  completed_at: string;
  result: FeedAvailabilityCompletion["result"];
  http_status: number | null;
}>;

function activeFor(inputs: PlanInputs) {
  let active = requestsInFlight.get(inputs);
  if (active === undefined) { active = new Set(); requestsInFlight.set(inputs, active); }
  return active;
}

function endpointKey(url: string) {
  return createHash("sha256").update(url, "utf8").digest("hex");
}

function parseSaved<T>(bytes: Uint8Array, parse: (raw: unknown) => T, path: string): T {
  try { return parse(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes))); }
  catch (error) {
    throw new PlanError("FEED_AVAILABILITY_STATE_INVALID",
      `Established feed availability file is corrupt: ${path}`, path);
  }
}

function sourceMap(inputs: PlanInputs): Map<string, ActiveSource> {
  const active = inputs.harvest.sources.filter(source => source.status === "active");
  if (active.length > inputs.availability.max_enrolled_feeds) {
    throw new PlanError("FEED_AVAILABILITY_CONFIG_INVALID", "Active feed count exceeds availability.max_enrolled_feeds", "feed_id");
  }
  const ids = active.map(source => source.id);
  if (new Set(ids).size !== ids.length) throw new Error("Active feed IDs must be unique for availability");
  for (const event of inputs.availability.operator_enrollments) {
    if (!active.some(source => source.id === event.feed_id)) {
      throw new PlanError("FEED_AVAILABILITY_CONFIG_INVALID",
        `availability.operator_enrollments names a feed that is not active: ${event.feed_id}`, "feed_id");
    }
  }
  return new Map(active.map(source => [source.id, source]));
}

function initialRecord(source: ActiveSource, enrollmentId: string | null = null): FeedAvailabilityRecord {
  return FeedAvailabilityStateSchema.shape.feeds.element.parse({
    feed_id: source.id,
    endpoint_key: endpointKey(source.url),
    consecutive_failed_checks: 0,
    rest_until: null,
    retired_at: null,
    episode: null,
    reservation: null,
    last_completion: null,
    operator_enrollment_id: enrollmentId,
  });
}

function catalogFingerprint(sources: ReadonlyMap<string, ActiveSource>) {
  const value = [...sources.values()].sort((a, b) => a.id.localeCompare(b.id))
    .map(source => `${source.id}\n${endpointKey(source.url)}`).join("\n");
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function initializedState(sources: ReadonlyMap<string, ActiveSource>, at: string): FeedAvailabilityState {
  return FeedAvailabilityStateSchema.parse({
    version: "2026-10-30",
    changelog: [{ version: "2026-10-30", change: CHANGE }],
    sequence: 0,
    updated_at: at,
    feeds: [...sources.values()].map(source => initialRecord(source)).sort((a, b) => a.feed_id.localeCompare(b.feed_id)),
  });
}

function initialEnrollment(sources: ReadonlyMap<string, ActiveSource>, at: string): FeedAvailabilityEnrollment {
  return FeedAvailabilityEnrollmentSchema.parse({
    version: "2026-10-30",
    changelog: [{ version: "2026-10-30", change: CHANGE }],
    initialized_at: at,
    initial_feed_ids: [...sources.keys()].sort(),
    catalog_sha256: catalogFingerprint(sources),
  });
}

function verifyPaths(inputs: PlanInputs) {
  const { state_path, enrollment_path } = inputs.availability;
  for (const path of [state_path, enrollment_path]) {
    if (!path.startsWith(STATE_PATH_PREFIX)) {
      throw new Error(`Availability paths must stay under ${STATE_PERMISSION}`);
    }
  }
  if (state_path === enrollment_path) throw new Error("Availability state and enrollment paths must differ");
}

function rawFiles(snapshot: Awaited<ReturnType<typeof read_git_data>>, inputs: PlanInputs) {
  const state = snapshot.files.find(file => file.path === inputs.availability.state_path);
  const enrollment = snapshot.files.find(file => file.path === inputs.availability.enrollment_path);
  if (state === undefined || enrollment === undefined) throw new Error("Availability publication omitted a named file");
  return { state, enrollment };
}

function recordStatus(record: FeedAvailabilityRecord, at: string): FeedAvailabilityStatus {
  if (record.retired_at !== null) return "retired";
  if (record.reservation !== null) return "unknown";
  if (record.rest_until !== null && Date.parse(record.rest_until) > Date.parse(at)) return "resting";
  return "eligible";
}

function view(record: FeedAvailabilityRecord, at: string): FeedAvailabilityView {
  return {
    feed_id: record.feed_id,
    endpoint_key: record.endpoint_key,
    status: recordStatus(record, at),
    consecutive_failed_checks: record.consecutive_failed_checks,
    rest_until: record.rest_until,
    retired_at: record.retired_at,
    failed_recovery_checks: record.episode?.failed_recovery_checks ?? 0,
    first_confirmed_failure_at: record.episode?.first_confirmed_failure_at ?? null,
  };
}

function effectiveUpdatedAt(previous: string, at: string) {
  return Date.parse(previous) > Date.parse(at) ? previous : at;
}

function setSourceEnrollments(
  state: FeedAvailabilityState,
  sources: ReadonlyMap<string, ActiveSource>,
  enrollments: PlanInputs["availability"]["operator_enrollments"],
) {
  let changed = false;
  const records = new Map(state.feeds.map(record => [record.feed_id, record]));
  for (const event of enrollments.filter(value => sources.has(value.feed_id))) {
    const source = sources.get(event.feed_id)!;
    const prior = records.get(source.id);
    if (prior?.operator_enrollment_id === event.enrollment_id) continue;
    records.set(source.id, initialRecord(source, event.enrollment_id));
    changed = true;
  }
  state.feeds = [...records.values()].sort((a, b) => a.feed_id.localeCompare(b.feed_id));
  for (const source of sources.values()) {
    const record = records.get(source.id);
    if (record === undefined) {
      throw new PlanError("FEED_AVAILABILITY_UNENROLLED", "Feed needs an explicit availability enrollment", "feed_id");
    }
    if (record.endpoint_key !== endpointKey(source.url)) {
      throw new PlanError("FEED_AVAILABILITY_ENDPOINT_CHANGED",
        "Feed address changed; add an explicit operator enrollment before checking it", "feed_id");
    }
  }
  return changed;
}

function markForeignReservationsUnknown(state: FeedAvailabilityState, inputs: PlanInputs) {
  let changed = false;
  const active = activeFor(inputs);
  for (const record of state.feeds) {
    const reservation = record.reservation;
    if (reservation?.status === "reserved" && !active.has(`${record.feed_id}:${reservation.request_id}`)) {
      record.reservation = { ...reservation, status: "unknown" };
      changed = true;
    }
  }
  return changed;
}

async function stageState(
  inputs: PlanInputs,
  state: FeedAvailabilityState,
  enrollment: FeedAvailabilityEnrollment | null,
  expectedRevision: string,
) {
  const root = await mkdtemp(join(tmpdir(), "feed-availability-"));
  try {
    const completed = join(root, "completed");
    await mkdir(completed);
    const stateBytes = new TextEncoder().encode(`${JSON.stringify(state)}\n`);
    await writeFile(join(completed, "state.json"), stateBytes);
    const files = [{
      sourcePath: "completed/state.json",
      targetPath: inputs.availability.state_path,
      sha256: createHash("sha256").update(stateBytes).digest("hex"),
    }];
    if (enrollment !== null) {
      const markerBytes = new TextEncoder().encode(`${JSON.stringify(enrollment)}\n`);
      await writeFile(join(completed, "enrollment.json"), markerBytes);
      files.push({
        sourcePath: "completed/enrollment.json",
        targetPath: inputs.availability.enrollment_path,
        sha256: createHash("sha256").update(markerBytes).digest("hex"),
      });
    }
    return await compare_and_swap_data({
      sourceRoot: root,
      destination: { kind: "git", repository: inputs.root },
      expected_revision: expectedRevision,
      max_bytes: inputs.availability.max_state_bytes,
      files,
      permittedPaths: [STATE_PERMISSION],
      committer: inputs.availabilityCommitter,
      message: "Update feed availability state",
    });
  } finally { await rm(root, { recursive: true, force: true }); }
}

async function transactUnserialized<T>(
  inputs: PlanInputs,
  at: string,
  mutate: (state: FeedAvailabilityState) => { value: T; changed: boolean },
): Promise<{ state: FeedAvailabilityState; revision: string; value: T }> {
  verifyPaths(inputs);
  const atInstant = at;
  const sources = sourceMap(inputs);
  for (let attempt = 0; attempt < inputs.availability.max_cas_refresh_attempts; attempt++) {
    let loaded: Awaited<ReturnType<typeof read_git_data>>;
    try {
      loaded = await read_git_data({
        repository: inputs.root,
        max_bytes: inputs.availability.max_state_bytes,
        paths: [{ path: inputs.availability.state_path }, { path: inputs.availability.enrollment_path }],
      });
    } catch (error) {
      if (error instanceof PlanError) throw error;
      const detail = error instanceof Error ? error.message : "unknown failure";
      throw new PlanError("FEED_AVAILABILITY_READ_FAILED",
        `Could not read the published feed availability state: ${detail}`, "availability.state_path");
    }
    const { state: stateFile, enrollment: enrollmentFile } = rawFiles(loaded, inputs);
    let state: FeedAvailabilityState;
    let enrollment: FeedAvailabilityEnrollment | null = null;
    let changed = false;
    let initial = false;
    if (stateFile.content === null && enrollmentFile.content === null) {
      if (stateFile.ever_published || enrollmentFile.ever_published) {
        throw new PlanError("FEED_AVAILABILITY_STATE_INVALID",
          "Previously established feed availability state and enrollment are both missing", "availability.state_path");
      }
      if (inputs.availability.initial_enrollment !== "all-active-configured-sources-once") {
        throw new PlanError("FEED_AVAILABILITY_STATE_INVALID", "Feed availability needs an explicit initial enrollment", "availability.initial_enrollment");
      }
      state = initializedState(sources, atInstant);
      enrollment = initialEnrollment(sources, atInstant);
      changed = true;
      initial = true;
    } else {
      if (stateFile.content === null || enrollmentFile.content === null) {
        throw new PlanError("FEED_AVAILABILITY_STATE_INVALID",
          "Established feed availability state or its enrollment marker is missing", "availability.state_path");
      }
      state = parseSaved(Buffer.from(stateFile.content, "base64"), value => FeedAvailabilityStateSchema.parse(value),
        inputs.availability.state_path);
      enrollment = parseSaved(Buffer.from(enrollmentFile.content, "base64"),
        value => FeedAvailabilityEnrollmentSchema.parse(value), inputs.availability.enrollment_path);
      if (state.feeds.length > inputs.availability.max_enrolled_feeds) {
        throw new PlanError("FEED_AVAILABILITY_STATE_INVALID",
          "Feed availability state exceeds availability.max_enrolled_feeds", "availability.state_path");
      }
      changed = setSourceEnrollments(state, sources, inputs.availability.operator_enrollments);
      changed = markForeignReservationsUnknown(state, inputs) || changed;
    }
    const result = mutate(state);
    changed = changed || result.changed;
    if (!changed) return { state, revision: loaded.revision, value: result.value };
    state.sequence++;
    state.updated_at = effectiveUpdatedAt(state.updated_at, atInstant);
    state = FeedAvailabilityStateSchema.parse(state);
    if (state.feeds.length > inputs.availability.max_enrolled_feeds) {
      throw new PlanError("FEED_AVAILABILITY_STATE_INVALID",
        "Feed availability state exceeds availability.max_enrolled_feeds", "availability.state_path");
    }
    let publication: Awaited<ReturnType<typeof stageState>>;
    try { publication = await stageState(inputs, state, initial ? enrollment : null, loaded.revision); }
    catch (error) {
      if (error instanceof PlanError) throw error;
      const detail = error instanceof Error ? error.message : "unknown failure";
      throw new PlanError("FEED_AVAILABILITY_PUBLISH_FAILED",
        `Could not publish feed availability state: ${detail}`, "availability.state_path");
    }
    if (publication.status === "published") {
      return { state, revision: publication.revision, value: result.value };
    }
  }
  throw new PlanError("FEED_CHECK_BUSY", "Feed availability changed repeatedly; refresh before retrying", "feed_id");
}

async function transact<T>(
  inputs: PlanInputs,
  at: string,
  mutate: (state: FeedAvailabilityState) => { value: T; changed: boolean },
): Promise<{ state: FeedAvailabilityState; revision: string; value: T }> {
  const key = inputs.root;
  const previous = transactionTails.get(key) ?? Promise.resolve();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const tail = previous.then(() => gate);
  transactionTails.set(key, tail);
  await previous;
  try { return await transactUnserialized(inputs, at, mutate); }
  finally {
    release();
    if (transactionTails.get(key) === tail) transactionTails.delete(key);
  }
}

export async function readFeedAvailability(inputs: PlanInputs, at = new Date().toISOString()): Promise<FeedAvailabilitySnapshot> {
  const current = await transact(inputs, at, () => ({ value: undefined, changed: false }));
  const feeds = current.state.feeds.map(record => view(record, at));
  return {
    revision: current.revision,
    feeds,
    eligible_feed_ids: feeds.filter(feed => feed.status === "eligible").map(feed => feed.feed_id),
  };
}

function findSourceRecord(state: FeedAvailabilityState, source: ActiveSource) {
  const record = state.feeds.find(value => value.feed_id === source.id);
  if (record === undefined) throw new PlanError("FEED_AVAILABILITY_UNENROLLED", "Feed needs an explicit availability enrollment", "feed_id");
  if (record.endpoint_key !== endpointKey(source.url)) {
    throw new PlanError("FEED_AVAILABILITY_ENDPOINT_CHANGED",
      "Feed address changed; add an explicit operator enrollment before checking it", "feed_id");
  }
  return record;
}

export async function reserveFeedCheck(
  inputs: PlanInputs,
  source: ActiveSource,
  request: ReservationContext,
  at = new Date().toISOString(),
) {
  if (source.status !== "active") throw new PlanError("INVALID_REQUEST", "Availability checks require an active feed", "feed_id");
  const reservedAt = at;
  const result = await transact(inputs, reservedAt, state => {
    const record = findSourceRecord(state, source);
    if (record.retired_at !== null) {
      throw new PlanError("FEED_RETIRED", "Feed is retired; an operator must explicitly re-enroll it", "feed_id");
    }
    if (record.reservation !== null) {
      throw new PlanError("FEED_CHECK_BUSY", "Feed already has a reserved or interrupted check", "feed_id");
    }
    if (record.rest_until !== null && Date.parse(reservedAt) < Date.parse(record.rest_until)) {
      throw new PlanError("FEED_RESTING", "Feed is resting until its UTC recovery deadline", "feed_id");
    }
    record.reservation = {
      request_id: request.request_id, run_id: request.run_id, attempt: request.attempt,
      reserved_at: reservedAt, phase: "fetch", status: "reserved",
    };
    return { value: record, changed: true };
  });
  activeFor(inputs).add(`${source.id}:${request.request_id}`);
  return result.value;
}

export async function claimFeedParse(
  inputs: PlanInputs,
  source: ActiveSource,
  request: ReservationContext,
  at = new Date().toISOString(),
) {
  const result = await transact(inputs, at, state => {
    const record = findSourceRecord(state, source);
    const reservation = record.reservation;
    if (reservation === null || reservation.request_id !== request.request_id
      || reservation.run_id !== request.run_id || reservation.attempt !== request.attempt) {
      throw new PlanError("REQUEST_CONFLICT", "Feed parse has no matching durable check reservation", "fetch_request_id");
    }
    if (reservation.phase !== "fetch") {
      throw new PlanError("FEED_CHECK_BUSY", "Feed response already has an active or interrupted parse", "fetch_request_id");
    }
    record.reservation = { ...reservation, phase: "parse", status: "reserved" };
    return { value: record.reservation, changed: true };
  });
  activeFor(inputs).add(`${source.id}:${request.request_id}`);
  return result.value;
}

function completionMatches(left: FeedAvailabilityCompletion, right: CompletionInput) {
  return left.request_id === right.request_id && left.run_id === right.run_id
    && left.attempt === right.attempt && left.result === right.result && left.http_status === right.http_status;
}

function checkedDeadline(at: string, hours: number) {
  const deadline = Date.parse(at) + hours * 60 * 60 * 1000;
  if (!Number.isFinite(deadline)) throw new Error("Availability deadline exceeds the supported UTC range");
  return new Date(deadline).toISOString();
}

function canRetire(record: FeedAvailabilityRecord, check: CompletionInput, config: FeedAvailabilityConfig) {
  const episode = record.episode;
  return episode !== null
    && episode.failed_recovery_checks >= config.failed_recovery_checks_before_retirement
    && Date.parse(check.completed_at) - Date.parse(episode.first_confirmed_failure_at)
      >= config.retirement_minimum_age_hours * 60 * 60 * 1000;
}

export function applyAvailabilityCompletion(
  record: FeedAvailabilityRecord,
  check: CompletionInput,
  config: FeedAvailabilityConfig,
) {
  const recovery = record.rest_until !== null && Date.parse(check.completed_at) >= Date.parse(record.rest_until);
  const completion = FeedAvailabilityCompletionSchema.parse({
    request_id: check.request_id,
    run_id: check.run_id,
    attempt: check.attempt,
    completed_at: check.completed_at,
    result: check.result,
    http_status: check.http_status,
  });
  if (check.result === "valid-feed") {
    record.consecutive_failed_checks = 0;
    record.rest_until = null;
    record.episode = null;
    record.retired_at = null;
    record.last_completion = completion;
    record.reservation = null;
    return;
  }
  record.consecutive_failed_checks++;
  if (check.result === "confirmed-http-failure") {
    if (record.episode === null) {
      record.episode = { first_confirmed_failure_at: check.completed_at, failed_recovery_checks: 0 };
    } else if (recovery) {
      record.episode.failed_recovery_checks++;
    }
  }
  record.rest_until = record.consecutive_failed_checks >= config.consecutive_failed_checks_before_rest
    ? checkedDeadline(check.completed_at, recovery ? config.recovery_rest_hours : config.rest_hours)
    : null;
  record.last_completion = completion;
  record.reservation = null;
  if (check.result === "confirmed-http-failure" && recovery && canRetire(record, check, config)) {
    record.retired_at = check.completed_at;
    record.rest_until = null;
  }
}

export async function completeFeedCheck(
  inputs: PlanInputs,
  source: ActiveSource,
  check: CompletionInput,
) {
  try {
    const result = await transact(inputs, check.completed_at, state => {
      const record = findSourceRecord(state, source);
      if (record.reservation === null) {
        if (record.last_completion !== null && completionMatches(record.last_completion, check)) {
          return { value: record, changed: false };
        }
        throw new PlanError("REQUEST_CONFLICT", "Feed check completion has no matching reservation", "request_id");
      }
      if (record.reservation.request_id !== check.request_id || record.reservation.run_id !== check.run_id
        || record.reservation.attempt !== check.attempt) {
        throw new PlanError("REQUEST_CONFLICT", "Stale feed check cannot complete a newer reservation", "request_id");
      }
      if (check.result === "confirmed-http-failure"
        && !(check.http_status === 404 || check.http_status === 410 || (check.http_status !== null && check.http_status >= 500))) {
        throw new PlanError("ARTIFACT_INVALID", "Only confirmed HTTP 404, 410 or 5xx can advance retirement", "http_status");
      }
      applyAvailabilityCompletion(record, check, inputs.availability);
      return { value: record, changed: true };
    });
    return view(result.value, check.completed_at);
  } finally { activeFor(inputs).delete(`${source.id}:${check.request_id}`); }
}

export async function markFeedCheckUnknown(
  inputs: PlanInputs,
  source: ActiveSource,
  request: Pick<ReservationContext, "request_id" | "run_id">,
  at = new Date().toISOString(),
) {
  try {
    await transact(inputs, at, state => {
      const record = findSourceRecord(state, source);
      const held = record.reservation;
      if (held === null || held.request_id !== request.request_id || held.run_id !== request.run_id) {
        return { value: undefined, changed: false };
      }
      if (held.status === "unknown") return { value: undefined, changed: false };
      record.reservation = { ...held, status: "unknown" };
      return { value: undefined, changed: true };
    });
  } finally { activeFor(inputs).delete(`${source.id}:${request.request_id}`); }
}

export function feedFetchFailureResult(fetched: Pick<FetchResult, "failure" | "http_status">): CompletionInput["result"] {
  if (fetched.failure === "http") {
    if (fetched.http_status === 404 || fetched.http_status === 410
      || (fetched.http_status !== null && fetched.http_status >= 500)) return "confirmed-http-failure";
    return "other-http-failure";
  }
  if (fetched.failure === "timeout") return "timeout";
  if (fetched.failure === "robots-denied" || fetched.failure === "robots-unknown") return "robots";
  if (fetched.failure === "dns" || fetched.failure === "network") return "transport-unknown";
  return "local-failure";
}

export function parserFailureResult(failure: string | null): CompletionInput["result"] | null {
  if (failure === null) return "valid-feed";
  if (failure === "parser-cancelled") return null;
  return "local-failure";
}

export function feedCheckIsCancelled(runtimeSignal?: AbortSignal, requestSignal?: AbortSignal) {
  return runtimeSignal?.aborted === true || requestSignal?.aborted === true;
}
