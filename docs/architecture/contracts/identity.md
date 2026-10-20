# Identity and Deterministic Identifiers

**Last Updated**: 2026-10-20

How files, work units, events, and correlation contexts are identified across Python and TypeScript stages.

This page is the contract for identifiers under `state/raw/` and pipeline telemetry. Follows [persistence.md](persistence.md) and [schemas.md](schemas.md).

---

## 1. The Four Identifiers

| Identifier | Generation Standard | Seed / Components | Purpose | Lifespan |
| :--- | :--- | :--- | :--- | :--- |
| `unit_id` | RFC 4122 Version 5 (UUIDv5) | Fixed namespace `github.com/miztiik/yen-idhazh` + `{ledger}|{covers}|{run_id}|{job_or_pipeline}|{shard}|{producer}` | Identifies a repeatable unit of work. Identical across job re-runs. | Durable across retries |
| `file_id` | RFC 9562 Version 8 (UUIDv8) | 48-bit Unix millisecond clock + SHA-256(`{unit_id}|{attempt}|{written_at_ms}`) | Names an individual physical file under `state/raw/`. Chronologically sortable. | Immutable per file |
| `event_id` | RFC 4122 Version 5 (UUIDv5) with `evt_` prefix | Fixed namespace `github.com/miztiik/yen-idhazh` + `runner:{runner}:shard:{shard}:source:{url}:event:{type}` | Deterministically identifies an observable telemetry or audit event. | Durable in logs |
| `correlation_id` | Run identity string or run UUID | String `{date}-{execution}` (e.g. `2026-10-20-39315527491`) or GitHub Run ID | Traces an execution batch across stages (`plan`, `work`, `assemble`). | Lifetime of the run |

---

## 2. Unit Identity (`unit_id`)

The `unit_id` answers: **which work unit does this record belong to?**

- **Namespace**: `uuid.uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")` (fixed UUID `f81d4fae-7dec-11d0-a765-00a0c91e6bf6` base).
- **Seeding string**:
  ```
  {ledger}|{covers}|{run_id}|{label}|{shard}|{producer}
  ```
  Where `label` is either `job` (legacy) or `{pipeline_name}|{task_name}`.
- **Invariance**: When a GitHub Action job fails and is re-run, GitHub preserves the `run_id`. The re-run produces the identical `unit_id`.
- **Compaction resolution**: The ledger compaction union keeps the highest `attempt` for each `unit_id`, cleanly replacing earlier attempts without duplicates.

---

## 3. File Identity (`file_id`)

The `file_id` answers: **which physical file is this on disk?**

Every raw file written through the ledger door carries a newly minted `file_id`. It serves as the filename:
```
state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet
```

### RFC 9562 Version 8 Bit-Packing Layout

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   unix_ts_ms (high 32 bits)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   unix_ts_ms (low 16 bits)    |  ver (0x8)    |  rand_a (12)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|var (0b10)|                   rand_b (62 bits)                 |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       rand_b (continued)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

1. **High 48 bits**: Current UTC instant as epoch milliseconds (`Date.now()` or `written_at_ms`). Guarantees lexicographical and directory sorting by time.
2. **Version nibble (4 bits)**: `0x8` (UUIDv8).
3. **Random bits**: Derived from `SHA-256("{unit_id}|{attempt}|{written_at_ms}")`.
   - `rand_a` (12 bits): Bits 0 to 11 of SHA-256 digest.
   - `variant` (2 bits): `0b10` (RFC 4122/9562 standard variant).
   - `rand_b` (62 bits): Bits 16 to 77 of SHA-256 digest.

Both Python (`backend/idhazh/ledger/filenames.py`) and TypeScript (`packages/common-contracts/src/identity/`) use this exact bit packing.

---

## 4. Telemetry Event Identity (`event_id`)

Derived from the implementation in `.github/scripts/ai-pipeline.ts`:

- Telemetry and audit events require deterministic identity to deduplicate across runner retries and verify that the same article event is not double-counted.
- `buildDeterministicEventId(runnerName, shardId, sourceUrl, eventType)`:
  ```
  seed = "runner:" + runnerName + ":shard:" + shardId + ":source:" + sourceUrl + ":event:" + eventType
  event_id = "evt_" + generateUuidV5(seed, NAMESPACE)
  ```
- Every structured log line and rejection record carries this `event_id`.

---

## 5. Correlation Identity (`correlation_id`)

The `correlation_id` binds all operations belonging to a single pipeline invocation.

- **Format**: `{YYYY-MM-DD}-{execution_id}` (e.g. `2026-10-20-39315527491`).
- **Propagation**: Passed through HTTP headers (`x-correlation-id`), CLI flags (`--execution`), structured JSONL logs, and Parquet file envelopes.
- **Cross-Service Traceability**: Allows an operator to filter logs across `feed-ingest-plan`, `host-fingerprints`, `host-probes`, and `file-identities` with a single `jq` query.

---

## See also

- [persistence.md](persistence.md) - how the ledger door reads and writes file envelopes.
- [schemas.md](schemas.md) - schema rules and contract definitions.
- [../../how-to/execute-a-plan.md](../../how-to/execute-a-plan.md) - execution contract.
