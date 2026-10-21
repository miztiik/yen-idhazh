# Identity and Deterministic Identifiers

**Last Updated**: 2026-10-21

How files, work units, events, and correlation contexts are identified across Python and TypeScript stages.

This page is the contract for identifiers under `state/raw/` and pipeline telemetry. Follows [persistence.md](persistence.md) and [schemas.md](schemas.md).

---

## 1. The Four Identifiers

| Identifier | Generation Standard | Seed / Components | Purpose | Lifespan |
| :--- | :--- | :--- | :--- | :--- |
| `unit_id` | RFC 4122 Version 5 (UUIDv5) | Namespace UUID `de055294-e352-5d65-a1b7-d14b5e20844d` + legacy job or pipeline-task seed | Identifies a repeatable unit of work. Identical across job re-runs. | Durable across retries |
| `file_id` | RFC 9562 Version 8 (UUIDv8) | 48-bit Unix millisecond clock + SHA-256(`{unit_id}|{attempt}|{written_at_ms}`) | Names an individual physical file under `state/raw/`. Chronologically sortable. | Immutable per file |
| `event_id` | SHA-256 hexadecimal string | The `FeedIngestEvent` contract's declared `Sha256` field | Identifies one typed feed-ingest audit event. | Durable in the event record |
| `correlation_id` | Run identity string | The run's declared correlation value | Connects records from one execution; it is not file-envelope metadata. | Lifetime of the run |

---

## 2. Unit Identity (`unit_id`)

The `unit_id` answers: **which work unit does this record belong to?**

- **Namespace UUID**: `uuid.uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")`, which is `de055294-e352-5d65-a1b7-d14b5e20844d`. The `uuid.NAMESPACE_URL` value is only the input to this calculation.
- **Seeding string**:
  ```
  {ledger}|{covers}|{run_id}|{job}
  {ledger}|{covers}|{run_id}|{pipeline_name}|{task_name}|{shard}|{producer}
  ```
  The first form is the legacy job identity. The second identifies a pipeline task.
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
   - `rand_a` (12 bits): The low 12 bits of digest bytes 0 and 1.
   - `variant` (2 bits): `0b10` (RFC 4122/9562 standard variant).
   - `rand_b` (62 bits): The low 62 bits of digest bytes 2 through 9.

Python (`backend/idhazh/ledger/filenames.py`) is the identity authority. The reusable TypeScript writer implements the same bit packing in `packages/ledger-file-writer/src/uuid/`.

---

## 4. Telemetry Event Identity (`event_id`)

`FeedIngestEvent.event_id` is a SHA-256 hexadecimal string, as declared by the Python and TypeScript contracts. The contract defines its shape, not a UUID algorithm.

The older `.github/scripts/ai-pipeline.ts` helper `buildDeterministicEventId` returns an `evt_`-prefixed UUIDv5 for its own telemetry events. That helper is not the `FeedIngestEvent.event_id` contract and does not create planner event IDs. Rejection records do not declare an `event_id`.

---

## 5. Correlation Identity (`correlation_id`)

The `correlation_id` binds all operations belonging to a single pipeline invocation.

- **Format**: `{YYYY-MM-DD}-{execution_id}` (e.g. `2026-10-20-39315527491`).
- **Propagation**: Carried in run context and declared ledger rows.
- **Boundary**: A correlation ID is not metadata in the Parquet file envelope. The envelope carries only its declared identity and provenance fields.

---

## See also

- [persistence.md](persistence.md) - how the ledger door reads and writes file envelopes.
- [schemas.md](schemas.md) - schema rules and contract definitions.
- [../../how-to/execute-a-plan.md](../../how-to/execute-a-plan.md) - execution contract.
